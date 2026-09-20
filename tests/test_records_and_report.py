"""Tests for the canonical record store, metric calculations and report reproducibility."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fragwatch.records import (  # noqa: E402
    SCHEMA_VERSION,
    CampaignRecord,
    EvaluatorLabels,
    MonitorInput,
    MonitorRecord,
    RecordStore,
    RunProvenance,
    content_hash,
)
from fragwatch.report import InvariantError, campaign_max, check_invariants  # noqa: E402


def _mon(cid, idx, view, value, status="valid", missing_reason=None):
    return MonitorRecord(
        schema_version=SCHEMA_VERSION, run_id="r", campaign_id=cid,
        event_id=f"{cid}/{idx}/{view}", commit_index=idx,
        monitor_input=MonitorInput(view=view, diff_hash="sha256:x", diff_lines=10,
                                   task_description_hash="sha256:y"),
        labels=EvaluatorLabels(is_attacker_commit=True, condition="K3_attack",
                               side_task_name="s", main_task_name="m"),
        value=value, status=status, n_attempts=1, n_valid=1 if status == "valid" else 0,
        spread=None, input_tokens=1, output_tokens=1, cost_usd=0.0,
        unresolved_reason=missing_reason,
    )


def _camp(cid, side_pass=True, k=3):
    return CampaignRecord(
        schema_version=SCHEMA_VERSION, run_id="r", campaign_id=cid, condition="K3_attack",
        k_agents=k, side_task_name="s", side_task_success=side_pass, main_tasks={"m": True},
        n_commits=3, fragments_delivered=3, fragments_retried=0,
        agent_limit_hits=0, agent_timeouts=0,
    )


def test_store_refuses_to_overwrite_another_run(tmp_path):
    """AUDIT.md issue 4: hard-coded paths destroyed a run's derived results."""
    RecordStore(tmp_path, "run1")
    with pytest.raises(FileExistsError):
        RecordStore(tmp_path, "run1")
    RecordStore(tmp_path, "run1", allow_existing=True)  # explicit opt-in only


def test_roundtrip_preserves_records(tmp_path):
    s = RecordStore(tmp_path, "r")
    s.write_provenance(RunProvenance("r", "confirmatory", "P-X", "log.eval"))
    s.write_monitor([_mon("c1", 0, "per_commit", 7.0)])
    s.write_campaigns([_camp("c1")])
    prov, mons, camps = RecordStore.load(tmp_path / "r")
    assert prov["provenance"] == "confirmatory"
    assert mons[0]["value"] == 7.0
    assert camps[0]["side_task_success"] is True


def test_monitor_records_are_written_in_deterministic_order(tmp_path):
    s = RecordStore(tmp_path, "r")
    s.write_provenance(RunProvenance("r", "historical", "P-X", "log.eval"))
    recs = [_mon("c2", 1, "per_commit", 1.0), _mon("c1", 0, "cumulative", 2.0),
            _mon("c1", 0, "per_commit", 3.0)]
    s.write_monitor(recs)
    order = [(m["campaign_id"], m["commit_index"], m["monitor_input"]["view"])
             for m in RecordStore.load(tmp_path / "r")[1]]
    assert order == sorted(order)


def test_evaluator_labels_are_separate_from_monitor_input():
    """Attack membership must not sit inside the monitor-visible object."""
    m = _mon("c1", 0, "per_commit", 7.0)
    visible = json.dumps(m.monitor_input.__dict__)
    for leak in ("is_attacker", "side_task", "condition", "K3"):
        assert leak not in visible


def test_campaign_max_reports_missing_and_never_hides_it():
    """AUDIT.md issue 7: maxima silently dropped missing verdicts."""
    mons = [json.loads(_mon("c1", 0, "per_commit", 7.0).to_json()),
            json.loads(_mon("c1", 1, "per_commit", None, "no_verdict").to_json())]
    mx, n_valid, missing = campaign_max(mons, "c1", "per_commit")
    assert (mx, n_valid, missing) == (7.0, 1, 1)


def test_campaign_max_with_no_valid_verdicts_is_none():
    mons = [json.loads(_mon("c1", 0, "per_commit", None, "no_verdict").to_json())]
    assert campaign_max(mons, "c1", "per_commit") == (None, 0, 1)


def test_invariant_catches_value_with_failure_status():
    bad = json.loads(_mon("c1", 0, "per_commit", 7.0, "no_verdict").to_json())
    with pytest.raises(InvariantError):
        check_invariants([bad], [json.loads(_camp("c1").to_json())])


def test_invariant_catches_out_of_range_value():
    bad = json.loads(_mon("c1", 0, "per_commit", 42.0).to_json())
    with pytest.raises(InvariantError):
        check_invariants([bad], [json.loads(_camp("c1").to_json())])


def test_invariant_catches_orphan_monitor_record():
    m = json.loads(_mon("ghost", 0, "per_commit", 7.0).to_json())
    with pytest.raises(InvariantError):
        check_invariants([m], [json.loads(_camp("c1").to_json())])


def test_content_hash_is_stable_and_distinguishes():
    assert content_hash("a") == content_hash("a") != content_hash("b")
    assert content_hash(None) == "sha256:none"


@pytest.mark.integration
def test_report_generation_is_byte_reproducible(tmp_path):
    """Two runs of the offline report on the same records must be identical."""
    s = RecordStore(tmp_path, "r")
    s.write_provenance(RunProvenance("r", "historical", "P-X", "log.eval"))
    s.write_monitor([_mon("c1", 0, "per_commit", 7.0), _mon("c1", 0, "cumulative", 3.0)])
    s.write_campaigns([_camp("c1")])
    cmd = [sys.executable, str(ROOT / "src/fragwatch/report.py"), str(tmp_path / "r")]
    a = subprocess.run(cmd, capture_output=True, text=True, check=True)
    b = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert a.stdout == b.stdout
    assert "UNCALIBRATED" in a.stdout, "threshold must be labelled as not yet calibrated"
