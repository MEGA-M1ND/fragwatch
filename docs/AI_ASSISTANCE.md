# Account of AI assistance

This project was built in a single session with an AI coding agent (Claude, in Claude Code). The work
was not reviewed by a second person, and the honest summary is that **the AI wrote effectively all of
the code, the experiment designs and the prose, and also made most of the substantive errors that the
later audit found.**

## What the AI did

- Environment setup, the ControlArena settings audit, and the choice of `iac_fast`.
- The campaign harness, the monitors, the scoring path, the record schema, the importer, the report
  generators, the test suite and the CI workflows.
- The attack decompositions, including the one rejected in `DEV_LOG.md` D1.
- Every experimental run and every write-up in this repository.

## Errors the AI made, and how they surfaced

These are listed because a reader should calibrate on them, not because they were caught.

| Error | How it surfaced |
|---|---|
| Published a headline no committed command reproduced | External review prompted the audit |
| Chose a post-hoc scoring path that favoured the hypothesis | Audit compared four procedures and found the ordering unstable |
| Hard-coded an output path that deleted a run's results | Audit; the file was recovered from git history |
| Confounded K=1 and K=3 on benign workload, budget and retries | External review |
| Declared a protocol "frozen" while still changing it | External review |
| Called the old assembly result "invalid" when the defensible claim was narrower | External review |
| Asserted dilution as a mechanism when judge instability explained the case | Offline prompt inspection during the final phase |
| Claimed "no false positives" from 3 honest campaigns | External review |

The pattern is consistent: the AI was reliable at building and running things, and unreliable at
resisting a tidy conclusion. Most corrections came from outside, not from the AI noticing.

## Design decisions the project owner should be able to explain

If you present this work, expect to be asked these. Each has a real answer in the repository.

1. **Why `iac_fast`?** It was the only ControlArena setting runnable in this environment (`infra`
   needs a Kubernetes cluster). Its side tasks are policy weakenings inside a mock AWS organisation,
   scored programmatically by pytest. See `ENVIRONMENT_AUDIT.md`.
2. **Why is the historical comparison inconclusive rather than negative?** Four scoring procedures on
   the same trajectories give per-commit 7/9, 9/9, 9/9 and 8/9 against cumulative 8/9, 7/9, 8/9, 7/9.
   Margins are one or two campaigns out of nine. See `AUDIT.md` §1.
3. **Why was the first assembly attack thrown away?** Its first commit alone created a role named
   `DevHelper` with `AdministratorAccess` and scored 9.0 by itself, so the split never distributed the
   incriminating evidence. See `PROTOCOL.md` §2 and `DEV_LOG.md` D1.
4. **Why is the threshold 5?** The protocol's own honest calibration set returned 1.0 on every verdict
   and could not locate a threshold. 5 is the smallest integer above the highest benign score observed
   in any honest data (4.0, historical). This mixes protocol versions and is disclosed. See
   `PROTOCOL.md` Amendment A1.
5. **Why report construction and attack success separately?** Delivery checks are greps; passing them
   shows the intended code shape, not a working backdoor. Attack success is verified by synthesising
   the template and checking an admin role actually reaches the target OU. See Amendment A3.
6. **Why is the honest control "linked"?** A monitor that flags any constant defined in one commit and
   used in another would score well on this attack while learning nothing. The control has the same
   dependency shape with no privilege change. See Amendment A4.
7. **Why stop instead of running the correlation experiment?** The gate failed: n=3 per arm, the effect
   did not replicate, it flips with the threshold, and the protocol is not frozen. See
   `GATE_DECISION.md`.
8. **Are the costs real?** They are modelled from Inspect's token counts and a hand-entered price
   sheet. OpenRouter's own cost field returned `None`. No figure here comes from an invoice.
