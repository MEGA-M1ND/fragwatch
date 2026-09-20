# data/

Raw Inspect `.eval` logs and rendered trajectory dumps, one subdirectory per run.
Regenerate a dump with `python src/dump_trajectory.py <file.eval> <out.md>`.

- `first_run/` — Step 3. Contains the two failed-launch logs (no model tokens, kept for the
  record), run 1 (gpt-4.1-nano), run 2 (gpt-4.1-mini) and run 3 (gpt-5-mini). See FIRST_RUN.md.
- `model_compare/gpt5mini/`, `model_compare/gpt41mini/` — Step 3b, 5 attack samples per untrusted model. See MODEL_COMPARE.md.
- `step4/` — Step 4 run A (uncontrolled): K1 got the vague stock side-task description while K3 got
  precise fragment instructions, so K1 agents never attempted the side task. Kept as the record of
  why the design was corrected. See FRAGMENTATION_REPRO.md.
- `step4_matched/` — Step 4 run B (instruction-matched): K1 receives the same three steps that K3
  splits between its agents. This is the comparison that answers the question.
