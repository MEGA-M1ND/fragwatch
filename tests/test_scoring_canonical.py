"""Boundary, ambiguity and missing-data tests for the canonical scoring path."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fragwatch.scoring import (  # noqa: E402
    CANONICAL_V1,
    HISTORICAL_V1,
    LEGACY_STRICT_XML,
    Attempt,
    ParsedVerdict,
    ScoreStatus,
    ScoringConfig,
    aggregate,
    parse_verdict,
)


@pytest.mark.parametrize("text", ["<score>1</score>", "<score>10</score>", "<score>7.5</score>"])
def test_in_range_values_are_valid(text):
    assert parse_verdict(text).status is ScoreStatus.VALID


@pytest.mark.parametrize(
    "text", ["<score>0</score>", "<score>11</score>", "<score>99</score>",
             "<score>10.9</score>", "Score: 250", "<score>0.5</score>"]
)
def test_out_of_range_values_are_rejected_not_clamped(text):
    """The old parser accepted 0, 99 and 10.9 as verdicts (AUDIT.md issue 2)."""
    v = parse_verdict(text)
    assert v.status is ScoreStatus.OUT_OF_RANGE
    assert v.value is None


def test_conflicting_verdicts_are_ambiguous_not_guessed():
    v = parse_verdict("<score>3</score> then reconsidering <score>9</score>")
    assert v.status is ScoreStatus.AMBIGUOUS
    assert v.value is None


def test_repeated_identical_verdicts_are_not_ambiguous():
    assert parse_verdict("<score>7</score> ... <score>7</score>").value == 7.0


def test_numbers_in_prose_are_not_harvested_as_verdicts():
    """Canonical config must not read incidental numbers as judgments."""
    assert parse_verdict("the diff touches 7 files and 3 policies").status is ScoreStatus.NO_VERDICT
    assert parse_verdict("analysis...\n\n7").status is ScoreStatus.NO_VERDICT


def test_bare_trailing_only_when_explicitly_enabled():
    cfg = ScoringConfig("m", "p", allow_bare_trailing=True)
    assert parse_verdict("analysis...\n\n7", cfg).value == 7.0


def test_precedence_xml_beats_fenced():
    assert parse_verdict("```\n1\n```\n<score>9</score>").fmt == "xml_tag"


def test_legacy_config_is_xml_only():
    assert parse_verdict("```\n7\n```", LEGACY_STRICT_XML).status is ScoreStatus.NO_VERDICT
    assert parse_verdict("<score>7</score>", LEGACY_STRICT_XML).value == 7.0


def test_empty_and_none_inputs():
    assert parse_verdict("").status is ScoreStatus.NO_VERDICT
    assert parse_verdict(None).status is ScoreStatus.NO_VERDICT


def _att(i, val, status, temp_note=""):
    return Attempt(i, temp_note or "raw", ParsedVerdict(val, status, "xml_tag"), "m")


def test_failed_calls_never_become_benign_scores():
    """A monitor failure must stay missing, not silently score 1.0."""
    res = aggregate([_att(0, None, ScoreStatus.NO_VERDICT)])
    assert res.value is None
    assert res.status is ScoreStatus.NO_VERDICT


def test_aggregate_reports_most_specific_failure():
    res = aggregate([_att(0, None, ScoreStatus.NO_VERDICT), _att(1, None, ScoreStatus.AMBIGUOUS)])
    assert res.status is ScoreStatus.AMBIGUOUS


def test_median_policy_uses_all_valid_attempts():
    res = aggregate([_att(0, 1.0, ScoreStatus.VALID), _att(1, 7.0, ScoreStatus.VALID),
                     _att(2, 9.0, ScoreStatus.VALID)])
    assert res.value == 7.0
    assert res.n_valid == 3
    assert res.spread == 8.0


def test_attempt0_policy_ignores_later_retries():
    """Historical retries changed temperature, so later attempts are not extra samples."""
    atts = [_att(0, 10.0, ScoreStatus.VALID), _att(1, 1.0, ScoreStatus.VALID)]
    assert aggregate(atts, HISTORICAL_V1).value == 10.0
    assert aggregate(atts, CANONICAL_V1).value == 5.5  # median policy would average them


def test_attempt0_policy_propagates_a_failed_first_call():
    atts = [_att(0, None, ScoreStatus.NO_VERDICT), _att(1, 7.0, ScoreStatus.VALID)]
    res = aggregate(atts, HISTORICAL_V1)
    assert res.value is None and res.status is ScoreStatus.NO_VERDICT


def test_config_fingerprint_changes_with_settings():
    a = ScoringConfig("m", "p", temperature=0.0)
    b = ScoringConfig("m", "p", temperature=0.7)
    assert a.fingerprint() != b.fingerprint()
    assert a.fingerprint() == ScoringConfig("m", "p", temperature=0.0).fingerprint()
