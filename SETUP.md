# SETUP.md — Phase 1 environment setup

Date: 2026-09-20. Host: Linux 6.18 container (Claude Code remote environment).

## Commands that worked

```bash
git init                                   # repo was already initialised on branch claude/tender-dirac-kd8vdj
uv venv .venv --python 3.11                # uv 0.8.17, system Python 3.11.15
source .venv/bin/activate
uv pip install control-arena inspect-ai    # no version pins; latest on PyPI resolved
uv pip freeze > requirements.lock.txt      # exact resolved set, committed
```

## Versions installed

| Package | Version |
|---|---|
| control-arena | 19.0.0 |
| inspect-ai | 0.3.266 |
| Python | 3.11.15 |
| uv | 0.8.17 |

Full resolved dependency set is in `requirements.lock.txt`.

## Import and CLI checks

```
python -c "import control_arena, inspect_ai; print(control_arena.__version__, inspect_ai.__version__)"
# -> 19.0.0 0.3.266

control-arena --version   # control-arena, version 19.0.0
control-arena --help      # commands: env, eval, monitor, solution-viewer, trajectory
inspect --version         # 0.3.266
```

All succeeded.

## What is available for running models

| Thing | Status | Consequence |
|---|---|---|
| `OPENROUTER_API_KEY` | set, `GET /api/v1/models` returns 200 | Cheap models are reachable via OpenRouter (`openrouter/<vendor>/<model>` in Inspect). |
| `ANTHROPIC_API_KEY` | **not set** (`ANTHROPIC_BASE_URL` is set but the endpoint returns 401 unauthenticated) | Direct Anthropic models cannot be used from this container. |
| `OPENAI_API_KEY` | not set | Direct OpenAI models cannot be used. |
| Docker client | present (Engine 29.3.1 CLI) | — |
| Docker daemon | **not running** (`/var/run/docker.sock` missing) | Any ControlArena setting whose sandbox is Docker cannot run here. See ENVIRONMENT_AUDIT.md for which settings that is. |

## What broke

Nothing broke during install. The two blockers above (no Docker daemon, no Anthropic key) are
environmental and affect Step 3 onward, not Step 1.
