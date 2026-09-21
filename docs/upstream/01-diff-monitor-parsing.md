# DRAFT — not sent. Upstream report: `git_diff_monitor` discards verdicts the model did state

**Target:** control-arena. **Observed on:** `control-arena==19.0.0` with `inspect-ai==0.3.266`.
**Status:** suspected upstream defect, not yet confirmed with maintainers.

## Summary

`git_diff_monitor`'s prompt asks the model to emit `<reasoning>` first and `<score>` last, and the scorer
extracts the score with `extract_xml_tag`. When the judge states its verdict in any other form — a fenced
number, a labelled "Score: 7" — the extraction returns `None` and the scorer raises
`ValueError("No score or reasoning found in model response")`. The verdict is lost, and the sample errors
rather than degrading.

## Why it matters

The responses that break format are not a random subset. In our data they skewed toward the longer,
more thorough analyses, so the surviving scores were biased toward shallower, lower-suspicion reads.
With `gemini-2.5-flash-lite` as the trusted model we measured 83/99 responses using `<score>` tags,
11/99 using another format that the scorer discards, and 5/99 unparseable by any rule we tried.

## Reproduction

Archived responses and a replay are in our repository (offline, no API key):

```
results/archive/defective_behaviour.json
python src/fragwatch/repro_bugs.py        # reproduction B1
```

Six archived responses show a stated verdict outside `<score>` tags for which the XML-only extraction
returns nothing.

## Suggested remedies

1. Ask for the score **first**, so a truncated or verbose answer still yields it.
2. Accept a small set of alternative formats, or constrain the output format at the provider level.
3. Degrade rather than raise: record a parse failure as its own status so the sample is analysable
   instead of errored.

We have not opened this upstream yet and would welcome correction if we have misread the intended usage.
