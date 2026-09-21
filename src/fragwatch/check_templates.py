"""Re-verify the archived CloudFormation templates and compare against every published classification.

Standard library only. No Docker, no container image, no eval stack, no network, no API key. This is the
command a reader runs to confirm that the outcome table was produced by the committed verifier from the
committed templates, and not asserted.

What it establishes, for each of the nine campaigns:

1. the preserved template and cumulative diff named by the manifest exist;
2. their SHA-256 hashes are the ones the manifest recorded;
3. the source `.eval` log still hashes to the value recorded when the template was synthesized;
4. the committed verifier, re-run against the archived template, returns the manifest's outcome;
5. that outcome agrees with the classification published in the pilot export.

Any missing file, any hash mismatch, any outcome difference and any verifier-revision drift is a visible
failure with a non-zero exit. It does not re-synthesize: going from the preserved source changes back to
a template needs the pinned container image (see `preserve_templates.py`). It also does not establish
that any template would deploy on AWS or that the access it expresses is exploitable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fragwatch.verify_attack import verify_backdoor, verify_s3_deletion  # noqa: E402

MANIFEST = Path("results/templates/MANIFEST.json")
EXPORT = Path("results/pilot_campaigns.json")
VERIFIER = Path(__file__).with_name("verify_attack.py")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(tmpl: dict, objective: str | None) -> dict:
    if objective == "O1":
        return verify_s3_deletion(tmpl)
    res = verify_backdoor(tmpl)
    if objective is None:
        res["s3_guardrail_removed"] = verify_s3_deletion(tmpl)["attack_success"]
    return res


def check(manifest_path: Path, export_path: Path) -> list[str]:
    problems: list[str] = []
    if not manifest_path.exists():
        return [f"MISSING MANIFEST: {manifest_path}"]
    manifest = json.loads(manifest_path.read_text())
    root = manifest_path.parent

    rev = manifest.get("verifier_revision") or {}
    live = sha256_file(VERIFIER)
    if rev.get("sha256") != live:
        problems.append(
            f"VERIFIER REVISION DRIFT: {VERIFIER} hashes {live[:16]} but the manifest records "
            f"{str(rev.get('sha256'))[:16]}. The archived outcomes were produced by a different "
            f"verifier. Re-run preserve_templates.py to refresh the manifest deliberately.")
    print(f"verifier  {VERIFIER}  sha256={live[:16]}  "
          f"{'matches manifest' if rev.get('sha256') == live else 'DIFFERS FROM MANIFEST'}")

    published: dict[str, object] = {}
    if export_path.exists():
        for c in json.loads(export_path.read_text()).get("campaigns", []):
            published[c["campaign"]] = c.get("semantic_attack_success")
    else:
        problems.append(f"MISSING EXPORT: {export_path} (cannot compare against the published table)")

    campaigns = manifest.get("campaigns") or []
    if not campaigns:
        problems.append("MANIFEST LISTS NO CAMPAIGNS")

    print(f"\n{'campaign':34} {'template':10} {'hashes':8} {'verifier':22} {'published':10}")
    for entry in campaigns:
        cid = entry["campaign"]
        tmpl_path = root / entry["template_file"]
        diff_path = root / entry["cum_diff_file"]
        t_state, h_state, v_state, p_state = "ok", "ok", "", ""

        for label, path in (("template", tmpl_path), ("cumulative diff", diff_path)):
            if not path.exists():
                problems.append(f"MISSING {label.upper()}: {cid} -> {path}")
                t_state = "MISSING"
        log_path = Path(entry["source_log_path"])
        if not log_path.exists():
            problems.append(f"MISSING SOURCE LOG: {cid} -> {log_path}")
            h_state = "MISSING"

        if t_state == "ok":
            for label, path, expected in (
                    ("template", tmpl_path, entry["template_sha256"]),
                    ("cumulative diff", diff_path, entry["cum_diff_sha256"])):
                actual = sha256_file(path)
                if actual != expected:
                    problems.append(f"HASH MISMATCH ({label}): {cid} -> {path} hashes {actual[:16]}, "
                                    f"manifest records {expected[:16]}")
                    h_state = "MISMATCH"
        if h_state == "ok" and log_path.exists():
            actual = sha256_file(log_path)
            if actual != entry["source_log_sha256"]:
                problems.append(f"HASH MISMATCH (source log): {cid} -> {log_path} hashes "
                                f"{actual[:16]}, manifest records {entry['source_log_sha256'][:16]}")
                h_state = "MISMATCH"

        if t_state == "ok":
            res = classify(json.loads(tmpl_path.read_text()), entry.get("objective"))
            got = (res.get("status"), res.get("attack_success"))
            want = (entry.get("expected_status"), entry.get("expected_attack_success"))
            v_state = f"{got[0]}/{got[1]}"
            if got != want:
                problems.append(f"OUTCOME DIFFERENCE: {cid} verifies as {got[0]}/{got[1]} but the "
                                f"manifest reports {want[0]}/{want[1]}")
                v_state += " != MANIFEST"
            if cid in published:
                if published[cid] != got[1]:
                    problems.append(f"OUTCOME DIFFERENCE (published table): {cid} verifies as "
                                    f"attack_success={got[1]} but {export_path} publishes "
                                    f"{published[cid]}")
                    p_state = "DIFFERS"
                else:
                    p_state = "agrees"
            elif published:
                problems.append(f"NOT IN PUBLISHED TABLE: {cid} is archived but absent from {export_path}")
                p_state = "ABSENT"
        print(f"{cid:34} {t_state:10} {h_state:8} {v_state:22} {p_state:10}")

    archived = {e["campaign"] for e in campaigns}
    for cid in sorted(set(published) - archived):
        problems.append(f"NO ARCHIVED TEMPLATE: {cid} is published in {export_path} but not archived")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--export", default=str(EXPORT))
    a = ap.parse_args()
    problems = check(Path(a.manifest), Path(a.export))
    if problems:
        print(f"\nFAILED: {len(problems)} problem(s)\n", file=sys.stderr)
        for x in problems:
            print(f"  - {x}", file=sys.stderr)
        raise SystemExit(1)
    print("\nOK: every archived template is present, hashes as recorded, and re-verifies to the "
          "classification published in the outcome table.")


if __name__ == "__main__":
    main()
