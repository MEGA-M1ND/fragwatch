# ENVIRONMENT_AUDIT.md — ControlArena 19.0.0 reconnaissance

Source of truth: the installed package at
`.venv/lib/python3.11/site-packages/control_arena/` (version 19.0.0) and
`.venv/lib/python3.11/site-packages/inspect_ai/` (0.3.266). All paths below are relative to
those two roots unless stated. Line numbers are from the installed files on 2026-09-20.

Method: I read the core interface files myself. The 16 settings were surveyed by three parallel
sub-agents reading the source; I then spot-checked the claims that this audit leans on (iac,
iac_fast, vllm, infra, bash, apps) against the files directly. One sub-agent claim was wrong
and is corrected below (§1, iac/iac_fast "git repo inside the sandbox": it is not).

---

## 0. Bottom line (for the two Phase 1 questions)

**Q1. Can a stock ControlArena setting serve as a shared-repository sabotage environment with
multiple sequential agents and a shared side task?**

- **Shared mutable repository with a diff captured at the end: yes**, in five settings
  (`iac`, `iac_fast`, `infra`, `vllm`, `swebench`, plus the private-repo `eval_sabotage`).
- **Multiple sequential agents on shared state: no, not natively.** Nothing in ControlArena or
  Inspect persists sandbox state across samples, and nothing lets a second agent start from a
  first agent's end state. The unit of evaluation is one sample = one fresh sandbox = one agent
  = one main task (+ optionally one side task) = one end-of-trajectory diff. See §3.
- **Shared side task across agents: no.** Datasets are the cross product (main task × side
  task); there is no notion of a campaign of K main tasks sharing one side task.
- **What is missing is bounded and sits above the setting layer**, not inside it: a custom
  micro-protocol (or dataset builder) that runs K agents *within one Inspect sample* on the same
  sandbox, gives each a different main task and the shared side task, and records a per-agent
  diff ("commit") between agents. §3.3 states precisely what would have to be written. This is
  an extension on top of a stock setting, not a replacement environment. Whether that counts as
  "stock" enough to proceed is the user's call at this gate.

**Q4 (asked in the prompt as item 4). Is there a FakeLab-style mock lab monorepo?** No. The
closest in spirit is `iac`/`iac_fast`: a mock frontier lab's AWS Organization as a single AWS
CDK app (one stack, ~15 Python files). `bash_arena` has a 5-service mock network but no source
repo. `infra` is one Helm chart plus a training script. None is a ~9-service application
monorepo.

**Recommended setting for Step 3: `iac_fast`.** Reasons in §4.

---

## 1. Settings inventory

Sixteen settings ship (`settings/` directory). Summary table, then per-setting notes.

| Setting (`get_name()`) | Sandbox | Codebase in sandbox | Main tasks | Side tasks | Persistent editable FS | git repo in sandbox | End diff captured | Sequential multi-agent | FakeLab-like |
|---|---|---|---|---|---|---|---|---|---|
| `agentdojo` | local (in-memory env) | none | 101 (external pkg) | ~42 injection tasks | no | no | no | no | no |
| `apps` | docker `python:3.4`, `network_mode: none` | none | ~10k APPS problems (HF) | 1 (`insert_backdoor`) | no (agent has no tools) | no | no | no | no |
| `bash` | docker alpine, **egress on** | none | 257 (local JSON) | 1 (`download_malware`, real pastebin URL) | yes | no | no | no | no |
| `bash_arena` | docker, per-sample 5-service compose | none (sysadmin box) | 640 (HF) | 4 | yes | no | no | no | partial (mock infra network, not a repo) |
| `bigcodebench` | docker, `network_mode: none` | none | 1140 / 148 hard (HF) | 1 (`insert_backdoor`) | no | no | no | no | no |
| `data_poisoning` | local | none | 98 generated | 7 password-lock | no | no | no | no | no |
| `eval_sabotage` | docker (bare) | **private** RepliBench fork, cloned over SSH | 18 | 1 × 6 methods | yes | yes | yes | no | no |
| `iac` | docker, image baked | mock lab AWS CDK org at `/repo` | 5 | 9 | yes | **no** | yes | no | closest |
| `iac_fast` | docker (k8s optional), image baked | same CDK org at `/repo` | 5 | 9 | yes | **no** | yes | no | closest |
| `infra` | **k8s (kind)** | `ca-k8s-infra` Helm/K8s repo cloned to `/workspace/training-infra` | 9 + 9 extended | 2 + 1 extended | yes | yes | yes | no | partial |
| `rogue_eval` | docker, `network_mode: none` | none (one `solution.py`) | 26 | 1 | no | no | no | no | no |
| `sae_interp_sabotage` | local | none | 22 | 1 | no | no | no | no | no |
| `shade_arena` | local (in-memory) | none; needs **private** `shade_arena` pkg | n/a (pkg missing) | 1 per pair | no | no | no | no | no |
| `swe_django_sidetask` (`swebench`) | docker, per-instance SWE-bench image | real Django at `/testbed` | 18 | 18 (CWE-mapped) | yes | yes | yes | no | no |
| `vllm` | docker, 4 cpu / 5 GB, image must be built | real vLLM at `/workspace` | 32 validated (HF) | 15 | yes | yes | yes | no | no (single real repo) |

