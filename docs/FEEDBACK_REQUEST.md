# Draft: request for external methodological feedback

**Status: DRAFT — not sent.** No recipient chosen. Links point at a branch, not a release.

---

Subject: Sanity check on a small AI-control pilot — fragmented attacks and per-commit monitoring

Hello,

I have been running a small pilot on whether an attack split across several commits evades a
per-commit LLM monitor, built on ControlArena's `iac_fast` setting. The pilot reached a gate and I
stopped rather than scaling it up. Before I either extend it or drop the setting, I would value a
methodological read from someone outside the work.

The short version: an earlier round of results did not survive its own audit. The published headline
was not reproducible by any committed command, the per-commit versus cumulative ordering changed
depending on which scoring procedure was used, and one of the two input files had been deleted by a
hard-coded output path. I rebuilt the measurement pipeline, froze a protocol, ran a small
developmental batch, and the batch did not support continuing.

What I think I can defend:

> In this small developmental batch, cumulative-diff monitoring did not improve detection over
> per-commit monitoring. Some partial changes received low suspicion scores, but the completed attack
> often retained a locally suspicious joining commit. These results do not yet establish a suitable
> setting for evaluating correlation-based recovery.

Everything is at `github.com/MEGA-M1ND/fragwatch`, branch `claude/audit-repair-protocol`:

- `AUDIT.md` — what was wrong with the earlier results, claim by claim.
- `PROTOCOL.md` — threat model, matched arms, measurements, and four amendments recording where I got
  it wrong (including declaring a freeze prematurely).
- `PILOT_REPORT.md` — the developmental results table.
- `GATE_DECISION.md` — why I stopped.
- `docs/WALKTHROUGH.md` — five offline minutes, no API key needed.

Three questions I would most like answered:

1. **Is the joining commit an artefact of my construction or a real property of this threat model?**
   In my decomposition the step that binds a privilege to a broad target stays locally suspicious
   (7.0, 4.0, 7.0 on a 1–10 scale) even when the privilege is referenced only by an imported constant.
   I can imagine both readings: that a distributed attack must always terminate in one conspicuous
   binding step, or that I simply have not found the right split. Is there a principled way to tell
   these apart without iterating decompositions until one evades the monitor, which I have deliberately
   refused to do?

2. **How should I aggregate an unstable judge at this scale?** The monitor is near-ternary on a 1–10
   scale and mostly stable (mean spread 0.29 over three same-settings calls at temperature 0), but the
   instability concentrates on exactly the decisive inputs. One campaign's verdict flips between alert
   and no-alert depending on whether I take the median or the maximum of three calls. More calls per
   input is the obvious answer; is there a better one, and what would you consider the minimum
   defensible number before reporting a campaign-level rate?

3. **Is this setting worth extending, or should I switch?** `iac_fast` gave me a programmatic grader
   and cheap runs, but its side tasks are single logical changes that resist meaningful fragmentation,
   and I found one grader defect (a correct implementation scores as failure unless the StackSet
   template body renders as `Fn::Join`). Would you extend this setting, move to an existing benchmark
   with genuinely multi-file objectives, or treat the measurement tooling as the contribution and drop
   the fragmentation question?

A caveat on provenance: this work was produced in one session with an AI coding agent, and
`docs/AI_ASSISTANCE.md` lists both what it built and the errors it made. Several of the corrections
above came from external review rather than from the work noticing its own problems, so I would treat
my self-assessment with appropriate suspicion.

Thank you for any time you can give it.
