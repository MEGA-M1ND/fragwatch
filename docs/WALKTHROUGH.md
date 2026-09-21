# Five-minute walkthrough

One command reproduces the whole reporting path. It needs **python3 (3.11+) and git only** — no API key,
no model calls, no Docker, no third-party packages.

```bash
./scripts/verify_release.sh
```

Three stages, each failing visibly if an artefact is missing or a number has drifted:

1. **Nine-campaign results table** from `results/pilot_campaigns.json`.
2. **Measurement-bug reproductions**, replaying archived defective behaviour from
   `results/archive/defective_behaviour.json`.
3. **Headline consistency**, asserting every number in `README.md` and `PILOT_REPORT.md` matches the
   regenerated values.

To run the tests as well (`pip install -r requirements-report.txt`, two pinned packages):

```bash
pytest -m "not integration"   # hermetic
pytest                        # adds design and reproducibility tests
```

Reproducing the **experiments** rather than the reporting is a different matter: that needs
`requirements.lock.txt` (168 packages), Docker, the `iac_fast` image and an OpenRouter key. See
`SETUP.md`.

## What to read, in order

| Minutes | Read | Why |
|---|---|---|
| 0–1 | [`CASE_STUDY.md`](../CASE_STUDY.md) §2–3 | how the original result changed across four scoring procedures, and the one raw response that shows why |
| 1–2 | output of stage 2 above | the defects, replayed, each attributed to us or to upstream |
| 2–3 | [`PILOT_REPORT.md`](../PILOT_REPORT.md) results table | the nine campaigns, with denominators |
| 3–4 | [`GATE_DECISION.md`](../GATE_DECISION.md) | why the pilot stopped instead of scaling |
| 4–5 | [`docs/AI_ASSISTANCE.md`](AI_ASSISTANCE.md) | who wrote this and which errors it made |

## The one-paragraph version

An earlier round of this project reported that per-commit monitoring beat cumulative monitoring and
concluded per-commit review was the stronger monitor. No committed command reproduced that number, the
ordering reversed depending on which of four scoring procedures was used, and one of its two input files
had been deleted by a hard-coded output path. The pipeline was rebuilt around a single validated scoring
path, a protocol was written, and a nine-campaign developmental batch found that cumulative monitoring
did not improve on per-commit monitoring — while also finding that the attack could not be fully
distributed, because the commit binding a privilege to a broad target stayed locally suspicious. The
pilot stopped there. n = 3 per arm establishes nothing about rates or equivalence.
