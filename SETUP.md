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
| Docker daemon | not running at session start (`/var/run/docker.sock` missing), **started manually** with `nohup dockerd --storage-driver=vfs &` (we are root; `dockerd`, `containerd`, `runc` are present). After start: `docker run --rm alpine:3.20 echo ok` pulls through the proxy and runs; `docker compose version` reports v5.1.1. | Docker-sandboxed settings can run here. The daemon is per-session and must be restarted in a fresh container. Storage driver is `vfs` (no overlayfs), so image builds are slow and disk-hungry. |

## What broke

Nothing broke during install. Docker had to be started by hand (see table). No Anthropic or
OpenAI key is present, so models must be routed through OpenRouter (`openrouter/...` model
strings in Inspect) for Step 3 onward.

## Restarting Docker in a fresh session

```bash
nohup dockerd --storage-driver=vfs > /tmp/dockerd.log 2>&1 &
sleep 8 && docker info | grep 'Server Version'
```
