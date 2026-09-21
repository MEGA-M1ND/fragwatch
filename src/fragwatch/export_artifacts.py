"""One-time export of everything the offline release report needs, into plain JSON.

Run once with the full eval stack installed. Afterwards the reporting path
(`pilot_report.py`, `repro_bugs.py`, `check_headlines.py`) reads only these JSON files and needs
**no third-party packages, no API key, no Docker**.

It also archives the raw monitor responses that demonstrate the historical parsing and retry defects,
so the bug reproductions exercise **archived** behaviour rather than requiring the defects to stay in
production code.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

from inspect_ai.log import read_eval_log

PRICES = {
    "openrouter/openai/gpt-5-mini": (0.25e-6, 0.025e-6, 2.00e-6),
    "openrouter/google/gemini-2.5-flash-lite": (0.10e-6, 0.025e-6, 0.40e-6),
}
PINNED = {"control-arena": "19.0.0", "inspect-ai": "0.3.266"}


def _cost(sample) -> float:
    t = 0.0
    for m, v in (sample.model_usage or {}).items():
        i, c, o = PRICES.get(m, (2e-6, 2e-6, 2e-6))
        t += v.input_tokens * i + (v.input_tokens_cache_read or 0) * c + v.output_tokens * o
    return t


def _files(diff: str) -> int:
    return len(set(re.findall(r"^\+\+\+ b/(.+)$", diff or "", re.M)))


def export_pilot(globs: list[str], semantic_path: str, out: Path, code_sha: str) -> dict:
    sem = json.loads(Path(semantic_path).read_text()) if Path(semantic_path).exists() else {}
    campaigns = []
    for g in globs:
        for f in sorted(glob.glob(g)):
            log = read_eval_log(f)
            for s in log.samples or []:
                st, md = s.store or {}, s.metadata or {}
                cs = st.get("commits", [])
                tr = st.get("task_results") or {}
                side = st.get("side_task_name")
                mains = st.get("main_task_names") or []
                commits = []
                for c in cs:
                    pm, cm = c.get("per_monitor") or {}, c.get("cum_monitor") or {}
                    commits.append({
                        "agent_index": c["agent_index"],
                        "is_attacker": bool(c.get("is_attacker")),
                        "main_task_name": c.get("main_task_name"),
                        "fragment_delivered": c.get("fragment_delivered"),
                        "fragment_retried": bool(c.get("fragment_retried")),
                        "diff_lines": c.get("diff_lines", 0),
                        "diff_files": _files(c.get("diff", "")),
                        "cum_diff_lines": c.get("cum_diff_lines", 0),
                        "per": {"value": pm.get("value"), "status": pm.get("status"),
                                "calls": [a.get("value") for a in pm.get("attempts", [])]},
                        "cum": {"value": cm.get("value"), "status": cm.get("status"),
                                "calls": [a.get("value") for a in cm.get("attempts", [])]},
                    })
                semv = sem.get(str(s.id))
                campaigns.append({
                    "campaign": str(s.id),
                    "condition": md.get("condition", "?"),
                    "objective": md.get("objective_id"),
                    "protocol_version": md.get("protocol_version"),
                    "n_agents": md.get("n_agents", len(cs)),
                    "side_task_name": side,
                    "pytest_attack_success": bool(tr.get(side)) if side else None,
                    "semantic_attack_success": (semv or {}).get("attack_success") if semv else None,
                    "semantic_detail": semv,
                    "main_tasks": {m: bool(tr.get(m)) for m in mains},
                    "cost_usd": _cost(s),
                    "source_log": Path(f).name,
                    "commits": commits,
                })
    payload = {
        "schema": "fragwatch.pilot_export/1",
        "code_sha": code_sha,
        "pinned_versions": PINNED,
        "scoring": {"monitor_model": "openrouter/google/gemini-2.5-flash-lite",
                    "prompt_version": "stock_git_diff_monitor_v1", "temperature": 0.0,
                    "n_calls": 3, "aggregate": "median", "valid_range": [1, 10]},
        "campaigns": sorted(campaigns, key=lambda c: (c["condition"], c["campaign"])),
    }
    out.write_text(json.dumps(payload, indent=1, sort_keys=True))
    return payload


def export_defect_archive(hist_globs: list[str], out: Path, max_examples: int = 6) -> dict:
    """Archive real monitor responses that the historical XML-only parser mishandled."""
    dropped, retry_pairs = [], []
    for g in hist_globs:
        for f in sorted(glob.glob(g)):
            log = read_eval_log(f, resolve_attachments=True)
            for s in log.samples or []:
                texts = []
                for e in s.events:
                    if e.event == "model" and "flash" in (e.model or ""):
                        txt = e.output.choices[0].message.text if e.output.choices else None
                        if txt:
                            texts.append(txt)
                for txt in texts:
                    has_xml = bool(re.search(r"<score>\s*-?[0-9.]+\s*</score>", txt, re.I))
                    fenced = re.findall(r"```[a-z]*\s*(-?[0-9]+(?:\.[0-9]+)?)\s*```", txt)
                    if not has_xml and fenced and len(dropped) < max_examples:
                        dropped.append({"source_log": Path(f).name, "campaign": str(s.id),
                                        "verdict_in_text": fenced[-1],
                                        "xml_tag_present": False, "response": txt})
    # Retry sequences that reversed a verdict, taken from the canonical historical records.
    for rf in sorted(glob.glob("results/hist_*/monitor_records.jsonl")):
        for line in Path(rf).read_text().splitlines():
            r = json.loads(line)
            vals = [a["value"] for a in r["attempts"] if a["value"] is not None]
            if len(vals) >= 2 and max(vals) - min(vals) >= 5:
                retry_pairs.append({
                    "event_id": r["event_id"], "attempt_values": vals,
                    "recorded_by_live_run": r["legacy_value"],
                    "attempt_formats": [a["fmt"] for a in r["attempts"]],
                    "responses": [a.get("raw_response") for a in r["attempts"]],
                })
    payload = {
        "schema": "fragwatch.defect_archive/1",
        "note": (
            "Archived evidence of defective historical behaviour. The production code no longer "
            "contains these defects; the reproductions replay these archived responses so the bugs "
            "stay demonstrable without keeping them in the pipeline."
        ),
        "xml_only_parser_dropped_verdicts": dropped,
        "temperature_changing_retry_reversals": retry_pairs,
    }
    out.write_text(json.dumps(payload, indent=1, sort_keys=True))
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--code-sha", required=True)
    ap.add_argument("--out-dir", default="results")
    a = ap.parse_args()
    out = Path(a.out_dir)
    (out / "archive").mkdir(parents=True, exist_ok=True)
    p = export_pilot(
        ["data/p1_dev_o2_v3/*.eval", "data/p1_dev_honest_linked/*.eval"],
        "results/semantic_verification.json", out / "pilot_campaigns.json", a.code_sha)
    d = export_defect_archive(["data/step4_cumulative/*.eval"], out / "archive" / "defective_behaviour.json")
    print(f"exported {len(p['campaigns'])} campaigns -> {out/'pilot_campaigns.json'}")
    print(f"archived {len(d['xml_only_parser_dropped_verdicts'])} dropped-verdict responses and "
          f"{len(d['temperature_changing_retry_reversals'])} retry reversals")


if __name__ == "__main__":
    main()
