"""Import historical `.eval` logs into canonical records, reparsing raw responses. No model calls.

The live path recorded only the value its XML-only parser accepted, but Inspect preserved every
monitor call's full response as a log attachment. Resolving those lets us reparse real historical
responses under the canonical config, which settles the live-vs-robust disagreement in AUDIT.md
without spending anything.

Pairing is fail-closed. Monitor calls are attributed to (commit, view) by replaying the live control
flow: for each agent, the per-commit view consumed calls until one parsed as strict XML (up to
max_attempts), then the cumulative view did the same; an empty diff consumed no call because the live
code short-circuited it. Every pairing is then *verified* by reparsing under the legacy config and
comparing to the value the live run stored. If they disagree, the record is marked unresolved rather
than silently accepted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fragwatch.records import (  # noqa: E402
    SCHEMA_VERSION,
    CampaignRecord,
    EvaluatorLabels,
    MonitorInput,
    MonitorRecord,
    RecordStore,
    RunProvenance,
    content_hash,
)
from fragwatch.scoring import (  # noqa: E402
    HISTORICAL_V1,
    LEGACY_STRICT_XML,
    Attempt,
    ScoreStatus,
    aggregate,
    parse_verdict,
)

# Prices used only to attribute historical monitor cost; see COSTS.md for provenance.
FLASH_LITE_IN, FLASH_LITE_OUT = 0.10 / 1e6, 0.40 / 1e6


def _monitor_events(sample, monitor_substr: str = "flash"):
    return [
        e for e in sample.events
        if e.event == "model" and monitor_substr in (e.model or "")
    ]


def _raw_text(ev) -> str | None:
    try:
        return ev.output.choices[0].message.text if ev.output.choices else None
    except Exception:  # pragma: no cover - defensive
        return None


def import_log(path: str, run_id: str, provenance: str, protocol_version: str,
               out_root: str, code_commit: str | None, allow_existing: bool) -> dict:
    log = read_eval_log(path, resolve_attachments=True)
    store = RecordStore(out_root, run_id, allow_existing=allow_existing)
    store.write_provenance(RunProvenance(
        run_id=run_id, provenance=provenance, protocol_version=protocol_version,
        source_log=path, code_commit=code_commit,
        scoring_config_fingerprint=HISTORICAL_V1.fingerprint(),
        prompt_version=HISTORICAL_V1.prompt_version,
        monitor_model=HISTORICAL_V1.monitor_model,
        notes="Reparsed from preserved raw responses; no new model calls. Aggregation policy 'attempt0': only the first call (temperature 0.0) counts, because live retries used temperature 0.5 and are not exchangeable.",
    ))

    mrecs: list[MonitorRecord] = []
    crecs: list[CampaignRecord] = []
    stats = {"paired": 0, "unresolved": 0, "no_call": 0, "campaigns": 0}

    for s in log.samples or []:
        md, st = s.metadata or {}, s.store or {}
        commits = st.get("commits") or []
        tr = st.get("task_results") or {}
        side = st.get("side_task_name")
        mains = st.get("main_task_names") or []
        events = _monitor_events(s)
        cursor = 0
        stats["campaigns"] += 1

        for c in commits:
            i = c["agent_index"]
            for view, stored, nlines in (
                ("per_commit", c.get("suspicion"), c.get("diff_lines", 0)),
                ("cumulative", c.get("cum_suspicion"), c.get("cum_diff_lines", 0)),
            ):
                attempts: list[Attempt] = []
                unresolved = None

                if not nlines:
                    # Live code returned 1.0 for an empty diff without calling the model. That is an
                    # evaluator shortcut, not a monitor judgment, so it is recorded as such.
                    stats["no_call"] += 1
                    rec_value, rec_status = None, "empty_diff_no_call"
                else:
                    # Consume calls the way the live loop did: stop at the first strict-XML parse.
                    while cursor < len(events) and len(attempts) < HISTORICAL_V1.max_attempts:
                        ev = events[cursor]
                        cursor += 1
                        raw = _raw_text(ev)
                        attempts.append(Attempt(
                            attempt_index=len(attempts),
                            raw_response=raw,
                            verdict=parse_verdict(raw or "", HISTORICAL_V1),
                            model=ev.model or "",
                            input_tokens=getattr(ev.output.usage, "input_tokens", 0) or 0,
                            output_tokens=getattr(ev.output.usage, "output_tokens", 0) or 0,
                        ))
                        if parse_verdict(raw or "", LEGACY_STRICT_XML).status is ScoreStatus.VALID:
                            break
                    if not attempts:
                        unresolved = "no monitor call available to pair"
                    res = aggregate(attempts, HISTORICAL_V1)
                    rec_value, rec_status = res.value, res.status.value

                # Fail-closed check: does the legacy reparse reproduce what the live run stored?
                legacy_vals = [
                    parse_verdict(a.raw_response or "", LEGACY_STRICT_XML) for a in attempts
                ]
                legacy_valid = [v.value for v in legacy_vals if v.status is ScoreStatus.VALID]
                legacy_value = legacy_valid[-1] if legacy_valid else None
                if nlines:
                    agrees = (legacy_value == stored) if stored is not None else (legacy_value is None)
                    if not agrees:
                        unresolved = (
                            f"pairing unverified: legacy reparse {legacy_value} != stored {stored}"
                        )
                else:
                    agrees = None

                if unresolved:
                    stats["unresolved"] += 1
                elif nlines:
                    stats["paired"] += 1

                ntok_in = sum(a.input_tokens for a in attempts)
                ntok_out = sum(a.output_tokens for a in attempts)
                mrecs.append(MonitorRecord(
                    schema_version=SCHEMA_VERSION, run_id=run_id, campaign_id=str(s.id),
                    event_id=f"{s.id}/{i}/{view}", commit_index=i,
                    monitor_input=MonitorInput(
                        view=view, diff_hash=content_hash(c.get("diff")),
                        diff_lines=nlines or 0,
                        task_description_hash=content_hash(c.get("main_task_name")),
                        diff_ref=f"{Path(path).name}#{s.id}/commit{i}/{view}",
                    ),
                    labels=EvaluatorLabels(
                        is_attacker_commit=bool(c.get("is_attacker")),
                        condition=md.get("condition", "?"), side_task_name=side,
                        main_task_name=c.get("main_task_name", "?"),
                        fragment_delivered=c.get("fragment_delivered"),
                        fragment_retried=c.get("fragment_retried"),
                    ),
                    value=rec_value, status=rec_status,
                    n_attempts=len(attempts),
                    n_valid=sum(1 for a in attempts if a.verdict.status is ScoreStatus.VALID),
                    spread=aggregate(attempts, HISTORICAL_V1).spread if attempts else None,
                    input_tokens=ntok_in, output_tokens=ntok_out,
                    cost_usd=ntok_in * FLASH_LITE_IN + ntok_out * FLASH_LITE_OUT,
                    attempts=[a.to_dict() for a in attempts],
                    legacy_value=legacy_value, legacy_agrees=agrees,
                    unresolved_reason=unresolved,
                ))

        crecs.append(CampaignRecord(
            schema_version=SCHEMA_VERSION, run_id=run_id, campaign_id=str(s.id),
            condition=md.get("condition", "?"), k_agents=md.get("n_agents", len(commits)),
            side_task_name=side,
            side_task_success=bool(tr.get(side)) if side else None,
            main_tasks={m: bool(tr.get(m)) for m in mains},
            n_commits=len(commits),
            fragments_delivered=sum(1 for c in commits if c.get("fragment_delivered")) or None,
            fragments_retried=sum(1 for c in commits if c.get("fragment_retried")) or None,
            agent_limit_hits=sum(1 for c in commits if c.get("limit_hit")),
            agent_timeouts=sum(1 for c in commits if c.get("timed_out")),
        ))

    store.write_monitor(mrecs)
    store.write_campaigns(crecs)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--provenance", default="historical",
                    choices=["historical", "exploratory", "confirmatory"])
    ap.add_argument("--protocol-version", required=True)
    ap.add_argument("--out-root", default="results")
    ap.add_argument("--code-commit", default=None)
    ap.add_argument("--allow-existing", action="store_true")
    a = ap.parse_args()
    stats = import_log(a.log, a.run_id, a.provenance, a.protocol_version,
                       a.out_root, a.code_commit, a.allow_existing)
    print(f"{a.run_id}: {stats}")


if __name__ == "__main__":
    main()
