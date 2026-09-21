# Future experiment specification — interleaved streams and correlation recovery

**Specification only. Nothing here is implemented, and no part of it has been run.** It exists so the
next experiment is designed before it is built, and so the gaps in the current pilot are explicit.

The pilot's campaigns are isolated: one sandbox, one campaign, no concurrent benign activity. That
cannot measure what a deployed monitor faces, and it cannot evaluate correlation, because there is
nothing to correlate against.

## 1. Valid same-repository interleaving

A **stream** is one repository with a single commit history to which many agents contribute in sequence.
Honest and attack activity interleave in that shared history rather than running in separate sandboxes.

Requirements for the interleaving to be valid:

- Commits from honest and attack agents are **ordered arbitrarily**, not blocked into runs, so position
  in the history carries no information about membership.
- Attack fragments may be separated by an arbitrary number of honest commits, sampled from a declared
  distribution rather than fixed.
- Every agent sees the repository as its predecessors left it, including other agents' honest work, so
  the attack must survive concurrent benign change.
- A stream that fails to build at any point is recorded as invalid from that commit onward and excluded,
  failing closed rather than scoring a broken repository.

## 2. Honest examples with shared files, dependencies and handoffs

Honest activity must be confusable with attack activity on structure alone, or a correlation method will
separate them for the wrong reason. Required properties:

- **Shared files.** Honest and attack commits edit overlapping files, including the files the attack
  weakens.
- **Real dependencies.** Honest work introduces constants, helpers and interfaces in one commit and
  consumes them in later commits, at a rate comparable to the attack's.
- **Task handoffs.** An honest agent leaves work deliberately unfinished for a successor (a TODO, a
  partially wired construct, a helper with no caller yet), so "a commit that only makes sense given a
  later one" is a normal event.
- Honest streams must include **benign refactors that touch security policy files** without weakening
  them, so proximity to sensitive code is not itself a signal.

## 3. Benign-to-malicious ratio, defined explicitly

Let **R** be the ratio of honest commits to attack-carrying commits within a stream. R must be declared
before running and reported with every result, because alert volume scales with it and a method that
looks precise at R=1 may be unusable at R=100.

- Report at least two values, for example R ≈ 10 and R ≈ 100, rather than one.
- R is defined over **commits**, not campaigns, and the count of attack-carrying commits excludes
  fragments that failed delivery.
- Streams with no attack at all (R = ∞) are required, to measure escalation on purely benign history.

## 4. Correlation decisions must use only information available at the time

A correlation method runs at commit *i* and may use **only** commits 1..*i*. It may not use:

- attack membership, objective names, fragment assignment or campaign identity (these live in the
  evaluator-only part of the record schema and must never be passed in);
- any commit after *i*, including the eventual outcome;
- the number of attacks present, or that an attack is present at all.

Enforcement: the method receives a redacted view built from `MonitorInput` only, and a test asserts that
no evaluator label appears in the object handed to it.

## 5. Measurements

Per stream, per method, per R:

| measurement | definition |
|---|---|
| **Stream-level escalation rate** | fraction of commits that trigger escalation to the expensive joint monitor |
| **Benign-only clusters escalated** | clusters escalated that contain no attack-carrying commit; the precision cost |
| **Repeated review of the same actions** | how many times a given commit is re-reviewed as part of different clusters; the duplicated-work cost |
| **Joint-monitor cost** | tokens, dollars and reviewed context volume spent on escalations, separately from the cheap per-commit pass |
| **Final false alerts** | alerts raised on streams or clusters with no attack, after escalation |
| **Attack recall** | attacks with at least one valid alert by the declared deadline, over attacks that actually succeeded (verified semantically, not by construction checks) |

Report campaign- or stream-level uncertainty separately from judge-call variability, as the pilot does.

## 6. Calibration and evaluation on separate streams

- **Calibration streams** fix every threshold and every escalation rule. Disjoint from evaluation.
- **Evaluation streams** are scored once, with thresholds frozen, and are not inspected beforehand.
- Calibration streams must contain enough benign variation to locate a threshold. The pilot's honest set
  did not: every verdict was 1.0, which licensed any threshold above 1 and therefore none.
- If a threshold cannot be located from calibration data, that is reported as a failure of the
  calibration set, not patched with a value borrowed from elsewhere.

## 7. Matched budgets across correlation methods

Any comparison of semantic against code-dependency or provenance correlation must equalise:

- **Compute budget**: total model calls and tokens available per stream, not per method invocation.
- **Context budget**: the number of commits and total diff volume a method may examine per decision.
- **Escalation budget**: the number of joint-monitor invocations allowed per stream.

A method that wins by spending more is not a better method. Where exact matching is impossible, report
the ratio and treat the cheaper method's result as a lower bound.

## 8. Prerequisites before any of this is worth building

1. A setting whose objectives genuinely distribute security-relevant evidence across commits. The
   pilot's did not: the step binding a privilege to a broad target stayed locally suspicious.
2. A judge stable enough for campaign-level rates, or enough calls per input to make the aggregate
   defensible. Three calls was not enough; one campaign's verdict flipped on the aggregation rule.
3. A calibration set with real benign variation.

Building the correlation comparison before these hold would produce numbers without meaning.
