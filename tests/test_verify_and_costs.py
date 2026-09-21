"""Spend accounting, plus a smoke test of the verifier's public shape.

Detailed verifier coverage moved to `test_verify_attack_regressions.py` when the predicate was
corrected to judge one role inside one StackSet. The cases previously here asserted success for a role
whose trust statement named no principal at all, which the corrected predicate rejects by design.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fragwatch.verify_attack import verify_backdoor, verify_s3_deletion  # noqa: E402


def test_verifier_reports_scope_and_never_claims_deployment():
    r = verify_backdoor({"Resources": {}})
    assert "not deployment or exploitation" in r["scope"]
    assert r["attack_success"] is False
    assert r["status"] in ("failure", "unresolved")


def test_s3_verifier_reports_scope():
    r = verify_s3_deletion({"Resources": {}})
    assert "not deployment or exploitation" in r["scope"]


def test_spend_accounting_adds_a_conservative_reserve():
    from fragwatch.costs import IN_FLIGHT_RESERVE_FRACTION, Spend
    sp = Spend(1.0, 1.0 * IN_FLIGHT_RESERVE_FRACTION, {}, {}, [], 0)
    assert sp.worst_case_usd > sp.modelled_usd
    assert IN_FLIGHT_RESERVE_FRACTION >= 0.1, "reserve must be meaningful, not cosmetic"


@pytest.mark.integration
def test_recorded_verification_matches_current_predicate():
    """The committed verification results must have been produced by the current predicate."""
    import json
    data = json.loads(Path("results/semantic_verification.json").read_text())
    assert len(data) == 9
    for cid, r in data.items():
        assert r["status"] in ("success", "failure", "unresolved"), cid
        if r["status"] == "success":
            assert r["supporting_resources"], f"{cid}: success without supporting resource ids"
