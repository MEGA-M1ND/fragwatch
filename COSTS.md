# COSTS.md — running tally of tokens and dollars

All model calls go through OpenRouter (the only key available in this environment).
Prices are from `GET https://openrouter.ai/api/v1/models` on 2026-09-20, USD per 1M tokens.

## Price sheet (candidate models)

| Model (Inspect string) | Input $/M | Output $/M | Tool calls | Note |
|---|---|---|---|---|
| `openrouter/openai/gpt-4.1-nano` | 0.10 | 0.40 | yes | cheapest OpenAI with reliable tool use |
| `openrouter/google/gemini-2.5-flash-lite` | 0.10 | 0.40 | yes | |
| `openrouter/openai/gpt-5-nano` | 0.05 | 0.40 | yes | reasoning model; hidden reasoning tokens billed as output |
| `openrouter/openai/gpt-4.1-mini` | 0.40 | 1.60 | yes | step up if nano can't drive the setting |
| `openrouter/openai/gpt-5-mini` | 0.25 | 2.00 | yes | |
| `openrouter/anthropic/claude-haiku-4.5` | 1.00 | 5.00 | yes | |
| `openrouter/openai/gpt-5.4-mini` | 0.75 | 4.50 | yes | ControlArena's default *trusted* model |
| `openrouter/anthropic/claude-sonnet-4.6` | 3.00 | 15.00 | yes | ControlArena's default *untrusted* model; too expensive for this pilot |

## Ledger

| # | Date | Step | What | Model(s) | Input tok | Output tok | Cost (USD) | Cumulative (USD) |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-20 | 1 | connectivity ping through Inspect | gpt-4.1-nano | 14 | 2 | 0.0000022 | 0.0000022 |
| 2 | 2026-09-20 | 3 | tool-schema validation pings (2 models) | gpt-4.1-nano, gemini-2.5-flash-lite | 1,160 | 4 | 0.00012 | 0.00012 |
| 3 | 2026-09-20 | 3 | run 1: iac_fast attack, 1 sample, 10 steps | untrusted gpt-4.1-nano (56,326 in + 207,872 cached in + 297 out); trusted gemini-2.5-flash-lite (3,371 in + 1,344 out) | 268,913 | 1,641 | 0.0119 | 0.0121 |

Cached input tokens for OpenAI models are billed at 25% of the input price on OpenRouter (nano: $0.025/M).
Costs are computed as `input_tok * in_price + cached_tok * cache_price + output_tok * out_price` from Inspect's reported
`ModelUsage`, because OpenRouter's `total_cost` field came back `None` through Inspect.
