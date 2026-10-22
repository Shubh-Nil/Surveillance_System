# PM/TL orchestrator

This is SETUP-001 infrastructure. Live execution is disabled. No research task has been started.

Use Python 3.11 in a Conda `agents` environment when Conda is available (Conda is absent on this host). `python3.11 .agents/orchestrator.py mock-test` runs isolated mock tests. `status`, `run --max-tasks 1 --mock`, `stop`, `resume`, and `answer-supervisor QUESTION_ID RESPONSE` are available. Mock responses must be a JSON array at `.agents/runtime/mock_responses.json`. Runtime state, history and summaries live in `.agents/runtime/` and are ignored by Git. `resume` reports the checkpoint for manual reconciliation; it never retries an uncertain invocation automatically.

For later activation, extract PM and TL instructions from Part B of `Interactive_AI_Agents.pdf` into two separate prompt text files outside tracked source. Set `pm_prompt_path` and `tl_prompt_path` in config. Verify Codex CLI version, authentication, sandbox isolation, role prompts, and permissions; then explicitly set `live_execution_enabled=true`. The installed CLI supports `codex exec`, `--sandbox`, `--output-schema`, `--output-last-message`, `--model`, and `model_reasoning_effort` configuration. PM uses read-only sandbox; TL uses workspace-write. Both are separate subprocesses. No exact model names were assumed. API billing is separate from Plus; this adapter does not fall back to API keys.

Only TL1 may run. Each invocation is checkpointed and a lock prevents concurrent writers. Usage limits pause without retry. Unknown outcomes and submitted jobs require manual evidence reconciliation. PM ACCEPT never merges main. Protect main with GitHub pull-request/check rules and non-merge-capable bot credentials; shared Supervisor credentials cannot distinguish actors. The CLI sandbox alone does not provide strong path-level isolation for TL. Keep live mode disabled until an isolated TL worktree and credentials are verified.

## SETUP-002 verification

Conda is installed at `/home/vis-comp/30007665/miniconda3`. The dedicated environment interpreter is `/home/vis-comp/30007665/miniconda3/envs/agents/bin/python`. Invoke it by absolute path for non-interactive processes. The only direct external dependency is declared in `.agents/requirements.txt`. Recreate with `conda create -n agents python=3.11 pip`, then run that environment's `python -m pip install -r .agents/requirements.txt`. Base was not modified.

Run tests with `/home/vis-comp/30007665/miniconda3/envs/agents/bin/python .agents/orchestrator.py mock-test`.

Readiness limitations: automatic mock handoff works; live remains disabled. Role prompts are not installed. Resume only reports status and does not reconcile artifacts. Stop cannot interrupt the current lock-holding process. Runtime is local to this checkout rather than shared across worktrees. JSONL and state are individually durable, but not a single crash-atomic transaction. The branch precheck does not constrain arbitrary Git commands run by a live TL. Evidence references are not independently verified. These require resolution before live activation; passing mock tests does not establish production readiness.

After these blockers are resolved, role prompts configured and the Supervisor explicitly enables live execution, the first cycle command is:

`/home/vis-comp/30007665/miniconda3/envs/agents/bin/python .agents/orchestrator.py run --max-tasks 1`

This command is currently gated off. PM acceptance never grants merge authorization.
