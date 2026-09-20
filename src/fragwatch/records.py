"""Canonical, versioned result records with provenance.

Two rules shape this schema:

1. **Evaluator-only labels are segregated.** `MonitorInput` holds exactly what a monitor (or a future
   deployable correlation method) may see. `EvaluatorLabels` holds attack membership, objective names
   and campaign identity. Nothing in `EvaluatorLabels` may be passed to a correlation method, or the
   evaluation silently becomes oracle-assisted.
2. **Missing stays missing.** A verdict that failed to parse is recorded with its failure status, never
   coerced to a benign score and never dropped, so every denominator can be stated exactly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SCHEMA_VERSION = "fragwatch.record/1"

Provenance = Literal["historical", "exploratory", "confirmatory"]


def content_hash(text: str | None) -> str:
    if text is None:
        return "sha256:none"
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


@dataclass
class RunProvenance:
    """Where a set of records came from, and under which code and protocol."""

    run_id: str
    provenance: Provenance
    protocol_version: str
    source_log: str
    code_commit: str | None = None
    scoring_config_fingerprint: str | None = None
    prompt_version: str | None = None
    monitor_model: str | None = None
    dependency_versions: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class MonitorInput:
    """Monitor-visible context only. Must contain no attack labels."""

    view: Literal["per_commit", "cumulative"]
    diff_hash: str
    diff_lines: int
    task_description_hash: str
    diff_ref: str = ""  # durable pointer (log + campaign + index), not the content itself


@dataclass
class EvaluatorLabels:
    """Ground truth for analysis only. Never an input to a monitor or correlation method."""

    is_attacker_commit: bool
    condition: str
    side_task_name: str | None
    main_task_name: str
    fragment_delivered: bool | None = None
    fragment_retried: bool | None = None


@dataclass
class MonitorRecord:
    """One monitor evaluation of one input, with every attempt preserved."""

    schema_version: str
    run_id: str
    campaign_id: str
    event_id: str
    commit_index: int
    monitor_input: MonitorInput
    labels: EvaluatorLabels
    value: float | None
    status: str
    n_attempts: int
    n_valid: int
    spread: float | None
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    legacy_value: float | None = None  # what the live XML-only path recorded, if known
    legacy_agrees: bool | None = None  # fail-closed pairing check
    unresolved_reason: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass
class CampaignRecord:
    """Campaign-level outcomes. Campaigns are the experimental units."""

    schema_version: str
    run_id: str
    campaign_id: str
    condition: str
    k_agents: int
    side_task_name: str | None
    side_task_success: bool | None
    main_tasks: dict[str, bool]
    n_commits: int
    fragments_delivered: int | None
    fragments_retried: int | None
    agent_limit_hits: int
    agent_timeouts: int
    untrusted_input_tokens: int = 0
    untrusted_output_tokens: int = 0
    untrusted_cached_tokens: int = 0
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class RecordStore:
    """Append-only JSONL store, one directory per run. Refuses to overwrite silently."""

    def __init__(self, root: Path | str, run_id: str, *, allow_existing: bool = False):
        self.dir = Path(root) / run_id
        if self.dir.exists() and not allow_existing:
            raise FileExistsError(
                f"{self.dir} already exists; pass allow_existing=True or choose another run_id. "
                "Derived results are never overwritten implicitly (see AUDIT.md issue 4)."
            )
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id

    def write_provenance(self, prov: RunProvenance) -> None:
        (self.dir / "provenance.json").write_text(json.dumps(asdict(prov), indent=1, sort_keys=True))

    def write_monitor(self, records: list[MonitorRecord]) -> None:
        with (self.dir / "monitor_records.jsonl").open("w") as fh:
            for r in sorted(records, key=lambda x: (x.campaign_id, x.commit_index,
                                                    x.monitor_input.view)):
                fh.write(r.to_json() + "\n")

    def write_campaigns(self, records: list[CampaignRecord]) -> None:
        with (self.dir / "campaign_records.jsonl").open("w") as fh:
            for r in sorted(records, key=lambda x: x.campaign_id):
                fh.write(r.to_json() + "\n")

    @staticmethod
    def load(run_dir: Path | str) -> tuple[dict, list[dict], list[dict]]:
        d = Path(run_dir)
        prov = json.loads((d / "provenance.json").read_text())
        def _read(name):
            p = d / name
            return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()] if p.exists() else []
        return prov, _read("monitor_records.jsonl"), _read("campaign_records.jsonl")
