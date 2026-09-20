# Five-minute walkthrough

Everything here runs **offline**. No API key, no Docker, no model calls.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock.txt
```

## 1. What the project claims, and what it does not (30 s)

Read the top of `README.md`. The one thing to notice: the historical per-commit versus cumulative
comparison is labelled **inconclusive**, because the ordering changes with the measurement procedure.
Earlier versions of this repository claimed a winner. That claim is withdrawn.

## 2. See the measurement bugs reproduce (1 min)

```bash
python src/fragwatch/repro_bugs.py
```

Four bugs reproduce against real logged data: the stock XML-only parser discards verdicts the model
did emit; the old parser accepted 0, 99 and 10.9 as 1–10 scores; a retry at a different temperature
overwrote a verdict of 10 with 1; and a hard-coded output path deleted an earlier run's results
(recoverable only from git).

## 3. Reproduce the headline contradiction (1 min)

```bash
python src/compare_monitors.py data/step4_cumulative/*.eval | head -20
```

This is the repository's own pre-audit generator. It reports per-commit 7/9 and cumulative 8/9, which
reverses the number the old README published. Neither is "the" answer; that is the point.

## 4. Regenerate the canonical historical tables (1 min)

```bash
python src/fragwatch/report.py results/hist_* --sweep
```

Deterministic, offline, with explicit denominators, missing-verdict counts and a threshold sweep. The
threshold is labelled UNCALIBRATED wherever it appears.

## 5. Regenerate the pilot table (1 min)

```bash
python src/fragwatch/pilot_report.py 'data/p1_dev_o2_v3/*.eval' 'data/p1_dev_honest_linked/*.eval' \
  --semantic results/semantic_verification.json
```

Every developmental campaign, with construction and security outcomes reported separately.

## 6. Run the tests (30 s)

```bash
pytest -m "not integration"   # hermetic, no eval stack needed
pytest                        # adds the design and reproducibility tests
```

## Where to look next

| Question | File |
|---|---|
| What was wrong with the earlier results? | `AUDIT.md` |
| What is the experiment supposed to be? | `PROTOCOL.md` |
| What was tried and rejected? | `DEV_LOG.md` |
| Should we have continued? | `GATE_DECISION.md` |
| What did the pilot actually find? | `PILOT_REPORT.md` |
