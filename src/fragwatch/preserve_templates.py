"""Preserve the synthesized CloudFormation template for every pilot campaign, with an evidence manifest.

One-time archival step. For each campaign it reads the cumulative diff preserved in the original
`.eval` log, writes that diff out as a durable patch file, reconstructs the repository state, synthesizes
the stack in the pinned container image, and writes the resulting template as canonical JSON. It then
records, for each campaign, the chain log -> diff -> template -> outcome with a hash at every link.

Requires the eval stack and Docker. The *checking* side (`check_templates.py`) requires neither: it reads
the archived templates and re-applies the verifier with the standard library alone.

Honesty note on the synthesis environment: the image used during the original revalidation was not
retained (the container store was empty after a daemon restart), so the image recorded here is a rebuild
from the same pinned Dockerfile. A rebuild is not byte-identical and cannot be shown to be. What is
established is that the archived templates, verified offline, reproduce the reported classifications.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inspect_ai.log import read_eval_log  # noqa: E402

from fragwatch.revalidate import IMAGE, synthesize  # noqa: E402
from fragwatch.verify_attack import verify_backdoor, verify_s3_deletion  # noqa: E402

OUT_DIR = Path("results/templates")
MANIFEST = OUT_DIR / "MANIFEST.json"
VERIFIER = Path(__file__).with_name("verify_attack.py")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def canonical_template(tmpl: dict) -> bytes:
    """One byte representation per template, so the hash is stable across runs."""
    return (json.dumps(tmpl, indent=1, sort_keys=True) + "\n").encode()


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def synthesis_environment() -> dict:
    r = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                       capture_output=True, text=True)
    image_id = r.stdout.strip() if r.returncode == 0 else "unavailable"
    return {
        "image_tag": IMAGE,
        "image_id": image_id,
        "dockerfile": "src/docker/iac_fast.Dockerfile.patched",
        "dockerfile_sha256": sha256_file(Path("src/docker/iac_fast.Dockerfile.patched")),
        "note": "rebuilt from the pinned Dockerfile; the image used at the original revalidation was "
                "not retained, and a rebuild is not byte-identical to it",
    }


def verifier_revision() -> dict:
    return {
        "module": "src/fragwatch/verify_attack.py",
        "sha256": sha256_file(VERIFIER),
        "code_sha": _git("rev-parse", "--short", "HEAD") or "unknown",
        "tree_dirty": bool(_git("status", "--porcelain")),
    }


def classify(tmpl: dict, objective: str | None) -> dict:
    if objective == "O1":
        return verify_s3_deletion(tmpl)
    res = verify_backdoor(tmpl)
    if objective is None:
        res["s3_guardrail_removed"] = verify_s3_deletion(tmpl)["attack_success"]
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("globs", nargs="+")
    ap.add_argument("--reported", default="results/semantic_verification.json",
                    help="the classifications the report already publishes")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    a = ap.parse_args()

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    reported = json.loads(Path(a.reported).read_text())

    entries, failures = [], []
    for g in a.globs:
        for f in sorted(glob.glob(g)):
            log_path = Path(f)
            log_sha = sha256_file(log_path)
            evl = read_eval_log(f)
            for s in evl.samples or []:
                cid = str(s.id)
                commits = (s.store or {}).get("commits", [])
                cum = commits[-1].get("cum_diff") if commits else None
                objective = (s.metadata or {}).get("objective_id")
                if not cum:
                    failures.append(f"{cid}: no cumulative diff preserved in {log_path.name}")
                    continue

                diff_path = out_dir / f"{cid}.cum_diff.patch"
                diff_bytes = (cum if cum.endswith("\n") else cum + "\n").encode()
                diff_path.write_bytes(diff_bytes)

                tmpl, why = synthesize(cum)
                if tmpl is None:
                    failures.append(f"{cid}: {why}")
                    continue

                tmpl_bytes = canonical_template(tmpl)
                tmpl_path = out_dir / f"{cid}.template.json"
                tmpl_path.write_bytes(tmpl_bytes)

                res = classify(tmpl, objective)
                rep = reported.get(cid, {})
                entry = {
                    "campaign": cid,
                    "objective": objective,
                    "source_log": log_path.name,
                    "source_log_path": str(log_path),
                    "source_log_sha256": log_sha,
                    "cum_diff_file": diff_path.name,
                    "cum_diff_sha256": sha256_bytes(diff_bytes),
                    "template_file": tmpl_path.name,
                    "template_sha256": sha256_bytes(tmpl_bytes),
                    "expected_status": rep.get("status"),
                    "expected_attack_success": rep.get("attack_success"),
                    "observed_status": res.get("status"),
                    "observed_attack_success": res.get("attack_success"),
                }
                if (entry["observed_status"], entry["observed_attack_success"]) != (
                        entry["expected_status"], entry["expected_attack_success"]):
                    failures.append(
                        f"{cid}: archived template classifies as "
                        f"{entry['observed_status']}/{entry['observed_attack_success']} but the report "
                        f"says {entry['expected_status']}/{entry['expected_attack_success']}")
                entries.append(entry)
                print(f"  {cid:34} {res['status']:11} attack_success={res['attack_success']}")

    manifest = {
        "schema": "fragwatch.template_manifest/1",
        "purpose": "links each preserved synthesized template to its campaign, its original log, its "
                   "preserved cumulative diff, the verifier revision that classified it, the synthesis "
                   "environment and the outcome the report publishes",
        "scope": "static validation of a synthesized template; not deployment and not exploitation",
        "verifier_revision": verifier_revision(),
        "synthesis_environment": synthesis_environment(),
        "reported_source": a.reported,
        "reported_source_sha256": sha256_file(Path(a.reported)),
        "campaigns": sorted(entries, key=lambda e: e["campaign"]),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"\nwrote {out_dir/'MANIFEST.json'} ({len(entries)} campaigns)")
    if failures:
        print("\nFAILURES:", file=sys.stderr)
        for x in failures:
            print(f"  - {x}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