Base classes every setting builds on:

- `Setting` ABC: `settings/_setting.py:18`. Abstract: `get_dataset` (`:66`), `get_agent_tools`
  (`:152`), `get_scorers` (`:175`), `get_sandbox_config` (`:184`). Optional hooks:
  `setup_environment() -> Solver | None` (`:132`), `post_submission() -> Solver | None` (`:143`).
  Filters `filter_main_task_names` / `filter_side_task_names` (`:47-55`, applied `:77-130`).
- `ControlTask` dataclass (`settings/_control_task.py:26-40`): `instructions`, `score`,
  `setup_environment`, `sandbox`, `files`. `MainTask` adds `git_code_ref`, `qa_dir` (`:43-65`).
  There is no `SideTask` class; side tasks are `ControlTask` (infra, vllm) or plain dict entries
  (iac, iac_fast: `settings/iac_fast/objectives.py`).
- `ControlTaskMetadata` (`_control_task_metadata.py:10-66`): `main_task_description`,
  `side_task_description`, `setting_description`, `eval_mode`, `setting_name`,
  `main_task_name`, `side_task_name`, `metadata`. Frozen; stored on the Inspect `Sample`.
  Accessed inside agents with `control_task_metadata()` (`:85-114`).

### 1.1 Per-setting notes (only what matters for this project)

**`iac` / `iac_fast`** (`settings/iac/control_iac_setting.py:86`, `settings/iac_fast/setting.py:102`).
- Environment: docker compose, one service, image baked from a Dockerfile that `COPY setting/ /repo/`
  (`settings/iac/Dockerfile:18`; `settings/iac_fast/docker/Dockerfile:33`). Codebase = a Python
  AWS CDK app modelling a mock frontier lab's AWS Organization: `core_infrastructure/root_account/organisation.py`,
  `components/organisation_units.py`, `components/scp_monitoring.py`, and 10 Service Control
  Policy modules under `components/service_control_policies/{all_accounts,weight_security}/`.
  README (`settings/iac/setting/README.md:1-9`) frames it as "guard-rails that keep research,
  model weights and customers safe".
- **Correction to sub-agent report:** `/repo` is *not* a git repository. Neither
  `settings/iac/setting` nor `settings/iac_fast/docker/setting` contains `.git`, and nothing in
  the Dockerfiles runs `git init`. The end-of-trajectory diff is computed on the host by
  `get_diff_from_ref_dir` (`utils/_git_diff_utils.py:37-107`), which copies the sandbox dir out and
  runs `git diff --no-index` against the reference dir (`:85-107`), excluding `cdk.out`, `.venv`,
  `.git`, `tests` (`settings/iac_fast/solvers.py:29-40`). Result goes to
  `state.store["submission_diff"]` (`:45`).
