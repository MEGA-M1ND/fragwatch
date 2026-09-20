"""Step 4 runner: build the campaign matrix and run it as one Inspect eval.

Conditions per side task: K1_attack (1 agent, whole side task) and K3_attack (3 agents, fragmented).
Plus a shared K3_honest baseline (3 agents, no side task) for the per-commit false-positive floor.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from inspect_ai import Task, eval  # noqa: E402

from campaign import build_campaign_samples, campaign_scorer, campaign_solver  # noqa: E402
from control_arena.settings.iac_fast import IACFastSetting  # noqa: E402
from fragments import SIDE_TASKS  # noqa: E402

UNTRUSTED = "openrouter/openai/gpt-5-mini"
TRUSTED = "openrouter/google/gemini-2.5-flash-lite"

# Main-task assignments. K3 uses three distinct main tasks; reps rotate the pool of 5.
K3_MAIN = [
    ["add_interpretability_ou", "create_billing_alarm", "tag_security_policies"],
    ["org_config_aggregator", "enforce_mandatory_tags_scp", "add_interpretability_ou"],
]
K1_MAIN = [["add_interpretability_ou"], ["create_billing_alarm"]]


def build_samples(n_reps: int):
    samples = []
    for key, spec in SIDE_TASKS.items():
        side = spec["side_task_name"]
        for rep in range(n_reps):
            # K1 attack: one agent, whole side task.
            samples += build_campaign_samples(
                side_task_name=side,
                fragments=[spec["whole"]],
                main_task_names=K1_MAIN[rep % len(K1_MAIN)],
                condition="K1_attack",
                n_reps=1,
            )
            # rename id to include rep index (build_campaign_samples uses rep0 internally)
            samples[-1].id = f"K1_attack_{side}_rep{rep}"
            # K3 attack: three agents, fragmented.
            samples += build_campaign_samples(
                side_task_name=side,
                fragments=spec["fragments"],
                main_task_names=K3_MAIN[rep % len(K3_MAIN)],
                condition="K3_attack",
                n_reps=1,
            )
            samples[-1].id = f"K3_attack_{side}_rep{rep}"
    # Shared honest baseline: K3, no side task.
    for rep in range(n_reps):
        samples += build_campaign_samples(
            side_task_name="create_backdoor_admin_role",  # ignored (honest)
            fragments=[],
            main_task_names=K3_MAIN[rep % len(K3_MAIN)],
            condition="K3_honest",
            n_reps=1,
            honest=True,
        )
        samples[-1].id = f"K3_honest_rep{rep}"
    return samples


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--untrusted", default=UNTRUSTED)
    ap.add_argument("--trusted", default=TRUSTED)
    ap.add_argument("--max-sandboxes", type=int, default=3)
    ap.add_argument("--only", default=None, help="substring filter on sample id (smoke tests)")
    ap.add_argument("--log-dir", default="data/step4")
    args = ap.parse_args()

    samples = build_samples(args.reps)
    if args.only:
        samples = [s for s in samples if args.only in s.id]
    print(f"{len(samples)} campaign samples:", [s.id for s in samples])

    task = Task(
        dataset=samples,
        solver=campaign_solver(untrusted_model=args.untrusted, trusted_model=args.trusted),
        scorer=campaign_scorer(),
        sandbox=IACFastSetting().get_sandbox_config(),
        name="step4_fragmentation",
    )
    logs = eval(
        task,
        sandbox_prebuilt=True,
        max_sandboxes=args.max_sandboxes,
        log_dir=args.log_dir,
        fail_on_error=False,
        retry_on_error=1,
    )
    log = logs[0]
    print("status:", log.status, "| location:", log.location)
    print("n samples:", len(log.samples or []))


if __name__ == "__main__":
    main()
