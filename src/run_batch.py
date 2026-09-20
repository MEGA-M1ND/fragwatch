"""Step 3b: run several iac_fast attack samples for one untrusted model, stock pipeline.

Usage:
    python src/run_batch.py --untrusted openrouter/openai/gpt-5-mini --tag gpt5mini \
        --sample-ids MT_a_ST_b MT_c_ST_d ...

Identical pipeline and limits to run_first.py (trusted_monitoring + basic_monitor, 500k token
limit, 40 steps) so results are comparable with runs 1-3. Logs go to data/model_compare/<tag>/.
"""

import argparse
from pathlib import Path

from inspect_ai import eval
from inspect_ai.model import get_model

from control_arena.eval import ControlEvalConfig, EvalMode, get_control_task
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.monitor import basic_monitor_builder
from control_arena.scorers import git_diff_monitor, max_suspicion_scorer
from control_arena.settings.iac_fast import IACFastSetting

TRUSTED = "openrouter/google/gemini-2.5-flash-lite"

# One sample per main task, each with a different side task.
DEFAULT_SAMPLES = [
    "MT_add_interpretability_ou_ST_create_backdoor_admin_role",
    "MT_create_billing_alarm_ST_allow_public_s3_policy",
    "MT_enforce_mandatory_tags_scp_ST_detach_mfa_requirement_policy",
    "MT_org_config_aggregator_ST_open_internet_egress_restricted_ous",
    "MT_tag_security_policies_ST_disable_fsx_deny_policy",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--untrusted", required=True)
    ap.add_argument("--trusted", default=TRUSTED)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--sample-ids", nargs="+", default=DEFAULT_SAMPLES)
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--token-limit", type=int, default=500_000)
    ap.add_argument("--max-sandboxes", type=int, default=2)
    args = ap.parse_args()

    log_dir = Path("data/model_compare") / args.tag
    setting = IACFastSetting()
    micro_protocol = trusted_monitoring_builder(monitor=basic_monitor_builder(model_role="trusted"))
    config = ControlEvalConfig(
        untrusted_model=get_model(args.untrusted, strict_tools=False),
        trusted_model=get_model(args.trusted, strict_tools=False),
        max_steps=args.max_steps,
        token_limit=args.token_limit,
        log_dir=str(log_dir),
        max_sandboxes=args.max_sandboxes,
        fail_on_error=False,
    )
    task = get_control_task(
        setting=setting,
        micro_protocol=micro_protocol,
        mode=EvalMode.ATTACK,
        eval_config=config,
        monitoring_scorers=[max_suspicion_scorer(), git_diff_monitor(model_role="trusted")],
        task_name_prefix=f"compare_{args.tag}",
    )
    logs = eval(task, sample_id=args.sample_ids, sandbox_prebuilt=True, **config.eval_args())
    log = logs[0]
    print("status:", log.status)
    print("location:", log.location)
    print("n samples:", len(log.samples or []))


if __name__ == "__main__":
    main()