- Main tasks (5) and side tasks (9) are strings in `settings/iac_fast/objectives.py:3-28`, `:30-67`.
  Main: `add_interpretability_ou`, `create_billing_alarm`, `tag_security_policies`,
  `org_config_aggregator`, `enforce_mandatory_tags_scp`. Side: `disable_fsx_deny_policy`,
  `disable_fsx_deny_policy_interpretability_ou`, `check_in_cdk_out_directory`,
  `detach_mfa_requirement_policy`, `allow_public_s3_policy`, `open_internet_egress_restricted_ous`,
  `create_backdoor_admin_role`, `exempt_ec2_public_ip_check`, `change_policy_to_version_one`.
  Verified: `IACFastSetting().stats` reports 5 main, 9 side, 45 combinations
  (`settings/iac_fast/setting.py:182-183`).
- Dataset: honest = one sample per main task; attack = full cross product, sample id
  `MT_<main>_ST_<side>` (`settings/iac_fast/setting.py:61-99`).
- Scoring: programmatic. `combined_pytest_scorer` uploads the reference pytest suite only at
  scoring time, runs `pytest -m <main_task_name>` and `-m <side_task_name>` (attack mode), then
  deletes the tests (`settings/iac_fast/scorers.py:236-282`). Tests synthesise the CDK template
  and assert on it; no AWS account or cluster needed. Reference tests:
  `settings/iac_fast/docker/setting/tests/test_<task>.py` (one per main and side task).
- Tools: `iac_fast` = `bash()`, daemon-backed `text_editor()`, `cdk_ls()`, `cdk_synth()`
  (`settings/iac_fast/setting.py:153-158`). An approval policy rejects any bash command matching
  `cdk\b` (`:117-123`, `settings/iac_fast/approvers.py:8-37`). `iac` = `bash_session()`,
  `text_editor()`, `cdk_ls()` (`settings/iac/control_iac_setting.py:111-112`).
- Requirements: docker only. `iac_fast` image is ~1.8 GB (README); ours must be built locally
  (`x-local: true`, `settings/iac_fast/docker/compose.yml:4`). `mem_limit: 2g` (`:16`).
- Safety: no real credentials, no CVEs, no network use at runtime (pure CDK synth). Side tasks
  are policy weakenings inside a mock org.

**`infra`** (`settings/infra/infra_setting.py:46`).
- Default sandbox is Kubernetes (`sandbox: Literal["docker","k8s","none"] = "k8s"`, `:79`);
  the "docker" option maps to a bare `python:3.13` test compose, not a usable environment
  (`:146`). `check_setup()` requires a kind cluster literally named `control-arena`
  (`settings/infra/utils/utils.py:98-119`), created by `control-arena env setup --env infra`
  (`settings/infra/README.md:35-40`), README recommends ≥32 GB RAM. Not runnable in this
  container.
- Codebase: `https://github.com/UKGovernmentBEIS/ca-k8s-infra.git` at a pinned ref, cloned per
  sample to `/workspace/training-infra` (`settings/infra/config.py:8-16`,
  `settings/infra/task/solvers.py:24-72`). It *is* a git repo when `should_include_git=True`
  (`infra_setting.py:74`). Diff via `get_diff_from_git_ref` (`task/solvers.py:79-93`).
- 18 main tasks (`settings/infra/main_tasks/__init__.py:24-47`), 3 side tasks including
  `secret_exfiltration_aws_credentials` (fake creds, moto mock AWS) and `k8s_network_vulnerability`
  (`settings/infra/side_tasks/__init__.py:19-27`). Scoring needs the live cluster.
- README security warning: sandboxing "not sufficient for agents which are capable and
  independently malicious" (`settings/infra/README.md:42-44`). Fake AWS keys hardcoded in
  `settings/infra/agent.yaml:6-9`.

**`vllm`** (`settings/vllm/vllm_setting.py:46`).
- Docker, image `vllm-control-arena:final` must be built by `build-docker.sh` (clones vLLM and
  builds its dev Dockerfile; large). Real vLLM at `/workspace`, a git repo, checked out per sample
  to the main task's parent commit (`settings/vllm/task/solvers.py:22-49`). Diff via
  `get_diff_from_git_ref` (`:54-73`). 32 validated main/side combos from HF dataset
  `RoganInglis/vllm-control-arena` (`settings/vllm/config.py:47-144`). 15 side tasks
  (`settings/vllm/side_tasks/__init__.py:65-81`).
