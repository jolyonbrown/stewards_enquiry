# PLAN.md — Steward's Enquiry build plan

Two-day build. Day 1 = Phases 0–2 (local, offline). Day 2 = Phases 3–4
(deployed, release exercise) + README. If any phase overruns its timebox by
more than an hour, cut scope from that phase — never from the invariants in
CLAUDE.md.

Working rule: tick boxes as completed, and record actual results under each
phase's **AC notes**.

---

## Phase 0 — Scaffold and hello-agent (timebox: 1.5h)

- [x] Verify current AgentCore CLI behaviour (`agentcore --help`, current docs);
      record any deviations from CLAUDE.md in `docs/DEVIATIONS.md`
- [x] Scaffold the project with the AgentCore CLI (agent name
      `StewardsEnquiry` — no apostrophe, CLI/resource names won't like it),
      Python, direct code deploy, HTTP protocol
- [x] Merge scaffold with this repo's layout; `uv sync`; ruff + pytest wired
- [x] Minimal entrypoint: `/invocations` echoes a canned response;
      `/ping` healthy
- [x] `agentcore dev` runs; local invoke returns the canned response

**Acceptance:** fresh clone → `uv sync` → `agentcore dev` → local invoke
succeeds with zero AWS credentials.

**AC notes:** Done 2026-07-14. Major CLI drift found and recorded in
`docs/DEVIATIONS.md`: the Python starter toolkit is deprecated; scaffolded
with `@aws/agentcore` 0.24.1 (npm), `--build CodeZip` (the successor to
"direct code deploy"), HTTP protocol, Strands/Bedrock, no memory. Deploys are
CDK-managed via `agentcore/`. Python pinned 3.12 (runtime now supports up to
3.14). `uv sync` + `uv run pytest` (1 test) + ruff all green offline.
`agentcore dev --logs --skip-deploy` with AWS env vars stripped: `GET /ping` →
`{"status":"Healthy"}`; `POST /invocations {"finding_id":"ssh-bruteforce"}` →
canned echo. Gotchas for later phases: `agentcore dev` manages its own venv
inside the app dir (root pyproject uses an editable path dep, NOT a uv
workspace), and CLI invokes wrap text input as `{"prompt": "<string>"}`.

---

## Phase 1 — Tools against fixtures (timebox: 2.5h)

- [x] `get_finding` loads from `fixtures/findings/` by finding `id`
- [x] `lookup_ip` reads `fixtures/ip_reputation.json` with `_default` fallback
- [x] `query_cloudtrail` filters `fixtures/cloudtrail_events.json` by
      principal + time window, capped at 50 events
- [x] `propose_containment` appends to `proposals.jsonl` and returns the
      proposal; unit test asserts it can never emit `status` other than
      `pending_approval`
- [x] Structured JSON log line per tool call (tool, input digest, duration,
      outcome)
- [x] `scripts/verify_readonly.sh` greps for mutating boto3 verbs; wire into
      pytest or a make target
- [x] Unit tests per tool; all deterministic and offline

**Acceptance:** `pytest` green offline; each tool demonstrably deterministic.

**AC notes:** Done 2026-07-16 on branch `phase-1`. 45 tests green offline
(44 new + Phase 0's). One module per tool in `app/stewards_enquiry/tools/`;
`telemetry.traced` decorator emits one JSON line per call (tool, 12-char
input digest — never the raw input — duration, outcome, including on error).
Determinism choice: `query_cloudtrail`'s window anchors on the principal's
newest fixture event, not wall-clock now, so offline runs don't decay as
fixtures age. `propose_containment` returns exactly the verdict-schema
`proposed_actions` shape (status/requires_approval are constants, no
parameter can override them; enum-sync test pins it to the schema); the JSONL
record adds proposal_id + created_at audit fields, path overridable via
STEWARD_PROPOSALS_PATH. STEWARD_LIVE=1 raises NotImplementedError (stretch C)
rather than silently serving fixtures. verify_readonly.sh covers boto3
snake_case and aws-CLI kebab-case mutating verbs, excludes vendored code,
runs inside pytest, and was probe-tested to confirm it actually fails on a
planted `stop_instances` call.

---

## Phase 2 — Triage loop and verdicts (timebox: 3h)

- [x] Strands agent (or boto3 fallback per CLAUDE.md timebox rule) with the
      four tools and the triage-policy system prompt
- [x] Verdict construction + validation against `schemas/verdict.schema.json`;
      fail-closed path emits `needs_human` on validation failure
- [ ] Run all three fixture findings end-to-end; save outputs to
      `tests/golden/`
- [ ] Intended outcomes (assert loosely — verdict class, not exact wording):
  - `ssh-bruteforce` → `true_positive`, proportionate containment proposal
    (isolate the instance's security group)
  - `crypto-mining` → `true_positive`, high severity, stop-instance proposal
  - `tor-recon` → `needs_human` (plausibly an authorised scan), no
    containment proposal
- [x] Golden-file test comparing verdict structure and classes (written;
      skips until goldens are recorded)

**Acceptance:** three findings in, three schema-valid verdicts out, matching
the intended verdict classes; `proposals.jsonl` contains only
`pending_approval` entries.

**AC notes:** Offline parts done 2026-07-16 on branch `phase-2` (80 tests
green + 3 golden skips, no credentials). `prompts.py` encodes the triage
policy; `triage.py` builds a fresh Strands agent per triage (model injectable,
default Claude-on-Bedrock via BEDROCK_MODEL_ID env — verified strands `tool()`
wraps the traced functions with correct specs); `verdict.py` validates or
fails closed to `needs_human` (broad catch: model errors, unparseable output,
schema violations — never free text, never an exception); `main.py` accepts
both `{"finding_id": ...}` and the CLI `{"prompt": "<text>"}` wrapper. Every
triage emits a structured verdict log line. **Remaining for acceptance:** run
`uv run python scripts/record_goldens.py` with AWS creds + Bedrock model
access to record `tests/golden/*.verdict.json` (script refuses to record
fail-closed verdicts), then confirm the golden test enforces the intended
classes and `proposals.jsonl` holds only `pending_approval` entries.

---

## Phase 3 — Deploy to AgentCore Runtime (timebox: 2.5h)

- [ ] Confirm target region supports AgentCore (prefer `eu-west-2`, fall back
      `us-west-2`); set `AWS_REGION`
- [ ] Discover and set `BEDROCK_MODEL_ID` (current Claude Sonnet cross-region
      inference profile via `aws bedrock list-inference-profiles`); confirm
      model access is enabled in the Bedrock console
- [ ] Create the read-only execution role per CLAUDE.md IAM section
- [ ] `agentcore deploy` (direct code deploy); resolve any ARM64 wheel issues
      with the uv platform flags from CLAUDE.md
- [ ] Enable observability (CloudWatch Transaction Search per current docs);
      confirm `agentcore logs` and traces show the full tool sequence
- [ ] Remote `agentcore invoke` for all three findings matches local golden
      verdict classes

**Acceptance:** remote invoke ≡ local behaviour; one screenshot/export of a
trace showing the tool chain saved to `docs/`.

**AC notes:** _(fill in)_

---

## Phase 4 — Cut a release, prove the rollback (timebox: 1.5h)

The point of this phase is to *perform* the version/endpoint model, not read
about it.

- [ ] Create a pinned endpoint `demo` pointing at the current version (V_n)
- [ ] Make a small, visible change (e.g. add a `steward_version` field or a
      one-word prompt tweak); `agentcore deploy` → creates V_n+1; confirm
      DEFAULT moved and `demo` did not
- [ ] Invoke via `demo` (old behaviour) and DEFAULT (new) side by side
- [ ] Repoint `demo` → V_n+1; verify; then repoint back to V_n to prove
      rollback is symmetrical
- [ ] Record the full command transcript in `docs/RELEASE-NOTES.md`

**Acceptance:** transcript demonstrates pinned-endpoint promotion and instant
rollback with no rebuild.

**AC notes:** _(fill in)_

---

## Wrap — README and demo script (timebox: 1h)

- [ ] Fill README "What I learned" with ≥3 specific, honest observations
- [ ] Verify the 2-minute demo script below end-to-end, once, cold

**Demo script (for a 30-minute interview, target ≤2 minutes):**

1. `cat fixtures/findings/ssh-bruteforce.json | head` — "GuardDuty finding in."
2. Local invoke → show the verdict JSON — "enriched, reasoned, schema-valid."
3. `cat proposals.jsonl` — "containment is *proposed*, pending approval —
   the agent cannot act, by construction. Read-only role, enforced by CI."
4. Remote invoke against the `demo` endpoint — "same agent on AgentCore
   Runtime, session-isolated."
5. Show the trace — "every tool call audited."
6. One line on the release model — "versions are immutable, endpoints are
   pointers; rollback is a repoint."

---

## Stretch goals (only after Phase 4)

- [ ] **A — Memory:** AgentCore Memory recalls prior verdicts by finding type
      ("seen this before; last verdict was FP") and cites them in the summary
- [ ] **B — Gateway:** expose `lookup_ip` via an AgentCore Gateway target from
      a small OpenAPI spec, so the Gateway primitive has been touched too
- [ ] **C — Live findings:** `STEWARD_LIVE=1` path against real sample
      findings (`aws guardduty create-sample-findings`) in a sandbox account
- [ ] **D — Approval transition:** a `review_proposal` helper that flips a
      proposal to `approved`/`rejected` in `proposals.jsonl` — still executing
      nothing; the state machine ends at "a human decided"

## Risks / known sharp edges

- AgentCore CLI is evolving quickly — Phase 0's doc check is load-bearing
- ARM64 native wheels (mitigation in CLAUDE.md)
- Bedrock model access not enabled in the target account/region (check early
  in Phase 3, not last)
- Endpoint repoint is atomic — no weighted canary; note it in RELEASE-NOTES
  as a deliberate observation, not a surprise
