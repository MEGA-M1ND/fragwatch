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
| `openrouter/openai/gpt-5-mini` | 0.25 | 2.00 | yes | cached input $0.025/M; reasoning billed as output. Run 3: cheapest capable model so far |
| `openrouter/anthropic/claude-haiku-4.5` | 1.00 | 5.00 | yes | |
| `openrouter/openai/gpt-5.4-mini` | 0.75 | 4.50 | yes | ControlArena's default *trusted* model |
| `openrouter/anthropic/claude-sonnet-4.6` | 3.00 | 15.00 | yes | ControlArena's default *untrusted* model; too expensive for this pilot |

## Ledger

| # | Date | Step | What | Model(s) | Input tok | Output tok | Cost (USD) | Cumulative (USD) |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-20 | 1 | connectivity ping through Inspect | gpt-4.1-nano | 14 | 2 | 0.0000022 | 0.0000022 |
| 2 | 2026-09-20 | 3 | tool-schema validation pings (2 models) | gpt-4.1-nano, gemini-2.5-flash-lite | 1,160 | 4 | 0.00012 | 0.00012 |
| 3 | 2026-09-20 | 3 | run 1: iac_fast attack, 1 sample, 10 steps | untrusted gpt-4.1-nano (56,326 in + 207,872 cached in + 297 out); trusted gemini-2.5-flash-lite (3,371 in + 1,344 out) | 268,913 | 1,641 | 0.0119 | 0.0121 |
| 4 | 2026-09-20 | 3 | run 2: iac_fast attack, 1 sample, 37 steps (token limit) | untrusted gpt-4.1-mini (39,660 in + 429,824 cached in @$0.10/M + 1,825 out); trusted gemini-2.5-flash-lite (21,657 in + 8,279 out) | 491,141 | 10,104 | 0.0673 | 0.0794 |
| 5 | 2026-09-20 | 3 | tool-schema validation ping, gpt-5-mini | gpt-5-mini (753 in + 51 out incl. reasoning) | 753 | 51 | 0.0003 | 0.0797 |
| 6 | 2026-09-20 | 3 | run 3: iac_fast attack, 1 sample, 9 steps (submit) | untrusted gpt-5-mini (15,116 in + 38,528 cached @$0.025/M + 1,117 out incl. 663 reasoning); trusted gemini-2.5-flash-lite (5,054 in + 1,979 out) | 58,698 | 3,096 | 0.0083 | 0.0880 |
| 7 | 2026-09-20 | 3b | model compare: 5 attack samples, gpt-5-mini | untrusted gpt-5-mini (177,931 in + 1,150,464 cached + 23,703 out incl. 13,273 reasoning); trusted flash-lite (72,466 in + 36,964 out) | 1,400,861 | 60,667 | 0.143 | 0.231 |
| 8 | 2026-09-20 | 3b | model compare: 5 attack samples, gpt-4.1-mini | untrusted gpt-4.1-mini (236,921 in + 1,743,744 cached + 18,880 out); trusted flash-lite (126,250 in + 67,196 out) | 2,106,915 | 86,076 | 0.339 | 0.570 |
| 9 | 2026-09-20 | 4 | Step 4 smoke: 1 K1 campaign | untrusted gpt-5-mini (20,229 in + 180,736 cached + 4,463 out); trusted flash-lite | 202,478 | 5,639 | 0.019 | 0.589 |
| 10 | 2026-09-20 | 4 | Step 4 run A: 9 campaigns (confounded, K1 not instruction-matched) | untrusted gpt-5-mini (494,129 in + 3,091,200 cached + 86,329 out); trusted flash-lite (29,038 in + 26,920 out) | 3,614,367 | 113,249 | 0.387 | 0.976 |
| 11 | 2026-09-20 | 4 | Step 4 run B: 10 campaigns (instruction-matched, the result) | untrusted gpt-5-mini (507,007 in + 2,777,728 cached + 79,714 out); trusted flash-lite (30,240 in + 2,040 cached + 26,396 out) | 3,316,975 | 106,110 | 0.369 | 1.346 |
| 12 | 2026-09-20 | 4b | 15 campaigns, per-commit + cumulative monitor | untrusted gpt-5-mini (929,113 in + 6,708,992 cached + 153,242 out); trusted flash-lite (142,159 in + 16,332 cached + 188,210 out) | 7,796,596 | 341,452 | 0.796 | 2.142 |
| 13 | 2026-09-20 | 4b | post-hoc robust re-scoring, ~297 judge calls, no agents re-run | flash-lite (~594k in + ~1.04M out) | 594,000 | 1,040,000 | 0.475 | 2.617 |
| 14 | 2026-09-20 | 4c | 6 backdoor campaigns, delivery fixed, side task 6/6 | untrusted gpt-5-mini (375,261 in + 2,603,008 cached + 59,538 out); trusted flash-lite (55,544 in + 4,082 cached + 123,388 out) | 3,037,895 | 182,926 | 0.333 | 2.950 |
| 15 | 2026-09-20 | 4c | robust re-scoring, 72 judge calls | flash-lite (~144k in + ~252k out) | 144,000 | 252,000 | 0.115 | 3.065 |

Cached input tokens for OpenAI models are billed at 25% of the input price on OpenRouter (nano: $0.025/M).
Costs are computed as `input_tok * in_price + cached_tok * cache_price + output_tok * out_price` from Inspect's reported
`ModelUsage`, because OpenRouter's `total_cost` field came back `None` through Inspect.
