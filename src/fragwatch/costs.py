"""Spend accounting with conservative headroom, across every model call in a run.

Scope, per the task's requirement that accounting cover everything:
  * **attacker calls** — the untrusted agent's generations, including its tool loop,
  * **monitor calls** — every judge call, including the extra calls of `n_calls`,
  * **retries** — delivery retries re-run an agent, so its calls appear again in the log and are
    counted; monitor retries likewise,
  * **in-flight usage** — a run killed mid-request may not have flushed usage, so a reserve is added.

Figures are **modelled**: Inspect's reported `ModelUsage` multiplied by a hand-entered price sheet.
OpenRouter's own `total_cost` came back `None` through Inspect, so no invoice-derived number is
available. Every reported figure says so.
"""

from __future__ import annotations

import argparse
import glob
from dataclasses import dataclass

from inspect_ai.log import read_eval_log

# USD per token. Cached input is billed at a fraction of input; see COSTS.md for provenance.
PRICES = {
    "openrouter/openai/gpt-5-mini": (0.25e-6, 0.025e-6, 2.00e-6),
    "openrouter/openai/gpt-4.1-mini": (0.40e-6, 0.10e-6, 1.60e-6),
    "openrouter/openai/gpt-4.1-nano": (0.10e-6, 0.025e-6, 0.40e-6),
    "openrouter/google/gemini-2.5-flash-lite": (0.10e-6, 0.025e-6, 0.40e-6),
}
# Reserve for requests that may have been in flight when a run ended, and for any model whose price is
# unknown. Deliberately generous: the point is to stop early, not to be exact.
IN_FLIGHT_RESERVE_FRACTION = 0.20
UNKNOWN_MODEL_RATE = 2.00e-6


@dataclass
class Spend:
    modelled_usd: float
    reserve_usd: float
    by_model: dict[str, float]
    tokens: dict[str, tuple[int, int, int]]
    unknown_models: list[str]
    n_samples: int

    @property
    def worst_case_usd(self) -> float:
        return self.modelled_usd + self.reserve_usd


def spend_for_logs(paths: list[str]) -> Spend:
    by_model: dict[str, float] = {}
    tokens: dict[str, tuple[int, int, int]] = {}
    unknown: list[str] = []
    n = 0
    for p in paths:
        log = read_eval_log(p)
        # Per-sample usage is summed rather than the header total, so a run that never finalised its
        # header (killed, timed out) still contributes its real spend.
        for s in log.samples or []:
            n += 1
            for m, v in (s.model_usage or {}).items():
                cr = v.input_tokens_cache_read or 0
                fresh_in = max(0, v.input_tokens)
                rate = PRICES.get(m)
                if rate is None:
                    if m not in unknown:
                        unknown.append(m)
                    rate = (UNKNOWN_MODEL_RATE, UNKNOWN_MODEL_RATE, UNKNOWN_MODEL_RATE)
                cost = fresh_in * rate[0] + cr * rate[1] + v.output_tokens * rate[2]
                by_model[m] = by_model.get(m, 0.0) + cost
                ti, tc, to = tokens.get(m, (0, 0, 0))
                tokens[m] = (ti + fresh_in, tc + cr, to + v.output_tokens)
    modelled = sum(by_model.values())
    return Spend(modelled, modelled * IN_FLIGHT_RESERVE_FRACTION, by_model, tokens, unknown, n)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("globs", nargs="+", help="eval log globs, e.g. 'data/p1_*/*.eval'")
    ap.add_argument("--cap-usd", type=float, default=10.0)
    ap.add_argument("--fail-over-cap", action="store_true")
    a = ap.parse_args()
    paths = sorted({p for g in a.globs for p in glob.glob(g)})
    sp = spend_for_logs(paths)
    print(f"logs: {len(paths)}, campaigns: {sp.n_samples}")
    for m, c in sorted(sp.by_model.items()):
        ti, tc, to = sp.tokens[m]
        print(f"  {m}: in={ti:,} cached={tc:,} out={to:,} -> ${c:.4f}")
    print(f"modelled spend:      ${sp.modelled_usd:.4f}")
    print(f"in-flight reserve:   ${sp.reserve_usd:.4f} ({IN_FLIGHT_RESERVE_FRACTION:.0%})")
    print(f"worst case:          ${sp.worst_case_usd:.4f} of ${a.cap_usd:.2f} cap")
    print(f"remaining headroom:  ${a.cap_usd - sp.worst_case_usd:.4f}")
    if sp.unknown_models:
        print(f"WARNING unpriced models charged at the conservative rate: {sp.unknown_models}")
    print("Figures are modelled from Inspect ModelUsage and a hand-entered price sheet, not invoices.")
    if a.fail_over_cap and sp.worst_case_usd > a.cap_usd:
        raise SystemExit(f"worst-case spend ${sp.worst_case_usd:.4f} exceeds cap ${a.cap_usd:.2f}")


if __name__ == "__main__":
    main()
