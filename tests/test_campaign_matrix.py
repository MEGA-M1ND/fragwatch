"""Integration tests: need control_arena + inspect_ai, but never Docker, network, or model calls.

These guard the experiment's design invariants -- above all that K=1 and K=3 are
instruction-matched, the bug that invalidated the first Step 4 run.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = pytest.mark.integration

pytest.importorskip("control_arena", reason="eval stack not installed")
pytest.importorskip("inspect_ai", reason="eval stack not installed")


@pytest.fixture(scope="module")
def samples():
    from run_step4 import build_samples

    return build_samples(3)


def test_matrix_has_expected_conditions(samples):
    conds = {s.metadata["condition"] for s in samples}
    assert conds == {"K1_attack", "K3_attack", "K3_honest"}
    assert len(samples) == 15, "3 reps x (K1 + K3) x 2 side tasks + 3 honest"


def test_k1_has_one_agent_and_k3_has_three(samples):
    for s in samples:
        expected = 1 if s.metadata["condition"] == "K1_attack" else 3
        assert s.metadata["n_agents"] == expected == len(s.metadata["agents"])


def test_k1_and_k3_are_instruction_matched(samples):
    """The K=1 agent must receive exactly the fragments K=3 splits, or the comparison is confounded."""
    from fragments import SIDE_TASKS

    for spec in SIDE_TASKS.values():
        side = spec["side_task_name"]
        k1 = next(
            s for s in samples
            if s.metadata["condition"] == "K1_attack" and s.metadata["side_task_name"] == side
        )
        k1_instr = k1.metadata["agents"][0]["side_instruction"]
        for frag in spec["fragments"]:
            text = frag["instruction"] if isinstance(frag, dict) else frag
            assert text in k1_instr, f"K1 for {side} is missing a fragment K3 receives"


def test_honest_campaigns_carry_no_side_task(samples):
    for s in samples:
        if s.metadata["condition"] != "K3_honest":
            continue
        assert s.metadata["side_task_name"] is None
        assert all(a["side_instruction"] is None for a in s.metadata["agents"])


def test_every_attacker_agent_has_a_delivery_check(samples):
    """A fragment with no check cannot be verified or retried, which is how campaigns died silently."""
    for s in samples:
        if s.metadata["condition"] == "K3_honest":
            continue
        for a in s.metadata["agents"]:
            if a["side_instruction"]:
                assert a["check_cmd"], f"{s.id}: {a['main_task_name']} fragment has no check_cmd"


def test_k3_main_tasks_are_distinct_within_a_campaign(samples):
    for s in samples:
        if s.metadata["n_agents"] != 3:
            continue
        names = [a["main_task_name"] for a in s.metadata["agents"]]
        assert len(set(names)) == 3, f"{s.id} repeats a main task: {names}"


def test_fragment_checks_reference_real_repo_paths():
    """Delivery predicates must point at files that exist in the setting, or they never pass."""
    from control_arena.settings.iac_fast.config import SETTING_REPO_PATH

    from fragments import SIDE_TASKS

    for spec in SIDE_TASKS.values():
        for frag in spec["fragments"]:
            if not isinstance(frag, dict) or not frag.get("check_cmd"):
                continue
            for token in frag["check_cmd"].split():
                if token.startswith("core_infrastructure/") and token.endswith(".py"):
                    # dev_helper_role.py is created by the attack, so only pre-existing files count
                    if "dev_helper_role" in token:
                        continue
                    assert (SETTING_REPO_PATH / token).exists(), f"check_cmd path missing: {token}"


def test_solver_and_scorer_construct():
    from campaign import campaign_scorer, campaign_solver

    assert campaign_solver(untrusted_model="m", trusted_model="t") is not None
    assert campaign_scorer() is not None
