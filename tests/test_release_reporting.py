"""Guard the release reporting path: stdlib-only, fails visibly, matches the documents."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REPORT_PATH_MODULES = [
    "src/fragwatch/pilot_report.py",
    "src/fragwatch/repro_bugs.py",
    "src/fragwatch/sections.py",
    "src/fragwatch/summary.py",
]
THIRD_PARTY = ("inspect_ai", "control_arena", "pandas", "numpy", "pydantic", "requests")


@pytest.mark.parametrize("mod", REPORT_PATH_MODULES)
def test_reporting_modules_do_not_import_third_party(mod):
    """The offline path must stay runnable from a clean checkout with no installs."""
    text = (ROOT / mod).read_text()
    for pkg in THIRD_PARTY:
        assert f"import {pkg}" not in text, f"{mod} imports {pkg}; reporting must be stdlib-only"
        assert f"from {pkg}" not in text, f"{mod} imports from {pkg}; reporting must be stdlib-only"


def test_verify_script_is_executable_in_git():
    """A clean clone must be able to run the documented command."""
    out = subprocess.run(["git", "ls-files", "-s", "scripts/verify_release.sh"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    assert out.startswith("100755"), f"verify_release.sh is not executable in git: {out.strip()}"


def test_missing_artifact_exits_non_zero(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "src/fragwatch/pilot_report.py"),
                        "--artifact", str(tmp_path / "nope.json")],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "ARTIFACT ERROR" in r.stderr


def test_malformed_artifact_exits_non_zero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "something/else", "campaigns": []}')
    r = subprocess.run([sys.executable, str(ROOT / "src/fragwatch/pilot_report.py"),
                        "--artifact", str(bad)], capture_output=True, text=True)
    assert r.returncode != 0 and "ARTIFACT ERROR" in r.stderr


@pytest.mark.integration
def test_generated_sections_match_committed_documents():
    r = subprocess.run([sys.executable, str(ROOT / "src/fragwatch/sections.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"generated sections are stale:\n{r.stdout}\n{r.stderr}"


@pytest.mark.integration
def test_stale_generated_section_is_detected(tmp_path):
    """Negative test: a drifted number in a generated block must fail the check."""
    doc = ROOT / "PILOT_REPORT.md"
    original = doc.read_text()
    try:
        doc.write_text(original.replace("| fragmented (K3) | 3 |", "| fragmented (K3) | 99 |", 1))
        r = subprocess.run([sys.executable, str(ROOT / "src/fragwatch/sections.py"), "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 1
        assert "STALE" in r.stderr
    finally:
        doc.write_text(original)


def test_retired_checker_refuses_to_run_silently():
    r = subprocess.run([sys.executable, str(ROOT / "src/fragwatch/check_headlines.py")],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2 and "sections.py --check" in r.stderr


def test_bug_reproductions_replay_archived_artifacts_not_production_code():
    """The defects must live in the archive, not in the shipped pipeline."""
    text = (ROOT / "src/fragwatch/repro_bugs.py").read_text()
    assert "archived" in text.lower()
    assert "defective_behaviour.json" in text
    # production scoring must not contain the old permissive behaviour
    scoring = (ROOT / "src/fragwatch/scoring.py").read_text()
    assert "allow_bare_trailing: bool = False" in scoring, "canonical config must default to strict"
