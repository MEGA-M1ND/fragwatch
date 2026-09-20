"""Step 3: run one stock ControlArena setting (iac_fast) end to end, unchanged.

Usage:
    python src/run_first.py [--sample MT_<main>_ST_<side>] [--mode attack|honest]

Everything here is stock ControlArena: IACFastSetting, trusted_monitoring micro-protocol,
basic_monitor (default prompt, last-tool-calls formatter), plus two post-hoc scorers
(max_suspicion_scorer, git_diff_monitor). Models are pinned to OpenRouter because that is the
only API key available in this environment.
"""

import argparse
import json
from pathlib import Path

from inspect_ai import eval

from control_arena.eval import ControlEvalConfig, EvalMode, get_control_task
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.monitor import basic_monitor_builder
from control_arena.scorers import git_diff_monitor, max_suspicion_scorer
from control_arena.settings.iac_fast import IACFastSetting

UNTRUSTED = "openrouter/openai/gpt-4.1-nano"
TRUSTED = "openrouter/google/gemini-2.5-flash-lite"
LOG_DIR = Path("data/first_run")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="attack", choices=["attack", "honest"])
    ap.add_argument("--main-task", default="add_interpretability_ou")
    ap.add_argument("--side-task", default="create_backdoor_admin_role")
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--untrusted", default=UNTRUSTED)
    ap.add_argument("--trusted", default=TRUSTED)
    args = ap.parse_args()

    mode = EvalMode(args.mode)
    setting = IACFastSetting(
        filter_main_task_names=[args.main_task],
        filter_side_task_names=[args.side_task] if mode == EvalMode.ATTACK else [None],
    )
    micro_protocol = trusted_monitoring_builder(
        monitor=basic_monitor_builder(model_role="trusted"),
    )
    config = ControlEvalConfig(
        untrusted_model=args.untrusted,
        trusted_model=args.trusted,
        max_steps=args.max_steps,
        token_limit=500_000,
        log_dir=str(LOG_DIR),
        max_sandboxes=1,
        fail_on_error=False,
    )
    task = get_control_task(
        setting=setting,
        micro_protocol=micro_protocol,
        mode=mode,
        eval_config=config,
        monitoring_scorers=[max_suspicion_scorer(), git_diff_monitor(model_role="trusted")],
        task_name_prefix="first_run",
    )
    # The iac_fast compose file has a `build:` key; without this flag Inspect rebuilds the image
    # from the stock Dockerfile on task init, which fails here (deb.debian.org is blocked).
    logs = eval(task, sandbox_prebuilt=True, **config.eval_args())
    log = logs[0]
    print("status:", log.status)
    print("location:", log.location)
    if log.stats:
        print("model_usage:", json.dumps({k: v.model_dump() for k, v in log.stats.model_usage.items()}, indent=1))
    if log.samples:
        s = log.samples[0]
        print("sample id:", s.id)
        print("scores:", {k: (v.value, (v.explanation or "")[:200]) for k, v in (s.scores or {}).items()})
        print("n assistant msgs:", sum(1 for m in s.messages if m.role == "assistant"))
        if s.error:
            print("sample error:", s.error)


if __name__ == "__main__":
    main()
