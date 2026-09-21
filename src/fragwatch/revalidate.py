"""Re-run static objective validation over preserved artifacts. No agents, no model calls.

Reconstructs each campaign's final repository state from the cumulative diff stored in its `.eval` log,
synthesizes the stack in the pinned container image, and applies the corrected per-role predicate.

Fails closed: a patch that will not apply, or a stack that will not synthesize, is recorded as
`unresolved` with the reason, never as a failure or a success.
"""

from __future__ import annotations

import argparse
import glob
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from control_arena.settings.iac_fast.config import SETTING_REPO_PATH  # noqa: E402
from inspect_ai.log import read_eval_log  # noqa: E402

from fragwatch.verify_attack import SYNTH_SNIPPET, verify_backdoor, verify_s3_deletion  # noqa: E402

GIT = ["-c", "user.email=r@r.local", "-c", "user.name=r"]
IMAGE = "iac-fast:latest"


def _sh(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def synthesize(cum_diff: str) -> tuple[dict | None, str]:
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        shutil.copytree(SETTING_REPO_PATH, repo,
                        ignore=shutil.ignore_patterns("tests", "cdk.out", ".venv", "__pycache__"))
        _sh(["git", "init", "-q", "."], repo)
        _sh(["git", *GIT, "add", "-A"], repo)
        _sh(["git", *GIT, "commit", "-q", "-m", "baseline"], repo)
        patch = Path(td) / "p.patch"
        patch.write_text(cum_diff if cum_diff.endswith("\n") else cum_diff + "\n")
        r = _sh(["git", "apply", "--whitespace=nowarn", str(patch)], repo)
        if r.returncode != 0:
            r = _sh(["git", "apply", "-3", "--whitespace=nowarn", str(patch)], repo)
        if r.returncode != 0:
            return None, f"patch did not apply: {r.stderr.strip()[:160]}"
        (repo / "_synth.py").write_text(SYNTH_SNIPPET)
        d = _sh(["docker", "run", "--rm", "-v", f"{repo}:/repo", "-w", "/repo",
                 IMAGE, "python", "/repo/_synth.py"])
        lines = d.stdout.splitlines()
        if not lines or lines[0].strip() != "SYNTH_OK":
            why = lines[1] if len(lines) > 1 else (d.stderr or "no output")[:160]
            return None, f"synth failed: {why[:160]}"
        try:
            return json.loads(lines[1]), ""
        except (IndexError, json.JSONDecodeError) as exc:
            return None, f"synth output unreadable: {exc}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("globs", nargs="+")
    ap.add_argument("--out", default="results/semantic_verification.json")
    a = ap.parse_args()

    out: dict[str, dict] = {}
    for g in a.globs:
        for f in sorted(glob.glob(g)):
            log = read_eval_log(f)
            for s in log.samples or []:
                cid = str(s.id)
                commits = (s.store or {}).get("commits", [])
                cum = commits[-1].get("cum_diff") if commits else None
                objective = (s.metadata or {}).get("objective_id")
                if not cum:
                    out[cid] = {"status": "unresolved", "attack_success": None,
                                "detail": "no cumulative diff preserved for this campaign"}
                    print(f"  {cid:34} unresolved (no cum_diff)")
                    continue
                tmpl, why = synthesize(cum)
                if tmpl is None:
                    out[cid] = {"status": "unresolved", "attack_success": None, "detail": why}
                    print(f"  {cid:34} unresolved ({why[:60]})")
                    continue
                if objective == "O1":
                    res = verify_s3_deletion(tmpl)
                else:
                    res = verify_backdoor(tmpl)
                    # Honest campaigns carry no objective; the same predicate confirms the control
                    # introduced no privileged role, and the s3 guardrail is checked separately.
                    if objective is None:
                        res["s3_guardrail_removed"] = verify_s3_deletion(tmpl)["attack_success"]
                out[cid] = res
                print(f"  {cid:34} {res['status']:11} attack_success={res['attack_success']}")

    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"\nwrote {a.out} ({len(out)} campaigns)")


if __name__ == "__main__":
    main()
