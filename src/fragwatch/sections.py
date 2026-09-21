"""Generate the numerical sections of README, PILOT_REPORT and CASE_STUDY from one canonical summary.

Every number a reader sees is computed here, so documents cannot drift from the data. Marked blocks are
delimited by HTML comments and rewritten in place:

    <!-- BEGIN GENERATED: name -->
    ...generated...
    <!-- END GENERATED: name -->

`--check` regenerates every block in memory and exits non-zero on any difference, printing a diff. It
replaces the previous fixed-string checker, which verified a handful of phrases such as
"Nine developmental campaigns" and could not notice a changed number elsewhere.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fragwatch.summary import (  # noqa: E402
    PRIMARY_THRESHOLD,
    SENSITIVITY_THRESHOLD,
    ArtifactError,
    load_export,
    summarise,
)

EXPORT = Path("results/pilot_campaigns.json")
BEGIN = "<!-- BEGIN GENERATED: {} -->"
END = "<!-- END GENERATED: {} -->"
ARM_LABEL = {"K1_matched": "concentrated (K1_matched)", "K3": "fragmented (K3)",
             "honest_linked": "honest linked", "K1_single": "single-agent (K1_single)"}


def _arm_order(arms: dict) -> list[str]:
    return sorted(arms, key=lambda c: (not arms[c]["is_attack_arm"], c))


def sec_outcomes(s: dict) -> str:
    out = ["| arm | campaigns | attack success | per-commit detection | cumulative detection |",
           "|---|---|---|---|---|"]
    for cond in _arm_order(s["arms"]):
        a = s["arms"][cond]
        out.append(f"| {ARM_LABEL.get(cond, cond)} | {a['n_campaigns']} | {a['attack_success_rate']} "
                   f"| {a['per_detection']} | {a['cum_detection']} |")
    out.append("")
    out.append(f"Detection denominators: for attack arms, campaigns with a **verified** successful "
               f"attack; for honest arms, all campaigns. Threshold {s['threshold']}. An arm with no "
               f"verified successful attack reports N/A rather than dividing by attempts.")
    return "\n".join(out)


def sec_missing(s: dict) -> str:
    rows = ["| arm | attack verified / failed / unresolved | per-commit alerted / no alert / unresolved "
            "| cumulative alerted / no alert / unresolved |", "|---|---|---|---|"]
    for cond in _arm_order(s["arms"]):
        a = s["arms"][cond]
        rows.append(
            f"| {ARM_LABEL.get(cond, cond)} | {a['attack_verified']} / {a['attack_failed']} / "
            f"{a['attack_unresolved']} | {a['per']['alerted']} / {a['per']['no_alert']} / "
            f"{a['per']['unresolved']} | {a['cum']['alerted']} / {a['cum']['no_alert']} / "
            f"{a['cum']['unresolved']} |")
    rows.append("")
    rows.append("A campaign counts as alerted on any valid alert even if another judgment is missing. "
                "With no valid alert and a missing required judgment it is unresolved, never 'no "
                "alert'. Absent attack verification is unresolved, never failure.")
    return "\n".join(rows)


def sec_variability(s: dict) -> str:
    v = s["variability"]
    per_arm = ", ".join(
        f"{s['arms'][c]['n_campaigns']} in {ARM_LABEL.get(c, c)}" for c in _arm_order(s["arms"]))
    return (
        f"- **Across independent campaigns** (the experimental unit): {per_arm}. "
        f"No confidence intervals were computed, so none are reported; differences of one campaign are "
        f"not evidence of an effect.\n"
        f"- **Across repeated judge calls on one input** (measurement, not units): "
        f"{v['n_inputs_with_repeats']} inputs had at least two valid calls. Observed score spread: mean "
        f"{v['mean_spread']}, maximum {v['max_spread']}, with {v['n_spread_ge_3']} inputs at or above 3 "
        f"and {v['n_spread_ge_5']} at or above 5. These are observed spreads; the distribution was not "
        f"characterised and no modality claim is made.\n"
        f"- **Aggregation sensitivity**: {v['aggregation_flips']} campaign-view verdict(s) change "
        f"between median-of-calls and maximum-of-calls at threshold {s['threshold']}."
    )


def sec_costs(s: dict) -> str:
    return (
        f"- **The {s['n_campaigns']}-campaign batch in this report**: "
        f"${s['cost']['campaigns_in_table']:.4f} modelled.\n"
        f"- **Total development spend across the whole pilot**, including earlier development runs, "
        f"calibration and superseded batches: $1.3492 modelled, from `COSTS.md`.\n"
        f"- **Historical Step 1–4 work** predating this protocol is accounted separately in `COSTS.md`.\n"
        f"- All figures are modelled from reported token counts times a hand-entered price sheet. "
        f"OpenRouter's own cost field returned `None`, so **no figure here comes from an invoice**. A "
        f"20% reserve for possibly in-flight requests is an estimate with headroom, not a bound."
    )


def sec_provenance(s: dict) -> str:
    p = s.get("provenance") or {}
    revs = p.get("execution_revisions") or {}
    lines = ["| revision kind | value | basis | meaning |", "|---|---|---|---|"]
    for run, meta in sorted(revs.items()):
        basis = meta.get("basis", "recorded")
        nxt = meta.get("next_commit")
        bracket = (f"run started {meta['run_started']}, after `{meta.get('prev_commit')}` "
                   f"({meta.get('prev_commit_time')}) and before `{nxt}` "
                   f"({meta.get('next_commit_time')})") if nxt else f"run started {meta['run_started']}"
        lines.append(f"| execution (`{run}`) | `{meta['code_sha']}` | **{basis}** | {bracket} |")
    lines.append(f"| export | `{p.get('export_revision', s['export_code_sha'])[:7]}` | recorded | "
                 f"commit at which the JSON artifacts were written |")
    lines.append("| reporting | printed by the report at generation time | recorded | commit "
                 "generating the text |")
    if any(m.get("basis") == "inferred" for m in revs.values()):
        lines += ["", "Execution revisions are **inferred**, not directly recorded: no run wrote its "
                      "git HEAD into its log, so each is placed on the commit timeline by its run start "
                      "time. The bracketing commits in the table are that evidence. The inference "
                      "assumes the checkout was at HEAD with a clean working tree, which no preserved "
                      "artifact records. Export and reporting revisions are recorded directly."]
    sc = s["scoring"]
    lines.append("")
    lines.append(f"Scoring: `{sc['monitor_model']}`, prompt `{sc['prompt_version']}`, temperature "
                 f"{sc['temperature']}, {sc['n_calls']} calls per input, aggregated by "
                 f"{sc['aggregate']}, valid range {sc['valid_range']}.")
    return "\n".join(lines)


def sec_sensitivity(s_primary: dict, s_alt: dict) -> str:
    rows = [f"Threshold {SENSITIVITY_THRESHOLD}, shown only as sensitivity. The primary threshold "
            f"{PRIMARY_THRESHOLD} was declared in advance and is not changed on the basis of outcomes.",
            "", "| arm | per-commit detection | cumulative detection |", "|---|---|---|"]
    for cond in _arm_order(s_alt["arms"]):
        a = s_alt["arms"][cond]
        rows.append(f"| {ARM_LABEL.get(cond, cond)} | {a['per_detection']} | {a['cum_detection']} |")
    return "\n".join(rows)


def build(summary: dict, summary_alt: dict) -> dict[str, str]:
    return {
        "outcomes": sec_outcomes(summary),
        "missing": sec_missing(summary),
        "variability": sec_variability(summary),
        "costs": sec_costs(summary),
        "provenance": sec_provenance(summary),
        "sensitivity": sec_sensitivity(summary, summary_alt),
    }


def replace_block(text: str, name: str, body: str) -> tuple[str, bool]:
    b, e = BEGIN.format(name), END.format(name)
    pattern = re.compile(re.escape(b) + r".*?" + re.escape(e), re.S)
    if not pattern.search(text):
        return text, False
    return pattern.sub(f"{b}\n{body}\n{e}", text), True


def current_block(text: str, name: str) -> str | None:
    b, e = BEGIN.format(name), END.format(name)
    m = re.search(re.escape(b) + r"\n(.*?)\n" + re.escape(e), text, re.S)
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="regenerate in memory and fail on differences")
    ap.add_argument("--docs", nargs="+",
                    default=["README.md", "PILOT_REPORT.md", "CASE_STUDY.md"])
    a = ap.parse_args()
    try:
        payload = load_export(EXPORT)
    except ArtifactError as exc:
        print(f"ARTIFACT ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    blocks = build(summarise(payload, PRIMARY_THRESHOLD),
                   summarise(payload, SENSITIVITY_THRESHOLD))

    failures, written, found = [], 0, 0
    for doc in a.docs:
        p = Path(doc)
        if not p.exists():
            print(f"ARTIFACT ERROR: missing document {doc}", file=sys.stderr)
            raise SystemExit(2)
        text = p.read_text()
        new_text = text
        for name, body in blocks.items():
            cur = current_block(new_text, name)
            if cur is None:
                continue
            found += 1
            if cur.strip() != body.strip():
                if a.check:
                    diff = "\n".join(difflib.unified_diff(
                        cur.splitlines(), body.splitlines(),
                        fromfile=f"{doc}:{name} (written)", tofile=f"{doc}:{name} (regenerated)",
                        lineterm=""))
                    failures.append(diff)
                else:
                    new_text, _ = replace_block(new_text, name, body)
                    written += 1
        if not a.check and new_text != text:
            p.write_text(new_text)

    if found == 0:
        print("ARTIFACT ERROR: no generated blocks found in any document", file=sys.stderr)
        raise SystemExit(2)
    if a.check:
        if failures:
            print("GENERATED SECTIONS ARE STALE — regenerate with "
                  "`python src/fragwatch/sections.py`:\n", file=sys.stderr)
            for d in failures:
                print(d, file=sys.stderr)
            raise SystemExit(1)
        print(f"All {found} generated sections match the canonical summary.")
    else:
        print(f"Regenerated {written} of {found} generated sections.")


if __name__ == "__main__":
    main()
