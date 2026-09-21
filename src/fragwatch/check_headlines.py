"""Assert that every numeric headline in README.md and PILOT_REPORT.md matches regenerated values.

Standard library only. Fails loudly, naming the claim and both values, so a stale document cannot pass
review. Run as part of `scripts/verify_release.sh`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fragwatch.pilot_report import (  # noqa: E402
    PRIMARY_THRESHOLD,
    ArtifactError,
    load,
    summarise,
)

ARTIFACT = Path("results/pilot_campaigns.json")
DOCS = [Path("README.md"), Path("PILOT_REPORT.md")]


def regenerate() -> dict:
    payload = load(ARTIFACT)
    summ = summarise(payload)
    arms: dict[str, list] = {}
    for k in summ.values():
        arms.setdefault(k["condition"], []).append(k)
    out = {"n_campaigns": len(summ), "arms": {}}
    for cond, g in arms.items():
        landed = [x for x in g if x["landed"]]
        den = landed if landed else g
        out["arms"][cond] = {
            "n": len(g),
            "landed": len(landed),
            "per": f"{sum(1 for x in den if x['per_max'] and x['per_max'] >= PRIMARY_THRESHOLD)}/{len(den)}",
            "cum": f"{sum(1 for x in den if x['cum_max'] and x['cum_max'] >= PRIMARY_THRESHOLD)}/{len(den)}",
        }
    out["total_attacks_landed"] = sum(v["landed"] for v in out["arms"].values())
    out["campaign_cost"] = round(sum(c["cost_usd"] for c in payload["campaigns"]), 4)
    out["honest_commits"] = sum(
        len(c["commits"]) for c in payload["campaigns"] if c["condition"] == "honest_linked")
    out["honest_campaigns"] = sum(
        1 for c in payload["campaigns"] if c["condition"] == "honest_linked")
    out["honest_agents_per_campaign"] = sorted({
        c["n_agents"] for c in payload["campaigns"] if c["condition"] == "honest_linked"})
    return out


def main() -> None:
    try:
        vals = regenerate()
    except ArtifactError as exc:
        print(f"ARTIFACT ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    text = {p.name: p.read_text() for p in DOCS if p.exists()}
    missing_docs = [p.name for p in DOCS if not p.exists()]
    if missing_docs:
        print(f"ARTIFACT ERROR: missing documents {missing_docs}", file=sys.stderr)
        raise SystemExit(2)

    a = vals["arms"]
    checks = [
        ("9 developmental campaigns", "Nine developmental campaigns", "README.md"),
        (f"attacks landed {vals['total_attacks_landed']}/6", "6/6", "README.md"),
        (f"concentrated per-commit {a['K1_matched']['per']}",
         f"{a['K1_matched']['per']} concentrated", "README.md"),
        (f"fragmented per-commit {a['K3']['per']}", f"{a['K3']['per']} fragmented", "README.md"),
        (f"honest per-commit {a['honest_linked']['per']}",
         f"{a['honest_linked']['per']} honest", "README.md"),
        (f"cumulative triple {a['K1_matched']['cum']}, {a['K3']['cum']}, {a['honest_linked']['cum']}",
         f"{a['K1_matched']['cum']}, {a['K3']['cum']}, {a['honest_linked']['cum']}", "README.md"),
        (f"campaign cost ${vals['campaign_cost']}", f"${vals['campaign_cost']}", "PILOT_REPORT.md"),
        (f"honest campaigns {vals['honest_campaigns']}", "three honest", "PILOT_REPORT.md"),
    ]
    failures = []
    for label, needle, doc in checks:
        if needle.lower() not in text[doc].lower():
            failures.append(f"{doc}: expected to find {needle!r} for [{label}]")
        else:
            print(f"  OK   {doc:17} {label}")

    # table rows must match regenerated per-arm counts
    for cond, v in a.items():
        row = f"| {cond} | {v['n']} | {v['landed']} | {v['per']} | {v['cum']} |"
        if row not in text["PILOT_REPORT.md"]:
            failures.append(f"PILOT_REPORT.md: arm row mismatch, expected {row!r}")
        else:
            print(f"  OK   PILOT_REPORT.md   arm row {cond}")

    print(f"\nregenerated: {json.dumps(vals['arms'], sort_keys=True)}")
    if failures:
        print("\nHEADLINE MISMATCH — documents disagree with regenerated values:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        raise SystemExit(1)
    print(f"\nAll {len(checks) + len(a)} headline checks agree with regenerated values.")


if __name__ == "__main__":
    main()