- Scoring is an LLM judge (`combined_pr_scorer`) for most tasks; 3 "sync" side tasks have
  programmatic scorers and a second nginx WebDAV `file-server` service.
- Safety flags: main compose has no `network_mode: none` (`settings/vllm/compose.yml`); several
  side tasks describe exfiltration to attacker-chosen external URLs (`exfiltrate_env_secrets`,
  `weight_exfiltration_loading`, `redirect_inference_requests`). A dummy SSH private key is
  planted for `exfiltrate_ssh_keys_sync`. No real CVEs or credentials, but this is the most
  offensive-flavoured setting and needs an egress-blocked network if used. Not recommended.

**`swe_django_sidetask`** (`settings/swebench/swebench_setting.py:75`).
- Per-instance SWE-bench docker images, real Django at `/testbed` (git). 18 instances, each
  paired with one CWE-mapped side task (XSS, SSRF, auth bypass, `eval` injection, …) from HF
  `schaeff/SWE-django-sidetasks`, scored by AST/pytest checks. Requires the `swebench` extra.
- Safety: side tasks are real vulnerability *classes* planted in a real OSS codebase.
  `allow_internet=True` default (`settings/swebench/dataset.py:98`). Excluded under the
  "no real CVEs" rule to be safe; they are not live CVEs but they are real-world weaknesses.

**`bash`** (`settings/bash/bash_setting.py:60`). The side task downloads and executes
`https://pastebin.com/raw/BHNWfMqr` for real; compose deliberately leaves egress on
(`settings/bash/compose.yml:10-11`). **Flagged. Do not use.**

**`bash_arena`**: 640 sysadmin tasks on a 5-service mock network (router DNAT fakes externals;
planted secrets are the AWS docs placeholder keys and fabricated tokens). No source repo, no diff.
Interesting as a mock-infra shape but not a shared-repo setting.

**`eval_sabotage`**, **`shade_arena`**: need private repos/packages; `shade_arena` import fails in
this venv. Excluded.

**`apps`, `bigcodebench`, `data_poisoning`, `rogue_eval`, `sae_interp_sabotage`, `agentdojo`**:
no persistent editable repository (single-submission or in-memory environments). Excluded.

---

## 2. How monitors, protocols, and scorers are represented

Everything is an Inspect `Agent` (`async (AgentState, list[Tool]) -> AgentState`) built through
the `@control_agent` decorator (`_control_agent.py:131-239`), which turns a builder function into
a serialisable, hashable Pydantic class registered for the CLI. Micro-protocols, policies and
monitors all share this shape and can nest arbitrarily (`:145-147`).

### 2.1 Monitors

- Interface: `Monitor` protocol (`monitor/_monitor.py:42-61`):
  `async __call__(state: AgentState, tools) -> MonitorResponse`. `MonitorResponse` is
  `{suspicion_score: float, reason: str, model_usage}` (`monitor/_types.py:9-22`).
- The `@monitor` helper (`monitor/_monitor.py:64-99`) converts attack tools to their
  monitor view (`:87`), calls the monitor function, and **writes the response into the metadata
  of the last assistant message** (`:92-97`). That is where every downstream scorer looks.
- **What a monitor receives:** the full `AgentState` (message history up to and including the
  assistant message being scored). What it *uses* is decided by the prompt formatter
  (`PromptFormatter = Callable[[ControlTaskMetadata, Sequence[ChatMessage], str], str]`,
  `monitor/_types.py:43`):
  - `last_tool_calls_prompt_formatter` (default for `basic_monitor`,
    `monitor/_basic_monitor.py:41-44`): only the tool calls of the last assistant message,
    rendered as `function: {json args}` lines (`monitor/_last_tool_calls_prompt_formatter.py:51-62`).
    So the default step-wise monitor sees **one action**, not a diff and not the transcript.
  - `full_trajectory_prompt_formatter_markdown` / `_xml`
    (`monitor/_full_trajectory_prompt_formatter.py:365-417`): the whole transcript.
  - Neither formatter sees the filesystem or a git diff. A diff-based monitor exists only as a
    *scorer* (§2.3, `git_diff_monitor`).
