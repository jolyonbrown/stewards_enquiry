# Steward's Enquiry

*An agentic security-alert triage demo on Amazon Bedrock AgentCore — detection
and response as an end-to-end agentic workflow, with the human veto built in,
not bolted on.*

## What it does

A GuardDuty finding goes in. The agent enriches it — IP reputation, recent
CloudTrail activity for the implicated principal — reasons about severity and
false-positive likelihood, and emits a structured, schema-validated
**verdict**. Where containment is warranted, it emits a **proposal**
(`status: pending_approval`), never an action.

```
GuardDuty finding ──▶ enrich ──▶ reason ──▶ verdict + proposed containment
                                                 │
                                                 ▼
                                        a human decides
```

## Why it's built this way

The interesting problem in agentic security operations isn't getting a model
to read an alert — it's giving an agent enough authority to be useful without
giving it enough to be dangerous. This demo takes a position:

- **Attenuated authority.** The agent's execution role is read-only; the
  ability to act simply does not exist in its permission set. Enforced by IAM
  and by a CI check that fails the build on any mutating SDK call.
- **Proposals, not actions.** Containment is a structured artefact awaiting
  approval — the human stays in the loop as an architectural property, not a
  policy document.
- **Fail closed.** A verdict that doesn't validate becomes `needs_human`,
  never free text.
- **Audit as a first-class output.** Every tool call is logged and traced;
  the observability trail *is* part of the demo.

## Quickstart (offline — no AWS account needed)

### Prerequisites

- **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **AgentCore CLI** — Node 18+, then `npm install -g @aws/agentcore`

> ⚠️ Install the CLI from **npm**, not pip. The pip package
> (`bedrock-agentcore-starter-toolkit`) is the deprecated starter toolkit and
> installs a different, unsupported `agentcore` binary. Details in
> `docs/DEVIATIONS.md`.

Python 3.12 is fetched automatically by uv (pinned in `.python-version`) —
it does not need to be preinstalled.

### Run

```bash
uv sync                              # one-time: create the venv, install deps

agentcore dev --logs --skip-deploy   # terminal 1: local dev server on :8080

# terminal 2: invoke with a fixture finding id (see fixtures/findings/)
curl -s -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"finding_id": "ssh-bruteforce"}'
```

`--skip-deploy` stops `agentcore dev` attempting to provision cloud resources
first; `--logs` gives a plain log stream instead of the browser chat UI.
Until Phase 2 lands, the response is a canned echo — the triage loop
replaces it.

### Test

```bash
uv run pytest        # offline, deterministic
uv run ruff check .
```

Three bundled findings, three intended outcomes:

| Fixture | Finding type | Expected verdict |
|---|---|---|
| `ssh-bruteforce` | `UnauthorizedAccess:EC2/SSHBruteForce` | `true_positive` + isolate-SG proposal |
| `crypto-mining` | `CryptoCurrency:EC2/BitcoinTool.B!DNS` | `true_positive`, high severity + stop-instance proposal |
| `tor-recon` | `Recon:IAMUser/TorIPCaller` | `needs_human` — plausibly an authorised scan |

That third one matters: **`needs_human` is a success state.** An agent that
knows when not to be confident is the one you can deploy.

## Deploying to AgentCore Runtime

```bash
# TODO(Phase 3): region + model discovery, execution role, deploy, invoke
```

## The release model, demonstrated

Runtime versions are immutable; endpoints are named pointers. Releases are a
pointer move; rollback is the same move backwards.

See `docs/RELEASE-NOTES.md` for the recorded transcript of cutting V(n+1),
verifying a pinned endpoint stayed put, promoting it, and rolling it back —
no rebuild involved.

## What I learned

<!-- TODO(Wrap): ≥3 honest, specific observations about AgentCore's sharp
edges. Sharp edges, not marketing. -->

- _(pending)_
- _(pending)_
- _(pending)_

## Scope, honestly

Two-day reference build. No UI, no database, no queue, no approval workflow
execution — the state machine deliberately ends at "a human decided". The
verdict schema (`schemas/verdict.schema.json`) and the invariants in
`CLAUDE.md` are the load-bearing parts; everything else is replaceable.

---

*On the name: in horse racing, a steward's enquiry is the review held after
the race when something looked wrong — the result stands or falls on human
judgment, after the evidence is examined. Which is exactly the design.*
