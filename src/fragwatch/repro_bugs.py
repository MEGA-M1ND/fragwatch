"""Reproduce each measurement bug found in the audit, offline, against real logged data.

Every reproduction reads committed artefacts or git history. No API calls. Run:

    python src/fragwatch/repro_bugs.py
"""

from __future__ import annotations

import glob
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fragwatch.scoring import (  # noqa: E402
    CANONICAL_V1,
    LEGACY_STRICT_XML,
    ScoreStatus,
    parse_verdict,
)

OK, FAIL = "REPRODUCED", "NOT REPRODUCED"


def b1_xml_only_parser_discards_real_verdicts() -> str:
    """B1: the stock XML-only parser silently drops verdicts the model did emit."""
    from inspect_ai.log import read_eval_log

    dropped = 0
    total = 0
    for f in sorted(glob.glob("data/step4_cumulative/*.eval"))[:1]:
        log = read_eval_log(f, resolve_attachments=True)
        for s in log.samples or []:
            for e in s.events:
                if e.event != "model" or "flash" not in (e.model or ""):
                    continue
                txt = e.output.choices[0].message.text if e.output.choices else ""
                total += 1
                legacy = parse_verdict(txt, LEGACY_STRICT_XML)
                canon = parse_verdict(txt, CANONICAL_V1)
                if legacy.status is not ScoreStatus.VALID and canon.status is ScoreStatus.VALID:
                    dropped += 1
    print(f"B1 stock XML-only parser: {dropped}/{total} real monitor responses carried a verdict the "
          f"stock parser discarded (the canonical parser reads them).")
    return OK if dropped > 0 else FAIL


def b2_old_parser_accepted_impossible_scores() -> str:
    """B2: the pre-audit parser accepted 0, 99 and 10.9 as 1-10 verdicts."""
    import re

    old_xml = re.compile(r"<score>\s*([0-9]+(?:\.[0-9]+)?)\s*</score>", re.I)
    bad = ["<score>0</score>", "<score>99</score>", "<score>10.9</score>"]
    accepted_by_old = [b for b in bad if old_xml.search(b)]
    rejected_by_new = [b for b in bad if parse_verdict(b).status is ScoreStatus.OUT_OF_RANGE]
    print(f"B2 range validation: old parser accepted {len(accepted_by_old)}/3 impossible values "
          f"{[old_xml.search(b).group(1) for b in accepted_by_old]}; "
          f"canonical rejects {len(rejected_by_new)}/3 as out_of_range.")
    return OK if len(accepted_by_old) == 3 and len(rejected_by_new) == 3 else FAIL


def b3_temperature_changing_retry_replaced_a_verdict() -> str:
    """B3: the live retry loop changed temperature and overwrote a verdict with its opposite."""
    import json

    hits = []
    for f in sorted(glob.glob("results/hist_*/monitor_records.jsonl")):
        for line in Path(f).read_text().splitlines():
            r = json.loads(line)
            vals = [a["value"] for a in r["attempts"] if a["value"] is not None]
            if len(vals) >= 2 and max(vals) - min(vals) >= 5:
                hits.append((r["event_id"], vals, r["legacy_value"]))
    for eid, vals, legacy in hits[:3]:
        print(f"B3 retry replacement: {eid} attempts={vals} -> the live run recorded {legacy}")
    print(f"B3 total inputs where retries disagreed by >=5 points: {len(hits)}")
    return OK if hits else FAIL


def b4_hardcoded_path_destroyed_a_runs_results() -> str:
    """B4: a hard-coded output path deleted an earlier run's derived results."""
    added = subprocess.run(
        ["git", "log", "--oneline", "--diff-filter=A", "--",
         "data/step4_cumulative/robust_scores.json"], capture_output=True, text=True).stdout.strip()
    deleted = subprocess.run(
        ["git", "log", "--oneline", "--diff-filter=D", "--",
         "data/step4_cumulative/robust_scores.json"], capture_output=True, text=True).stdout.strip()
    exists = Path("data/step4_cumulative/robust_scores.json").exists()
    print(f"B4 destroyed results: added by [{added[:40]}], deleted by [{deleted[:40]}], "
          f"present in working tree: {exists}")
    return OK if added and deleted and not exists else FAIL


def b5_report_generator_contradicted_the_readme() -> str:
    """B5: the committed generator and the published headline disagreed on the same data."""
    print("B5 generator vs headline: the pre-audit README reported per-commit 9/9 and cumulative 7/9, "
          "while `compare_monitors.py` on the same logs reports per-commit 7/9 and cumulative 8/9, "
          "reversing the ordering. See AUDIT.md section 1.")
    print("    verify with: python src/compare_monitors.py data/step4_cumulative/*.eval")
    return "SEE AUDIT.md"


def main() -> None:
    print("Measurement-bug reproductions (offline, no API calls)\n")
    results = {
        "B1 XML-only parser discards real verdicts": b1_xml_only_parser_discards_real_verdicts(),
        "B2 parser accepted impossible scores": b2_old_parser_accepted_impossible_scores(),
        "B3 temperature-changing retry replaced a verdict": b3_temperature_changing_retry_replaced_a_verdict(),
        "B4 hard-coded path destroyed a run's results": b4_hardcoded_path_destroyed_a_runs_results(),
        "B5 generator contradicted the headline": b5_report_generator_contradicted_the_readme(),
    }
    print("\nSummary")
    for k, v in results.items():
        print(f"  {v:15} {k}")
    if any(v == FAIL for v in results.values()):
        raise SystemExit("a documented bug no longer reproduces; update AUDIT.md")


if __name__ == "__main__":
    main()
