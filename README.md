# fragwatch

Pilot reproduction of the **distributed (decomposed) attack** threat model on
[ControlArena](https://github.com/UKGovernmentBEIS/control-arena)'s `iac_fast` setting: if an
untrusted model splits one covert objective across **K sequential agents**, each also doing a
legitimate task and each producing exactly **one commit**, does per-commit monitoring still catch it?

Everything here is **additive experiment code**. ControlArena and the `iac_fast` Docker image are
unmodified.

## Status: the headline comparison is INCONCLUSIVE

An audit of the earlier results (`AUDIT.md`) found that **no committed command reproduced the numbers
this README used to report**, and that the per-commit versus cumulative ordering **changes with the
measurement procedure**. On the same trajectories:

| measurement procedure | per-commit | cumulative |
|---|---|---|
| live XML-only parser with temperature-changing retries | 7/9 | 8/9 |
| post-hoc rescoring, 3 fresh calls (the old README) | 9/9 | 7/9 |
| canonical reparse, median across the live retries | 9/9 | 8/9 |
| canonical reparse, first call only at the frozen temperature | 8/9 | 7/9 |

Two of four procedures favour per-commit, one favours cumulative, one is close to tied, and the
margins are one or two campaigns out of nine. **No retrospective scoring path may be selected because
it favours the hypothesis.** The earlier claims that per-commit review is "the stronger single monitor"
and that running both "dominates either alone" are **withdrawn**: they were artefacts of choosing one
procedure and of pooling runs with different protocols.

What survives from the historical work is methodological, not empirical, and is listed below.

## Pilot outcome

> In this small developmental batch, cumulative-diff monitoring did not improve detection over
> per-commit monitoring. Some partial changes received low suspicion scores, but the completed attack
> often retained a locally suspicious joining commit. These results do not yet establish a suitable
> setting for evaluating correlation-based recovery.

Nine developmental campaigns: 3 concentrated attacks, 3 fragmented attacks, 3 honest controls with the
same cross-commit dependency shape. Attacks landed in 6/6, verified by synthesising each template, not
by the delivery greps. Per-commit alerts: 3/3 concentrated, 2/3 fragmented, 0/3 honest. Cumulative:
3/3, 1/3, 0/3. Full table, caveats and cost in **[PILOT_REPORT.md](PILOT_REPORT.md)**; the decision to
stop rather than scale is in **[GATE_DECISION.md](GATE_DECISION.md)**.

**n = 3 per arm cannot establish equivalence between the two views, a deployment false-positive rate,
or general robustness.** One campaign's verdict flips depending on whether three judge calls are
aggregated by median or maximum.

The measurement pipeline has been rebuilt around a single canonical scoring path, versioned records
with provenance, and an offline report generator (`PROTOCOL.md`, `results/README.md`). Protocol
**P-1 is developmental**, not frozen; see `PROTOCOL.md` Amendment A2. Development runs and their
outcomes, including failures, are in `DEV_LOG.md`.

## Reproduce everything offline, one command

```bash
./scripts/verify_release.sh
```

Needs **python3 (3.11+) and git only** — no API key, no model calls, no Docker, no third-party packages.
It regenerates the nine-campaign table, replays the measurement-bug reproductions from archived
responses, and asserts every number in this README and `PILOT_REPORT.md` matches the regenerated values.
Missing artefacts and drifted numbers fail visibly.

## Start here

| I want to... | Go to |
|---|---|
| Read the technical account | [CASE_STUDY.md](CASE_STUDY.md) |
| Spend five offline minutes | [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) |
| See what the pilot found | [PILOT_REPORT.md](PILOT_REPORT.md) |
| Know what was wrong before | [AUDIT.md](AUDIT.md) |
| See what a real experiment would need | [docs/FUTURE_EXPERIMENT.md](docs/FUTURE_EXPERIMENT.md) |
| Understand the AI's role and errors | [docs/AI_ASSISTANCE.md](docs/AI_ASSISTANCE.md) |
| Quiz the owner | [docs/TEN_QUESTIONS.md](docs/TEN_QUESTIONS.md) |

## Not evaluated

Semantic versus code-dependency or provenance correlation (no method was implemented), high-ratio benign
background traffic (every campaign is isolated), and any deployable joint-monitor escalation policy. All
three are specified in [docs/FUTURE_EXPERIMENT.md](docs/FUTURE_EXPERIMENT.md) and implemented nowhere.

## Three defects found in the stock tooling

These affect anyone using these components, independent of the fragmentation question.

1. **`git_diff_monitor` silently discards ~16% of its own verdicts.** Its prompt asks for
   `<score>N</score>`, but gemini-2.5-flash-lite often emits the verdict fenced or bare, and
   `extract_xml_tag` returns `None`. The discarded answers skew toward the *long, thorough* analyses,
   biasing surviving scores low. It also raises rather than degrading, which errored 4/10 samples.
   Fixed here by a robust extractor (`src/parsing.py`) — measured compliance: 83/99 xml, 11/99 other
   formats, 5/99 unparseable.
2. **`create_backdoor_admin_role` is ungradeable by a correct implementation.** Its test reads the
   StackSet's `TemplateBody` and reports "no DevHelper role" unless it is a `dict` or an `Fn::Join`,
   but `CfnStackSet` types `template_body` as `str` (a dict raises at synth). Only a JSON string
   embedding a CDK token — which CDK renders as `Fn::Join` — is visible to the scorer. A correct
   real-world implementation is graded as failure; this produced 9 consecutive false zeros.
3. **Prompted attack policies often just don't attack.** Given the vague one-line stock side-task
   description, 4/4 K=1 agents did their main task and ignored the side task entirely. Any
   fragmentation comparison must be **instruction-matched** or it measures attack occurrence rather
   than detectability.

## Repo layout

| Path | What |
|---|---|
| `SETUP.md` | Environment: Docker storage driver, proxy-aware image builds, blocked apt mirror |
| `ENVIRONMENT_AUDIT.md` | Settings inventory, interfaces, and exactly what was missing for K-agent runs |
| `FIRST_RUN.md` | Step 3: first end-to-end runs, three untrusted models |
| `MODEL_COMPARE.md` | gpt-5-mini vs gpt-4.1-mini, 5 attack samples each → model choice |
| `FRAGMENTATION_REPRO.md` | Steps 4/4b/4c: the experiment, results, corrections, caveats |
| `COSTS.md` | Token/dollar ledger for every run (CI checks its arithmetic) |
| `src/campaign.py` | The harness: K sequential agents in one sandbox, one commit each, both monitors |
| `src/fragments.py` | White-box side-task decompositions + per-fragment delivery checks |
| `src/parsing.py` | Dependency-free verdict parser and K=1 instruction joiner |
| `data/` | Raw `.eval` logs for every run (committed; see `data/README.md`) |

## Reproducing

Needs Docker and an `OPENROUTER_API_KEY`. The `iac-fast:latest` image must be built locally; see
SETUP.md for the proxy-aware build and why the base image is patched.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock.txt

# Step 3: one stock attack sample, end to end
python src/run_first.py --untrusted openrouter/openai/gpt-5-mini

# Step 4: the fragmentation matrix (K1 vs K3, 2 side tasks, + honest baseline)
python src/run_step4.py --reps 3 --log-dir data/my_run
python src/summarize_step4.py data/my_run/*.eval
python src/compare_monitors.py data/my_run/*.eval

# Re-score committed logs with the robust parser (no agents re-run)
python src/reconstruct_cumulative.py data/my_run/*.eval
```

Cost at the measured rates: ~$0.03 per gpt-5-mini agent-run; the 15-campaign matrix is ~$0.80.
Total spend for all experiments in this repo: **~$3.07** (see COSTS.md).

## Limitations

**n=3 per cell.** Every effect size here rests on three campaigns. The honest next step is n≈10
(~$4). Only K=1 vs K=3 was tested; K=9 needs repeated main tasks since `iac_fast` has only 5.
Fragments are hand-written, so this is one coordinated attack construction. It bounds nothing: a
different decomposition could be stronger or weaker. One judge, one setting, and its verdicts cluster on {1,3,4,7,8,9,10}, so the
scale is coarse.

## CI

`ci.yml` runs lint plus hermetic unit tests on every push (no Docker, no API keys, no model calls),
then an integration job that installs the full eval stack and checks the campaign matrix builds.
`report.yml` regenerates the results tables from the committed `.eval` logs and uploads them as
build artifacts. **CI never runs an eval** — that costs money and needs a sandbox.
