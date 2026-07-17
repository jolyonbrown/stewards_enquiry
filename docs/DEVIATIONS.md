# Deviations from CLAUDE.md / PLAN.md

CLAUDE.md was written 2026-07-13 and warned it might already be stale. It was.
Each entry: what the brief said, what is actually true (verified 2026-07-14),
and what we did.

| # | Brief said | Actually true (2026-07-14) | What we did |
|---|---|---|---|
| 1 | Use the AgentCore CLI (implicitly the Python `bedrock-agentcore-starter-toolkit`) | That toolkit prints "no longer supported"; the current CLI is `@aws/agentcore` on npm ("new features are only accessible in the AgentCore CLI") | Installed `@aws/agentcore` 0.24.1 (node v25.2.1), uninstalled the Python toolkit |
| 2 | "Direct code deploy (zip, ≤250 MB, no Docker)" via CLI flags | Deployment is declarative: `build: "CodeZip"` in `agentcore/agentcore.json`, deployed by `agentcore deploy` through CDK. No manual zip handling | Scaffolded with `--build CodeZip`; CDK project lives in `agentcore/cdk/` |
| 3 | "AgentCore direct code deploy supports Python 3.10–3.13" | Schema now accepts `PYTHON_3_10`–`PYTHON_3_14` (and Node 18/20/22 — TypeScript agents exist now); scaffold defaulted to `PYTHON_3_14` | Pinned `PYTHON_3_12` and `.python-version` 3.12 per the brief — inside both ranges |
| 4 | `.gitignore` assumed old-toolkit state files (`.bedrock_agentcore.yaml`, ignored `deployed-state.json`) | Project state is `agentcore/agentcore.json` + `aws-targets.json`, both meant to be committed; the CLI's own `.gitignore` deliberately commits `agentcore/.cli/deployed-state.json` too | Removed the stale root ignores; `agentcore/.gitignore` now governs that directory |
| 5 | Phase 4 uses "pinned endpoints" via CLI endpoint commands | Current model: `runtimeEndpoints` array in `agentcore.json` (RuntimeEndpoint → named pointer at a runtime version) plus an `agentcore promote` command | Noted for Phase 4; no action yet |
| 6 | "Do not hardcode a Bedrock model ID from memory" | The official scaffold itself hardcodes `global.anthropic.claude-sonnet-4-5-20250929-v1:0` in `model/load.py` | Discarded that module; Phase 2 reads `BEDROCK_MODEL_ID` from the environment |
| 7 | Scaffold expected to be minimal | Scaffold ships an MCP client, a skills fetcher, a session LRU cache, and streaming plumbing | Trimmed to a canned entrypoint per the thin-slice invariant; Phase 2 adds only the four tools |

| 8 | "Confirm model access is enabled in the Bedrock console" (Phase 3 checklist) | The Bedrock "Model access" page was retired (observed 2026-07-16): serverless foundation models auto-enable on first invocation in all commercial regions. Anthropic models may additionally require first-time users to submit use-case details; Marketplace-served models need one invocation by a user with Marketplace permissions | No manual enablement step; we confirm access by invoking (playground or first `record_goldens.py` run) and submit the Anthropic use-case form if prompted |

Other observations worth keeping:

- `agentcore create` enforces project names: start with a letter, alphanumeric,
  max 23 chars. `StewardsEnquiry` fits.
- `agentcore dev` auto-deploys project resources before starting unless
  `--skip-deploy` is passed — relevant for the offline-first invariant.
- The old `agentcore launch` is now `agentcore deploy` (rename happened inside
  the deprecated toolkit already).
- `agentcore dev` creates and manages its own venv *inside* `codeLocation`
  (spawns `.venv/bin/uvicorn` there), so the app's pyproject must be
  standalone — making it a uv workspace member redirects the install to the
  root venv and dev startup fails with ENOENT. Hence the editable path
  dependency in the root pyproject instead of a workspace.
- `agentcore dev "<text>"` / `agentcore invoke "<text>"` wrap the argument as
  `{"prompt": "<text>"}` before POSTing. Phase 2's payload parsing must accept
  both a raw finding payload (curl style) and a JSON string under `"prompt"`.
