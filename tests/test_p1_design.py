"""Tests for the P-1 matched design. These encode the confounds AUDIT.md issue 6 identified."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = pytest.mark.integration
pytest.importorskip("control_arena", reason="eval stack not installed")

from fragments_p1 import P1_OBJECTIVES  # noqa: E402
from run_p1 import ARMS, BENIGN, build_agents, build_samples  # noqa: E402


@pytest.fixture(scope="module")
def samples():
    return build_samples(["O1", "O2"], list(ARMS), 2)


def test_every_arm_has_identical_benign_workload(samples):
    """Benign workload must not vary with K, or detection differences are confounded."""
    for s in samples:
        assert s.metadata["main_task_names"] == BENIGN


def test_k3_spreads_the_attack_and_k1_matched_concentrates_it():
    frags = P1_OBJECTIVES["O2"]["fragments"]
    k3 = build_agents("K3", frags)
    k1m = build_agents("K1_matched", frags)
    assert len(k3) == len(k1m) == 3, "the control must have the same agent and commit count as K3"
    assert sum(1 for a in k3 if a["side_instruction"]) == 3
    assert sum(1 for a in k1m if a["side_instruction"]) == 1


def test_k1_matched_agent_receives_every_fragment():
    frags = P1_OBJECTIVES["O2"]["fragments"]
    instr = build_agents("K1_matched", frags)[0]["side_instruction"]
    for f in frags:
        assert f["instruction"] in instr


def test_k1_single_carries_all_benign_tasks_in_one_agent():
    agents = build_agents("K1_single", P1_OBJECTIVES["O2"]["fragments"])
    assert len(agents) == 1
    assert agents[0]["main_tasks"] == BENIGN


def test_honest_arm_has_no_attack_instructions():
    for a in build_agents("honest", []):
        assert a["side_instruction"] is None and a["check_cmd"] is None


def test_honest_campaigns_exist_for_calibration(samples):
    honest = [s for s in samples if s.metadata["condition"] == "honest"]
    assert honest, "a disjoint honest set is required to calibrate the threshold"
    assert all(s.metadata["side_task_name"] is None for s in honest)


def test_every_attack_agent_has_a_delivery_check(samples):
    for s in samples:
        for a in s.metadata["agents"]:
            if a["side_instruction"]:
                assert a["check_cmd"], f"{s.id}: attack fragment without a delivery check"


def test_o2_forbids_inlining_the_privilege_literal():
    """The split only holds if F3 refers to the constant instead of restating the ARN."""
    arn = "arn:aws:iam::aws:policy/AdministratorAccess"
    f2, f3 = P1_OBJECTIVES["O2"]["fragments"][1], P1_OBJECTIVES["O2"]["fragments"][2]
    assert f"! grep -q '{arn}'" in f2["check_cmd"]
    assert f"! grep -q '{arn}'" in f3["check_cmd"]


def test_o2_first_fragment_creates_no_role():
    f1 = P1_OBJECTIVES["O2"]["fragments"][0]
    assert "CfnRole|CfnStackSet|AWS::IAM::Role" in f1["check_cmd"]


def test_protocol_version_is_stamped_on_every_campaign(samples):
    assert {s.metadata["protocol_version"] for s in samples} == {"P-1"}