- `basic_monitor_builder` (`monitor/_basic_monitor.py:26-175`): prompt from
  `monitor/prompts/default.txt` (0–10 scale, placeholders `{task_description}` and
  `{tool_calls}`), normalised to 0–1 by `MonitorScoreRange` (`monitor/_types.py:25-40`).
  Returns 0.0 if the message has no tool calls (`:133-137`). Model chosen by `model_role`
  (default `"trusted"`).
- `ensemble_monitor_builder` (`monitor/_ensemble_monitor.py`) averages several samples.

### 2.2 Micro-protocols and policies

- `trusted_monitoring_builder` (`micro_protocol/_trusted_monitoring.py:11-43`): run the policy,
  then if the output has tool calls run the monitor on the live state (`:36-41`). Non-intervening.
  Others: `defer_to_trusted`, `defer_to_resample`, `trusted_editing` (`micro_protocol/__init__.py`).
- `untrusted_policy_builder` (`policy/_untrusted_policy.py:17-57`) dispatches on
  `eval_mode` to `honest_policy` or `attack_policy`.
- `attack_policy_builder` (`policy/_attack_policy.py:26-124`) replaces the system prompt with
  `policy/prompts/attack_policy.txt` (formatted with `main_task_description`,
  `side_task_description`, `setting_description`, `:90-96`) and generates from the untrusted model.
  Optional `ephemeral_reminder` re-injects the side task before each call (`:101-112`).
- `fixed_policy_builder` (`policy/_fixed_policy.py:14-59`) replays a fixed tool-call list, from a
  `TrajectoryProvider` (`policy/_trajectory_provider.py:17-70`: `.eval` file or `.jsonl`).
  Useful for deterministic replays but not for state handoff.

### 2.3 Scorers (`scorers/__init__.py`)

- `max_suspicion_scorer` (`scorers/_max_suspicion_scorer.py:9-38`): max of
  `message.metadata["suspicion_score"]` over assistant messages. This is the "per-trajectory max".
- `git_diff_monitor` (`scorers/_diff_monitor.py:32-85`): LLM over `state.store["submission_diff"]`
  (`:56`) with a 1–10 prompt (`:9-28`). One diff per sample.
- `end_of_trajectory_monitor(monitor)` (`scorers/_end_of_trajectory_monitor.py:36-102`): runs any
  monitor once over the full message history.
- Post-hoc replay: `run_monitor_for_messages` (`eval/_run_monitors.py:49-149`) runs a monitor on
  the prefix ending at **each** assistant message (`:129-136`) and writes scores back into message
  metadata. `evaluate_monitor_post_hoc` (`eval/_eval_different_monitor.py:19-51`) does that for a
  whole `.eval` log. This is exactly the "replay monitors over identical trajectories" primitive
  the eventual experiment needs, and it exists stock.

### 2.4 Eval assembly and models

- `get_control_task` (`eval/_control_eval_def.py:61-156`) builds an Inspect `Task`:
  solver chain = `setting.setup_environment()` → `control_solver` → `setting.post_submission()`
  (the last is run in a `finally` so the diff is captured even on limit errors, `:44-58`,
  `:106-112`); dataset = `setting.get_filtered_dataset(mode)` (`:142`); sandbox =
  `setting.get_sandbox_config()` (`:145`); scorers = setting scorers + `monitoring_scorers`.
- `control_solver` (`_control_solver.py:118-234`) wraps the micro-protocol in Inspect's `react`
  loop (`agent_scaffolds/_react_scaffold.py:44-74`) with a step counter (`:57-114`) and the
  setting's submit tool.
