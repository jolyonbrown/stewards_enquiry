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

One-time setup: an AWS account with Bedrock Anthropic access enabled, and
your own 12-digit account id + region in `agentcore/aws-targets.json`.

```bash
aws sso login --profile <your-profile>      # or any AWS credential method
export AWS_PROFILE=<your-profile> AWS_REGION=eu-west-2

# discover a current Claude inference profile; set it as BEDROCK_MODEL_ID
# in agentcore/agentcore.json envVars
aws bedrock list-inference-profiles --region "$AWS_REGION"

agentcore deploy -y                         # CDK: runtime, role, telemetry (~5 min)
bash scripts/e2e_remote.sh --no-deploy      # 3 live triages, checked against goldens
```

The generated execution role and its honest audit (including three documented
surplus-privilege follow-ups) are in `docs/EXECUTION-ROLE.md`; a full trace of
one cloud triage is in `docs/trace-ssh-bruteforce.json`.

## The release model

Runtime versions are immutable; endpoints are named pointers. Releases are a
pointer move; rollback is the same move backwards. Performing that exercise
end-to-end (pinned `demo` endpoint, V(n+1), symmetric rollback) is PLAN.md
Phase 4 — the one remaining planned deliverable.

## What I learned

- **Verify the platform against itself, not its docs.** In one three-day
  build: the pip starter toolkit announced its own deprecation (the real CLI
  is `@aws/agentcore` on npm, with a completely different CDK-based model),
  and the Bedrock "Model access" console page was retired mid-build. Eight
  deviations from the written brief are recorded in `docs/DEVIATIONS.md`;
  the habit of checking live CLI output before writing code paid for itself
  twice in the first hour.
- **CodeZip packaging was painless; the packaged filesystem is not.** The
  feared ARM64 native-wheel problem never materialised. What nearly shipped
  broken instead: anything your code reads must physically live inside
  `codeLocation` — our repo-root fixtures and schema would have
  `FileNotFoundError`'d in production. Caught in review, fixed with the real
  files inside the app dir and a layout-pinning test.
- **Generated IAM is convenient, not least-privilege.** The deploy
  construct's default execution role included write access to a config store
  the project never uses, log-read access across *all* runtimes in the
  account, and invoke rights on every Bedrock model. All bounded, none
  exploitable here — but "trust the vendor default" and "least privilege"
  are different policies. Audited and tracked in `docs/EXECUTION-ROLE.md`.
- **Schema validation cannot catch lies — only trace-grounding can.** Under
  ambiguity the model produced a confident, schema-valid, *false* evidence
  claim ("zero CloudTrail events" for a principal the fixture showed as
  active — it had queried the wrong key and dressed the empty result as
  fact). An independent review caught it against the fixtures; the fix
  cross-checks every verdict against what the tools actually returned, and
  fabrication now fails closed. That one finding justified the whole
  review-gate process.

## Scope, honestly

Two-day reference build. No UI, no database, no queue, no approval workflow
execution — the state machine deliberately ends at "a human decided". The
verdict schema (`schemas/verdict.schema.json`) and the invariants in
`CLAUDE.md` are the load-bearing parts; everything else is replaceable.

---

*On the name: in horse racing, a steward's enquiry is the review held after
the race when something looked wrong — the result stands or falls on human
judgment, after the evidence is examined. Which is exactly the design.*
