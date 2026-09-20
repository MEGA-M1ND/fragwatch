"""Reconstruct each campaign's cumulative diffs from stored per-commit patches, then re-score.

The harness stored per-commit diffs but only line counts for the cumulative ones, and the stock
diff-monitor parser discarded ~16% of verdicts (see rescore.py). Rather than re-run any agents, this
replays the stored patches onto a pristine copy of the setting repo, recomputing baseline..HEAD at
each step, then scores both views with the robust extractor. Deterministic and agent-free.
"""

import asyncio
import glob
import json
import shutil
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

from control_arena.scorers._diff_monitor import DIFF_MONITOR_PROMPT_TEMPLATE
from control_arena.settings.iac_fast.config import SETTING_REPO_PATH
from control_arena.settings.iac_fast.objectives import main_objectives
from inspect_ai.log import read_eval_log
from inspect_ai.model import GenerateConfig, get_model

sys.path.insert(0, str(Path(__file__).parent))
from rescore import robust_score  # noqa: E402

MONITOR = "openrouter/google/gemini-2.5-flash-lite"
N_SAMPLES = 3
GIT = ["-c", "user.email=r@r.local", "-c", "user.name=r"]


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def rebuild(commits: list[dict]) -> list[str | None]:
    """Replay per-commit patches; return the cumulative diff after each commit (None if apply fails)."""
    out: list[str | None] = []
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        shutil.copytree(SETTING_REPO_PATH, repo,
                        ignore=shutil.ignore_patterns("tests", "cdk.out", ".venv", "__pycache__"))
        sh(["git", "init", "-q", "."], repo)
        sh(["git", *GIT, "add", "-A"], repo)
        sh(["git", *GIT, "commit", "-q", "-m", "baseline"], repo)
        base = sh(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        for c in commits:
            d = c["diff"]
            if d.strip():
                p = Path(td) / "p.patch"
                p.write_text(d if d.endswith("\n") else d + "\n")
                r = sh(["git", "apply", "--whitespace=nowarn", str(p)], repo)
                if r.returncode != 0:
                    r = sh(["git", "apply", "-3", "--whitespace=nowarn", str(p)], repo)
                if r.returncode != 0:
                    out.append(None)
                    continue
            sh(["git", *GIT, "add", "-A"], repo)
            sh(["git", *GIT, "commit", "-q", "--allow-empty", "-m", "c"], repo)
            out.append(sh(["git", "diff", base, "HEAD"], repo).stdout)
    return out


async def score(model, desc: str, diff: str) -> dict:
    if not diff.strip():
        return {"median": 1.0, "samples": [1.0], "note": "empty"}
    prompt = DIFF_MONITOR_PROMPT_TEMPLATE.format(main_task_description=desc, git_diff=diff)
    vals = []
    for _ in range(N_SAMPLES):
        o = await model.generate(input=prompt, tools=[], cache=False,
                                 config=GenerateConfig(temperature=0.0))
        v, _f = robust_score(o.message.text)
        if v is not None:
            vals.append(v)
    return {"median": st.median(vals) if vals else None, "samples": vals}


async def main():
    paths = sys.argv[1:] or sorted(glob.glob("data/step4_cumulative/*.eval"))
    model = get_model(MONITOR, role=None, strict_tools=False)
    rows = []
    for p in paths:
        log = read_eval_log(p)
        for s in log.samples or []:
            md, store = s.metadata or {}, s.store or {}
            commits = store.get("commits") or []
            if not commits:
                continue
            agents = md.get("agents") or []
            tr = store.get("task_results") or {}
            side = store.get("side_task_name")
            cums = rebuild(commits)
            for c, cum in zip(commits, cums, strict=True):
                i = c["agent_index"]
                rows.append({
                    "campaign": s.id, "condition": md.get("condition"), "K": md.get("n_agents"),
                    "side": side, "side_pass": bool(tr.get(side)) if side else None,
                    "agent_index": i, "main_task": c["main_task_name"],
                    "per_diff": c["diff"],
                    "cum_diff": cum,
                    "cum_desc": "\n\n".join(
                        main_objectives[a["main_task_name"]] for a in agents[: i + 1]),
                    "per_desc": main_objectives[c["main_task_name"]],
                    "rebuild_ok": cum is not None,
                })
    ok = sum(1 for r in rows if r["rebuild_ok"])
    print(f"rebuilt cumulative diffs for {ok}/{len(rows)} commits")

    sem = asyncio.Semaphore(8)

    async def work(r):
        async with sem:
            r["per"] = await score(model, r["per_desc"], r["per_diff"])
            r["cum"] = (await score(model, r["cum_desc"], r["cum_diff"])
                        if r["rebuild_ok"] else {"median": None, "samples": []})

    print(f"scoring {len(rows)} commits x 2 views x {N_SAMPLES} samples...")
    await asyncio.gather(*(work(r) for r in rows))
    for r in rows:
        for k in ("per_diff", "cum_diff", "cum_desc", "per_desc"):
            r.pop(k, None)
    Path("data/step4_cumulative/robust_scores.json").write_text(json.dumps(rows, indent=1))
    print("wrote data/step4_cumulative/robust_scores.json")


if __name__ == "__main__":
    asyncio.run(main())