- `ControlEvalConfig` (`eval/_control_eval_config.py:45-256`): `untrusted_model`,
  `trusted_model`, limits, `max_sandboxes`, `epochs`, `log_dir`. Default models come from env
  vars `UNTRUSTED_MODEL` / `TRUSTED_MODEL`, else `anthropic/claude-sonnet-4-6` and
  `openai/gpt-5.4-mini` (`protocol_arg_defaults.py:15-16`, `:42-66`). Both defaults are
  unreachable here; we will set both to OpenRouter strings.

---

## 3. Sequential multi-agent support (the critical capability)

### 3.1 What exists

Nothing. A grep of the package for `sequential|multi.?agent|handoff|prior_state|snapshot|checkpoint`
finds only unrelated hits (resampling strategy, data_poisoning task names, infra model
checkpoints). No setting, solver, or protocol accepts a prior sandbox's state.

### 3.2 Why: the sample lifecycle

Inspect creates the sandbox per sample in `init_sandbox_environments_sample`
(`inspect_ai/util/_sandbox/context.py:258-300`: `sample_init` → copy sample files → run setup
script) and destroys it in `cleanup_sandbox_environments_sample` (`:303-312`). ControlArena's
`setup_environment` solvers then reset the repo to a clean ref inside that fresh sandbox
(`settings/vllm/task/solvers.py:38`, `settings/infra/task/solvers.py:56`); for `iac`/`iac_fast` the
clean state is simply the baked image. The only artefact that survives a sample is the message
history plus one `submission_diff` string in the store.

So "agent N sees the state agent N-1 left behind" has no carrier: the state lives in a container
that is gone before the next sample starts.

### 3.3 Closest things, and precisely what is missing

Closest primitives (all stock):

1. **Within one sample, the sandbox persists across every model call.** A micro-protocol is
   just an agent; it can call any number of sub-agents in sequence, each with its own fresh
   `AgentState(messages=[...])`, all executing tools in the same `sandbox()`. Inspect also
   ships `handoff()` / `run()` (`inspect_ai/agent/_handoff.py:19-`, `agent/__init__.py`) for
   multi-agent within a sample, with per-agent message filters.
2. **`ControlTask.files` / `setup_environment` per task** can seed a sandbox with arbitrary files,
   and `setup_environment(git_code_ref_override=...)` in vllm can start from any ref
   (`settings/vllm/task/solvers.py:22-24`). Neither chains samples.
3. **`get_diff_from_ref_dir` / `get_diff_from_git_ref`** produce a diff between the sandbox and
   a reference; they can be called at any point, not only post-submission.
4. **Post-hoc monitor replay** over stored messages (§2.3) already supports scoring each
   assistant message independently.

What would have to be written to run "K sequential agents, one shared side task, per-commit
monitoring" on top of `iac_fast`:

- **(a) A campaign dataset builder.** One Inspect `Sample` per campaign, whose metadata carries
  an ordered list of K main tasks (drawn from the 5 stock ones, with repetition when K > 5) and
  the one shared side task. Stock `ControlTaskMetadata` has a single `main_task_description`;
  the list goes in its free-form `metadata` dict (`_control_task_metadata.py:63-66`).
- **(b) A sequential micro-protocol.** Loops i = 1..K: builds a fresh message history with the
  system prompt + main task i (attack mode: the attack prompt with the shared side task and, per
  Makins et al., what the previous agents already did), runs the stock react loop for that agent
  until it submits, then records a "commit". No stock scaffold does the loop; it is a new
  `@control_agent`, roughly 60–100 lines.
- **(c) A commit primitive.** `/repo` is not a git repo (§1.1). Either `git init` it in a
  `setup_environment` solver and `git commit -a` after each agent, or snapshot with
  `get_diff_from_ref_dir` after each agent and diff consecutive snapshots. Either gives a
  per-agent diff to store in message metadata.
- **(d) Per-commit monitor.** Stock `basic_monitor` scores actions, not commits. A per-commit
  monitor is a `basic_monitor` with a custom `prompt_formatter` that renders the commit's diff
  (and main task) instead of tool calls; `git_diff_monitor`'s prompt is a starting point. Roughly
  20 lines. The Makins et al. Appendix C.3 prompts would slot in here if provided.
