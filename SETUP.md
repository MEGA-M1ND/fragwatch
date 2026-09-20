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
nohup dockerd > /tmp/dockerd.log 2>&1 &     # default driver resolves to overlay2 here
sleep 8 && docker info | grep -E 'Server Version|Storage Driver'
```

**Do not use `--storage-driver=vfs`.** I first started the daemon with vfs; vfs stores every
image layer as a full filesystem copy, and a 13-of-32-layer partial build of the ~1.8 GB
`iac-fast` image consumed ~30 GB and exhausted the session's writable-disk allowance
(`df` showed 38 GB used, 0 available, then even tool output failed with ENOSPC). Pruning
Docker recovered the space. The kernel supports overlay and `/var/lib/docker` is ext4, so
overlay2 works and is what the daemon picks by default.

## Building sandbox images behind the egress proxy

Build containers cannot reach the session proxy at `127.0.0.1:38275` and do not trust its CA
(`/root/.ccr/README.md`). What worked:

```bash
docker build --network host \
  --build-arg HTTPS_PROXY="$HTTPS_PROXY" --build-arg https_proxy="$HTTPS_PROXY" \
  --build-arg NO_PROXY="$NO_PROXY"       --build-arg no_proxy="$NO_PROXY" \
  -t <tag> <context-with-ca-bundle.crt>
```

with a Dockerfile preamble that `COPY`s `/root/.ccr/ca-bundle.crt` into
`/usr/local/share/ca-certificates/`, runs `update-ca-certificates`, and declares the proxy and
CA variables as `ARG`s so they exist only at build time. See `src/docker/`.

**`deb.debian.org` is denied by the organisation egress policy** (403 on CONNECT), so any
Dockerfile step that runs `apt-get` fails here. Reachable: Docker Hub, `pypi.org`,
`files.pythonhosted.org`, `registry.npmjs.org`, `nodejs.org`, `raw.githubusercontent.com`.
