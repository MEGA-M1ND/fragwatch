"""Print the per-campaign results table from archived JSON. Standard library only.

Arm-level rates come from `summary.py`, the single canonical computation shared with the generated
document sections, so the table and the documents cannot disagree. The previous implementation used
`den = landed if landed else g`, which silently changed the denominator when nothing was verified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fragwatch.sections import build  # noqa: E402
from fragwatch.summary import (  # noqa: E402
    PRIMARY_THRESHOLD,
    SENSITIVITY_THRESHOLD,
    ArtifactError,
    load_export,
    summarise,
)


def _yn(v) -> str:
    return "-" if v is None else ("yes" if v is True else ("no" if v is False else str(v)))


def emit(payload: dict) -> dict:
    summary = summarise(payload, PRIMARY_THRESHOLD)
    alt = summarise(payload, SENSITIVITY_THRESHOLD)
    blocks = build(summary, alt)

    print("## Developmental pilot — all campaigns\n")
    print(blocks["provenance"])
    print(f"\nPrimary threshold **{PRIMARY_THRESHOLD}** (PROTOCOL.md Amendment A1).\n")

    hdr = ["arm", "campaign", "constructed", "attack verified", "per-commit scores",
           "cumulative scores", "per outcome", "cum outcome", "missing per/cum", "main tasks",
           "cost USD"]
    print("| " + " | ".join(hdr) + " |")
    print("|" + "---|" * len(hdr))
    by_id = {c["campaign"]: c for c in summary["campaigns"]}
    for c in payload["campaigns"]:
        row = by_id[c["campaign"]]
        checks = [x for x in c["commits"] if x["fragment_delivered"] is not None]
        constructed = (f"{sum(1 for x in checks if x['fragment_delivered'])}/{len(checks)}"
                       if checks else "n/a")
        per = [("-" if x["per"]["value"] is None else f"{x['per']['value']:.1f}")
               for x in c["commits"]]
        cum = [("-" if x["cum"]["value"] is None else f"{x['cum']['value']:.1f}")
               for x in c["commits"]]
        mains = c["main_tasks"]
        print(f"| {c['condition']} | {c['campaign']} | {constructed} | "
              f"{_yn(row['attack_verified'])} | {per} | {cum} | {row['per']['outcome']} | "
              f"{row['cum']['outcome']} | {row['per']['n_missing']}/{row['cum']['n_missing']} | "
              f"{sum(1 for v in mains.values() if v)}/{len(mains)} | {c['cost_usd']:.4f} |")

    for title, key in (("Outcomes and detection denominators", "outcomes"),
                       ("Missing and unresolved outcomes", "missing"),
                       ("Two kinds of variation", "variability"),
                       ("Sensitivity analysis", "sensitivity"),
                       ("Cost", "costs")):
        print(f"\n### {title}\n")
        print(blocks[key])
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", default="results/pilot_campaigns.json")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    try:
        payload = load_export(Path(a.artifact))
    except ArtifactError as exc:
        print(f"ARTIFACT ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    summary = emit(payload)
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(summary, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
