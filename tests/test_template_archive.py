"""The archived-template check must fail visibly on a missing file, a changed hash, or a changed outcome.

A check that only passes is not evidence of anything, so each failure mode is exercised directly.
Standard library only, in keeping with the offline verification path.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "src" / "fragwatch" / "check_templates.py"
ARCHIVE = ROOT / "results" / "templates"


def run_check(manifest: Path, export: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK), "--manifest", str(manifest), "--export", str(export)],
        capture_output=True, text=True, cwd=ROOT)


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    """A private copy of the archive, so a mutation test never touches the committed evidence."""
    dst = tmp_path / "templates"
    shutil.copytree(ARCHIVE, dst)
    return dst


def test_committed_archive_passes() -> None:
    r = run_check(ARCHIVE / "MANIFEST.json", ROOT / "results" / "pilot_campaigns.json")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "re-verifies to the classification published" in r.stdout


def test_missing_template_fails(archive: Path) -> None:
    manifest = json.loads((archive / "MANIFEST.json").read_text())
    victim = manifest["campaigns"][0]
    (archive / victim["template_file"]).unlink()
    r = run_check(archive / "MANIFEST.json", ROOT / "results" / "pilot_campaigns.json")
    assert r.returncode != 0
    assert "MISSING TEMPLATE" in r.stderr
    assert victim["campaign"] in r.stderr


def test_hash_mismatch_fails(archive: Path) -> None:
    manifest = json.loads((archive / "MANIFEST.json").read_text())
    victim = manifest["campaigns"][0]
    p = archive / victim["template_file"]
    tmpl = json.loads(p.read_text())
    tmpl["Resources"]["fragwatch_tamper"] = {"Type": "AWS::IAM::Role"}
    p.write_text(json.dumps(tmpl, indent=1, sort_keys=True) + "\n")
    r = run_check(archive / "MANIFEST.json", ROOT / "results" / "pilot_campaigns.json")
    assert r.returncode != 0
    assert "HASH MISMATCH (template)" in r.stderr


def test_outcome_difference_fails(archive: Path) -> None:
    """A template whose content no longer expresses the objective must be reported, not passed over."""
    manifest_path = archive / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    victim = next(c for c in manifest["campaigns"] if c["expected_attack_success"] is True)
    p = archive / victim["template_file"]
    tmpl = json.loads(p.read_text())
    for res in tmpl.get("Resources", {}).values():
        if res.get("Type") == "AWS::CloudFormation::StackSet":
            res.setdefault("Properties", {})["TemplateBody"] = json.dumps({"Resources": {}})
    body = json.dumps(tmpl, indent=1, sort_keys=True) + "\n"
    p.write_text(body)
    # Update the recorded hash so the outcome comparison, not the hash check, is what fails.
    victim["template_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    r = run_check(manifest_path, ROOT / "results" / "pilot_campaigns.json")
    assert r.returncode != 0
    assert "OUTCOME DIFFERENCE" in r.stderr


def test_verifier_drift_is_reported(archive: Path) -> None:
    manifest_path = archive / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["verifier_revision"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    r = run_check(manifest_path, ROOT / "results" / "pilot_campaigns.json")
    assert r.returncode != 0
    assert "VERIFIER REVISION DRIFT" in r.stderr


def test_missing_manifest_fails(tmp_path: Path) -> None:
    r = run_check(tmp_path / "nope.json", ROOT / "results" / "pilot_campaigns.json")
    assert r.returncode != 0
    assert "MISSING MANIFEST" in r.stderr


def test_check_is_stdlib_only() -> None:
    """The check must import nothing beyond the standard library and the verifier module."""
    src = CHECK.read_text()
    for banned in ("import inspect_ai", "import control_arena", "import pytest", "import docker",
                   "import numpy", "import pandas", "import requests"):
        assert banned not in src, f"{banned} would break the stdlib-only guarantee"


def test_every_published_campaign_has_an_archived_template() -> None:
    manifest = json.loads((ARCHIVE / "MANIFEST.json").read_text())
    export = json.loads((ROOT / "results" / "pilot_campaigns.json").read_text())
    archived = {c["campaign"] for c in manifest["campaigns"]}
    published = {c["campaign"] for c in export["campaigns"]}
    assert published == archived, f"published but not archived: {sorted(published - archived)}"


def test_manifest_records_the_evidence_chain() -> None:
    manifest = json.loads((ARCHIVE / "MANIFEST.json").read_text())
    assert manifest["verifier_revision"]["sha256"]
    assert manifest["synthesis_environment"]["image_tag"]
    for c in manifest["campaigns"]:
        for field in ("campaign", "source_log", "source_log_sha256", "cum_diff_sha256",
                      "template_sha256", "expected_status", "template_file"):
            assert c.get(field) is not None, f"{c['campaign']} is missing {field}"