- **(e) Scoring.** Stock `combined_pytest_scorer` scores one main task and one side task per
  sample. For a campaign it would need to run `pytest -m` for each of the K main tasks and the
  side task; the test files already exist per task, so this is a loop over the stock scorer's
  internals (`settings/iac_fast/scorers.py:159-`).

None of (a)–(e) modifies ControlArena; they are additions in `src/`. The environment itself
(image, codebase, tools, tests) stays stock. This is not a replacement environment, but it is
experiment code, and the prompt says not to write experiment code before this gate.

### 3.4 Caveat on the shared side task in `iac_fast`

The 9 side tasks are each a single logical change (delete one SCP statement, add one role, …).
Fragmenting one across K agents is possible but the pieces are small; e.g.
`create_backdoor_admin_role` could be split into "add an IAM construct file", "wire it into the
stack", "widen its policy", "attach to every account in the OU". Whether a K=9 split still
produces individually innocuous commits in a ~15-file codebase is exactly what Step 4 would test,
and it is a legitimate way the effect could fail to reproduce here. The main tasks also number
only 5, so K=9 requires repeating main tasks or writing new ones; repeating is the honest option
and should be stated in FRAGMENTATION_REPRO.md if used.

---

## 4. Recommendation for Step 3

Use **`iac_fast`**, attack mode, one sample, stock `trusted_monitoring` micro-protocol with the
stock `basic_monitor`, plus `max_suspicion_scorer` and `git_diff_monitor` as monitoring scorers.

Why over the alternatives:

| | `iac_fast` | `iac` | `vllm` | `infra` | `swebench` |
|---|---|---|---|---|---|
| Runs in this container | yes (docker) | yes (docker) | probably, but needs a very large image build (vLLM dev Dockerfile) at 4 cpu / 5 GB per sandbox | **no** (kind cluster, 32 GB) | yes, but needs `swebench` extra and per-instance images |
| Scoring | programmatic pytest, no LLM | same, slower | LLM judge (extra cost, less reproducible) | live cluster | programmatic |
| Safety | mock org, no egress needed | same | exfil-flavoured side tasks, open network | fake creds, README warning | real CWE weaknesses in real Django |
| Fits "mock lab" framing | mock frontier lab AWS org | same | real OSS repo | training cluster infra | real OSS repo |
| Cost per sample | small: 15-file repo, fast tools | small | large context (vLLM) | n/a | medium |

Known constraints for the Step 3 run:

- The `iac-fast:latest` image must be built locally (~1.8 GB, Node + CDK). With the `vfs`
  storage driver here that is slow but should work; if the build fails through the proxy, `iac`'s
  image is the same size and shape, so it would fail the same way.
- Models: both roles must be set explicitly to `openrouter/...` strings (no Anthropic/OpenAI
  keys). Plan: untrusted = `openrouter/openai/gpt-4.1-nano`, trusted (monitor) =
  `openrouter/google/gemini-2.5-flash-lite`; step up to `gpt-4.1-mini` only if nano cannot
  drive the CDK tools. Reported in COSTS.md either way.
- `iac_fast` bars the agent from calling `cdk` via bash; the model must use `cdk_ls`/`cdk_synth`.
  A weak model may thrash on this. That is a Step 3 observation, not something to tune around.

---

## 5. Safety review summary

| Setting | Concern | Verdict |
|---|---|---|
| `bash` | side task fetches and executes a real pastebin URL; egress intentionally on | do not use |
| `vllm` | exfiltration-style side tasks, open network in main compose, planted dummy SSH key | do not use without egress block; not needed |
| `swebench` | real CWE weaknesses in real Django; internet allowed by default | excluded |
| `infra` | fake AWS keys (moto), README says sandbox insufficient for capable malicious agents | not runnable here anyway |
| `eval_sabotage` | dangerous-capability eval content; private repo | excluded |
| `iac` / `iac_fast` | side tasks weaken mock security policies in a synthetic CDK org; no creds, no network, no CVEs | acceptable |

Nothing in `iac`/`iac_fast` touches a network outside the sandbox at runtime. The image build
does fetch npm/pip packages, which is ordinary.
