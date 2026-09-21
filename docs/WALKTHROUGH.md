# Five-minute walkthrough

One command reproduces the whole reporting path. It needs **python3 (3.11+) and git only** — no API key,
no model calls, no Docker, no third-party packages.

```bash
./scripts/verify_release.sh
```

Four stages, each failing visibly if an artefact is missing or a number has drifted:

1. **Archived-template check**, re-running the committed verifier against the nine preserved
   CloudFormation templates in `results/templates/` and comparing every outcome against the published
   table. Also runnable on its own:

   ```bash
   python3 src/fragwatch/check_templates.py
   ```

2. **Nine-campaign results table** from `results/pilot_campaigns.json`.
3. **Measurement-bug reproductions**, replaying archived defective behaviour from
   `results/archive/defective_behaviour.json`.
4. **Generated-section check**, regenerating every numerical section of `README.md`,
   `PILOT_REPORT.md` and `CASE_STUDY.md` in memory and failing on any difference.

### What the release check does and does not verify

`./scripts/verify_release.sh` verifies, offline:

1. each of the nine preserved templates named in `results/templates/MANIFEST.json` exists, hashes to
   the recorded SHA-256, and re-verifies — under the committed verifier, whose own hash is checked — to
   the outcome the report publishes;
2. the per-campaign table regenerates from `results/pilot_campaigns.json`, which is structurally
   validated (schema, required fields, duplicate campaign ids, score range);
3. **two executable reproductions** — the archived XML-only parser and the archived unvalidated parser
   are re-run against archived input and give the wrong answer where current code does not;
4. **two evidence-only checks** — preserved records confirm the retry reversal and the deleted results
   file. These document that the defects occurred; they do **not** re-execute the cause;
5. one defect (the grader reading) is **documented only** and needs Docker to replay;
6. every generated numerical section in README, PILOT_REPORT and CASE_STUDY matches a fresh in-memory
   regeneration from the canonical summary.

It does **not** re-run any agent, make any model call, or re-synthesize any template.

### The reproducibility boundary

The chain of evidence has three links, and only the first is reproducible from a clean checkout with
python3 and git alone:

| link | reproducible offline? | what it needs |
|---|---|---|
| archived template → verifier outcome → published table | **yes** | python3 and git; no Docker, no key, no network |
| preserved source changes (`*.cum_diff.patch`) → synthesized template | **no** | Docker and the pinned `iac-fast` image, rebuilt from `src/docker/iac_fast.Dockerfile.patched` (`src/fragwatch/preserve_templates.py`) |
| agent trajectories → source changes | **no** | the full eval stack, Docker and a paid OpenRouter key |

Two honest limits on the second link. The image used at the original revalidation was not retained, so
the recorded synthesis environment is a **rebuild** from the same pinned Dockerfile; a rebuild is not
byte-identical and cannot be shown to be. And CDK synthesis is not asserted to be bit-reproducible, so a
re-synthesis may produce a template that differs from the archived bytes while expressing the same thing.
What the offline check establishes is narrower and stated exactly: the published outcomes follow from the
committed verifier applied to the committed templates.

**Static verification is not deployment and not exploitation.** A template classified `success` expresses
the objective — the required privilege on a role whose own trust policy admits the modelled principal,
inside a StackSet targeting the required OU. Nothing here deploys to AWS, and nothing here demonstrates
that the access is reachable or usable in a real account.


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
