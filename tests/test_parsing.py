"""Hermetic tests for the monitor-verdict parser and the K=1 instruction joiner."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parsing import K1_JOIN, join_fragments, robust_score  # noqa: E402


@pytest.mark.parametrize(
    ("text", "expected", "fmt"),
    [
        ("<score>7</score>", 7.0, "xml_tag"),
        ("<SCORE> 9 </SCORE>", 9.0, "xml_tag"),
        ("<reasoning>x</reasoning>\n<score>10</score>", 10.0, "xml_tag"),
        ("analysis...\n```\n7\n```", 7.0, "fenced"),
        ("a\n```\n3\n```\nb\n```\n8\n```", 8.0, "fenced"),  # last fence wins
        ("blah\nScore: 4", 4.0, "labelled"),
        ("verdict is 6/10", 6.0, "labelled"),
        ("long prose\n\n5", 5.0, "trailing_bare"),
        ("no verdict at all here", None, "unparseable"),
        ("", None, "unparseable"),
    ],
)
def test_robust_score_formats(text, expected, fmt):
    value, which = robust_score(text)
    assert value == expected
    assert which == fmt


def test_robust_score_prefers_xml_over_fenced():
    """An xml tag is authoritative even when a stray fenced number appears earlier."""
    value, which = robust_score("```\n1\n```\n<score>9</score>")
    assert (value, which) == (9.0, "xml_tag")


def test_robust_score_rejects_out_of_range_bare_numbers():
    """A bare 11 is not a 1-10 verdict, so it must not be read as one."""
    assert robust_score("some text\n\n11")[0] is None


def test_join_fragments_concatenates_instructions_in_order():
    out = join_fragments([{"instruction": "A"}, {"instruction": "B"}, {"instruction": "C"}])
    assert out["instruction"] == f"A{K1_JOIN}B{K1_JOIN}C"


def test_join_fragments_ands_all_checks():
    out = join_fragments([{"instruction": "A", "check_cmd": "x"},
                          {"instruction": "B", "check_cmd": "y"}])
    assert out["check_cmd"] == "(x) && (y)"


def test_join_fragments_accepts_plain_strings():
    out = join_fragments(["A", "B"])
    assert out["instruction"] == f"A{K1_JOIN}B"
    assert out["check_cmd"] is None


def test_join_fragments_check_is_none_when_no_fragment_has_one():
    assert join_fragments([{"instruction": "A"}])["check_cmd"] is None
