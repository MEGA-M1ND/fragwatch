"""Guard the cost ledger: the cumulative column must actually be the running total.

The ledger is the only record of what the experiments cost, and it is maintained by hand across many
commits. A drifting cumulative column silently misreports spend, so CI checks the arithmetic.
"""

import re
from pathlib import Path

import pytest

COSTS = Path(__file__).resolve().parents[1] / "COSTS.md"


def ledger_rows():
    rows = []
    for line in COSTS.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 9 or not re.fullmatch(r"\d+", cells[0]):
            continue
        rows.append({"n": int(cells[0]), "what": cells[3],
                     "cost": float(cells[7]), "cum": float(cells[8])})
    return rows


def test_ledger_is_parseable_and_nonempty():
    rows = ledger_rows()
    assert len(rows) >= 10, f"expected the full ledger, parsed only {len(rows)} rows"


def test_ledger_ids_are_sequential():
    assert [r["n"] for r in ledger_rows()] == list(range(1, len(ledger_rows()) + 1))


def test_cumulative_column_matches_running_total():
    running = 0.0
    for r in ledger_rows():
        running += r["cost"]
        # rows are rounded to 3-4 dp by hand; allow a cent of accumulated rounding
        assert r["cum"] == pytest.approx(running, abs=0.011), (
            f"row {r['n']} ({r['what']}): cumulative {r['cum']} but running total is {running:.4f}"
        )


def test_costs_are_non_negative():
    """A negative cost means cached tokens were subtracted from input rather than added."""
    for r in ledger_rows():
        assert r["cost"] >= 0, f"row {r['n']} has negative cost {r['cost']}"
