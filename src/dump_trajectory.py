"""Dump an Inspect .eval log from a ControlArena run into a readable markdown file.

Usage: python src/dump_trajectory.py <path.eval> <out.md>

Writes: task metadata, every message (system/user/assistant/tool) with tool calls and
per-step monitor suspicion scores from assistant-message metadata, the captured
submission_diff from the store, the sample scores, and model usage.
"""

import json
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for c in content:
        t = getattr(c, "text", None)
        if t is None:
            t = getattr(c, "reasoning", None)
        parts.append(t if t is not None else f"[{getattr(c, 'type', 'content')}]")
    return "\n".join(parts)


def main(eval_path: str, out_path: str) -> None:
    log = read_eval_log(eval_path)
    out = []
    out.append(f"# Trajectory dump of `{Path(eval_path).name}`\n")
    out.append(f"status: **{log.status}**  \ntask: `{log.eval.task}`  \nmodel: `{log.eval.model}`  \nmodel_roles: `{log.eval.model_roles}`\n")
    if log.stats:
        out.append("## Model usage\n")
        out.append("| model | input | output | total | cache_read |\n|---|---|---|---|---|")
        for m, u in log.stats.model_usage.items():
            out.append(f"| {m} | {u.input_tokens} | {u.output_tokens} | {u.total_tokens} | {u.input_tokens_cache_read} |")
        out.append("")
    if not log.samples:
        out.append("**No samples in log.**")
        Path(out_path).write_text("\n".join(out))
        return
    for s in log.samples:
        out.append(f"## Sample `{s.id}` (epoch {s.epoch})\n")
        md = s.metadata or {}
        out.append(f"- main_task: `{md.get('main_task_name')}`\n- side_task: `{md.get('side_task_name')}`\n- eval_mode: `{md.get('eval_mode')}`")
        if s.error:
            out.append(f"- **error:** `{s.error.message[:500]}`")
        if s.limit:
            out.append(f"- **limit hit:** `{s.limit}`")
        out.append("\n### Scores\n")
        for k, v in (s.scores or {}).items():
            out.append(f"- **{k}**: value=`{v.value}`\n  - explanation: {(v.explanation or '').strip()[:1500]}")
        out.append("\n### Per-step suspicion (assistant messages with monitor metadata)\n")
        out.append("| step | tool calls | suspicion | reason (truncated) |\n|---|---|---|---|")
        step = 0
        for m in s.messages:
            if isinstance(m, ChatMessageAssistant):
                step += 1
                tc = ", ".join(t.function for t in (m.tool_calls or [])) or "(none)"
                meta = m.metadata or {}
                sus = meta.get("suspicion_score")
                reason = str(meta.get("reason", "")).replace("\n", " ")[:160]
                out.append(f"| {step} | {tc} | {sus if sus is not None else ''} | {reason} |")
        out.append("\n### Full transcript\n")
        step = 0
        for m in s.messages:
            if isinstance(m, ChatMessageAssistant):
                step += 1
                out.append(f"#### [{step}] assistant\n")
                txt = content_text(m.content).strip()
                if txt:
                    out.append(txt + "\n")
                for t in m.tool_calls or []:
                    out.append(f"**tool call** `{t.function}`\n```json\n{json.dumps(t.arguments, indent=1)[:4000]}\n```")
                meta = m.metadata or {}
                if "suspicion_score" in meta:
                    out.append(f"> monitor suspicion = **{meta['suspicion_score']}**\n> {str(meta.get('reason','')).strip()[:2000]}\n")
            elif isinstance(m, ChatMessageTool):
                err = f" **ERROR: {m.error.message[:300]}**" if m.error else ""
                out.append(f"#### tool result `{m.function}`{err}\n```\n{content_text(m.content)[:3000]}\n```")
            else:
                out.append(f"#### {m.role}\n```\n{content_text(m.content)[:6000]}\n```")
        diff = (s.store or {}).get("submission_diff")
        out.append("\n### submission_diff (from store)\n")
        out.append("```diff\n" + (diff if diff else "(none)") + "\n```")
    Path(out_path).write_text("\n".join(out))
    print("wrote", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
