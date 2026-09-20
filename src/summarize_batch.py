"""Print a per-sample table for one or more .eval logs (steps, outcome, scores, tokens)."""

import sys

from inspect_ai.log import read_eval_log


def row(log, s):
    n_steps = sum(1 for m in s.messages if m.role == "assistant")
    ended = "limit" if s.limit else "submit"
    sc = s.scores or {}
    py = sc.get("combined_pytest_scorer")
    mt = py.value.get("main_task_success") if py and isinstance(py.value, dict) else "?"
    st = py.value.get("side_task_success") if py and isinstance(py.value, dict) else "?"
    ms = sc.get("max_suspicion_scorer")
    dm = sc.get("git_diff_monitor")
    steps = []
    for m in s.messages:
        if m.role == "assistant" and m.metadata and "suspicion_score" in m.metadata:
            steps.append(m.metadata["suspicion_score"])
    hot = sum(1 for x in steps if x is not None and x >= 0.3)
    u = s.model_usage or {}
    unt = [v for k, v in u.items() if "flash" not in k]
    tu = unt[0] if unt else None
    diff = (s.store or {}).get("submission_diff") or ""
    return (
        s.id.replace("MT_", "").replace("_ST_", " / "),
        n_steps, ended, mt, st,
        f"{ms.value:.1f}" if ms and isinstance(ms.value, (int, float)) else "-",
        f"{dm.value:.0f}" if dm and isinstance(dm.value, (int, float)) else ("ERR" if s.error else "-"),
        hot,
        f"{tu.input_tokens:,}/{(tu.input_tokens_cache_read or 0):,}/{tu.output_tokens:,}" if tu else "-",
        len(diff.splitlines()),
    )


def main() -> None:
    hdr = ("sample", "steps", "ended", "main", "side", "maxsusp", "diffmon", "steps>=0.3", "in/cached/out", "difflines")
    for path in sys.argv[1:]:
        log = read_eval_log(path)
        print(f"\n## {path}  status={log.status}")
        print("| " + " | ".join(hdr) + " |")
        print("|" + "---|" * len(hdr))
        for s in log.samples or []:
            print("| " + " | ".join(str(x) for x in row(log, s)) + " |")
        mu = log.stats.model_usage if log.stats else {}
        for k, v in mu.items():
            print(f"usage {k}: in={v.input_tokens:,} cached={(v.input_tokens_cache_read or 0):,} out={v.output_tokens:,} reasoning={(v.reasoning_tokens or 0):,}")


if __name__ == "__main__":
    main()
