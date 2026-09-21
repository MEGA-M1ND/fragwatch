# results/ — canonical derived records

One directory per run, never overwritten implicitly. Each contains:

- `provenance.json` — run id, provenance class (historical / exploratory / confirmatory), protocol
  version, source log, code commit, monitor model, prompt version, scoring-config fingerprint.
- `monitor_records.jsonl` — one record per (commit, view) monitor evaluation, with every attempt's raw
  response, parsed verdict, status, tokens and modelled cost. Evaluator-only labels are held in a
  separate `labels` object from the monitor-visible `monitor_input`.
- `campaign_records.jsonl` — campaign-level outcomes. Campaigns are the experimental units.

## Regenerating

```bash
# Import a historical .eval log (no model calls; reparses preserved raw responses)
python src/fragwatch/import_legacy.py data/<run>/*.eval \
  --run-id hist_<run> --protocol-version P-X --code-commit <sha>

# Offline report from canonical records
python src/fragwatch/report.py results/hist_* --sweep
```

## Provenance of the historical imports

| run id | source | protocol | notes |
|---|---|---|---|
| `hist_step4_matched` | `data/step4_matched/` | P-A | no delivery checks; no cumulative monitor, so 25 cumulative views have no model call |
| `hist_step4_cumulative` | `data/step4_cumulative/` | P-B | adds cumulative monitor; s3 and backdoor fragments without delivery checks |
| `hist_step4_backdoor_fixed` | `data/step4_backdoor_fixed/` | P-C | backdoor only; delivery checks + retry, scorer-specific fragment hints |

All three are **historical**: they were produced before the protocol was frozen, under a live scoring
path that has since been replaced. They are evidence about the pipeline, not confirmatory results.

Historical verdicts use the `attempt0` aggregation policy: only the first monitor call counts, because
the live retry loop changed temperature between attempts (0.0 then 0.5), which makes later attempts
non-exchangeable. The discarded attempts are preserved in each record and are themselves a finding —
in several cases the live path replaced a high-suspicion verdict with a low-suspicion one.

`data/step4_cumulative/robust_scores.json` for the s3 arm was deleted from the working tree by
commit `7963b93` (hard-coded output path). It is recoverable with
`git show dff0f37:data/step4_cumulative/robust_scores.json`, and is superseded by the canonical import
above, which reparses the same run's raw responses.
