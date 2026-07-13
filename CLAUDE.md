# CLAUDE.md — Steward's Enquiry

## What this is

**Steward's Enquiry** is a security-alert triage agent running on Amazon Bedrock
AgentCore Runtime. It takes an Amazon GuardDuty finding as input, enriches it
with context (IP reputation, CloudTrail activity), reasons about severity and
false-positive likelihood, and produces a structured **verdict** with
**proposed** containment actions. It never executes anything: every action is a
proposal awaiting human approval.

This is a two-day reference build demonstrating that detection and response can
be agentified *without* surrendering control — governance expressed in code,
not in a slide. Optimise for **legibility over completeness**: this repo will
be read by security engineers. Small, boring, obvious code wins.

## Non-negotiable invariants

These override anything else in this file or in PLAN.md. If a phase goal
conflicts with an invariant, the invariant wins and the phase goal shrinks.

1. **Read-only, everywhere.** No AWS SDK call anywhere in this codebase may
   create, modify, or delete anything. Allowed API verbs: `Get*`, `List*`,
   `Describe*`, `Lookup*`. Nothing else. This applies to live mode, tests,
   and any helper scripts.
2. **Propose, never act.** `propose_containment` returns a structured proposal
   with `status: pending_approval` and appends it to a local
   `proposals.jsonl`. There is no code path that executes a containment
   action. Do not build an "approve and execute" path — approval workflow is
   explicitly out of scope for v1 (see PLAN.md stretch goals for the
   non-executing state transition).
3. **Verdicts validate or fail closed.** Every verdict must validate against
   `schemas/verdict.schema.json`. On validation failure, emit a minimal
   verdict with `verdict: needs_human` and `escalate_to_human: true` rather
   than raising or emitting free text.
4. **Offline-first.** The default mode runs entirely from `fixtures/` with no
   AWS credentials and no network calls. Live mode (real GuardDuty /
   CloudTrail reads) sits behind `STEWARD_LIVE=1`. The demo must work on a
   train.
5. **Everything is traceable.** Every tool invocation logs a structured JSON
   line (tool name, input digest, duration, outcome). When deployed, AgentCore
   Observability / OTel traces must show the full tool sequence for a triage.
6. **Thin slice.** No web UI, no database, no queues, no config framework.
   Input is a finding, output is a verdict. Anything else is scope creep.

## Freshness warning — read before writing any AgentCore code

This brief was written on **2026-07-13**. AgentCore, its CLI, and the Strands
SDK are moving fast; details below may already be stale. Before Phase 0:

- Run `agentcore --help` and skim the current command set.
- Check the current docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/
- Trust live docs and CLI output over this file. Record any deviation from
  this brief in `docs/DEVIATIONS.md` (create it) with a one-line reason.

Do not hardcode a Bedrock model ID from memory. Read it from the
`BEDROCK_MODEL_ID` env var and document how to discover a current Claude
Sonnet cross-region inference profile:
`aws bedrock list-inference-profiles --region "$AWS_REGION"`.

## Architecture

```
                 ┌──────────────────────────────────────────────┐
                 │        AgentCore Runtime (session-isolated)   │
                 │                                              │
 GuardDuty       │  ┌────────────┐     ┌──────────────────┐     │
 finding ───────▶│  │ triage      │────▶│ Claude on Bedrock │     │   verdict.json
 (fixture or     │  │ entrypoint  │◀────│ (tool-use loop)   │     │──▶ + proposals.jsonl
 live GetFinding)│  └────────────┘     └──────┬───────────┘     │   (pending_approval)
                 │                            │ tools            │
                 │        ┌───────────────────┼───────────────┐  │
                 │        ▼           ▼       ▼           ▼   │  │
                 │  get_finding  lookup_ip  query_     propose_ │  │
                 │  (read-only)  (fixture/  cloudtrail continment│ │
                 │               feed)      (read-only) (NO-OP)  │  │
                 └──────────────────────────────────────────────┘
                        every step → structured logs + OTel traces
```

## Stack and conventions

- **Python 3.12** (AgentCore direct code deploy supports 3.10–3.13). `uv` for
  env and deps, `ruff` for lint/format, `pytest` for tests.
- **Agent framework: Strands Agents** with a Claude model on Bedrock — it is
  the AgentCore-native path and what the platform's own examples use.
  **Timebox rule:** if Strands costs more than one hour of integration
  friction, fall back to a plain `boto3` Bedrock converse tool-use loop. The
  invariants live in our tools, not the framework, so the swap is cheap.
- **Entrypoint:** `app/stewards_enquiry/main.py`, implementing the AgentCore
  Runtime HTTP contract (`POST /invocations`, `GET /ping`) via the AgentCore
  Python SDK app wrapper. Tools live in `app/stewards_enquiry/tools/`, one
  module each, pure functions where possible.
- **Deployment:** AgentCore CLI, **direct code deploy** (zip, ≤250 MB, no
  Docker). Region from `AWS_REGION`; prefer `eu-west-2` if AgentCore supports
  it at build time, otherwise `us-west-2` — check current region support,
  don't assume.
- **ARM64 gotcha:** Runtime is ARM64-only and validates native binaries in the
  zip. If any dependency ships native wheels, resolve with
  `uv pip install --python-platform aarch64-manylinux2014 --only-binary=:all:`.
  Prefer pure-Python deps to avoid the problem entirely.
- Type hints throughout. Small modules. No cleverness.

## Tools — exact behaviours

| Tool | Signature | Fixture mode (default) | Live mode (`STEWARD_LIVE=1`) | Hard rules |
|---|---|---|---|---|
| `get_finding` | `(finding_id: str) -> dict` | Load matching JSON from `fixtures/findings/` | `guardduty:GetFindings` | Must be the agent's first tool call |
| `lookup_ip` | `(ip: str) -> dict` | Lookup in `fixtures/ip_reputation.json`, `_default` on miss | Same fixture file (a real feed is a stretch goal) | Never call external reputation APIs in v1 |
| `query_cloudtrail` | `(principal: str, hours: int = 24) -> list[dict]` | Filter `fixtures/cloudtrail_events.json` | `cloudtrail:LookupEvents` | Read-only; cap at 50 events returned |
| `propose_containment` | `(action: str, target: str, justification: str, risk_if_wrong: str) -> dict` | Append to `proposals.jsonl`, return proposal | Identical — **live mode changes nothing** | `requires_approval` always `true`; `status` always `pending_approval`; action must be from the enum in the verdict schema |

## Triage policy (encode this in the system prompt)

- Always call `get_finding` first; never reason from the finding ID alone.
- Corroborate before concluding: a verdict of `true_positive` needs at least
  two independent pieces of evidence (e.g. finding + IP reputation, or
  finding + CloudTrail pattern).
- `needs_human` is a first-class outcome, not a failure. Use it when: the
  principal's intent is plausibly legitimate (e.g. a scanner service account
  that might be an authorised pentest), evidence conflicts, or severity ≥ 7
  with confidence < 0.7.
- Proposals must be proportionate: an SSH brute-force against one instance
  justifies isolating that instance's security group, not stopping the fleet.
- Every verdict `summary` is written for a SOC analyst: plain language, ≤ 4
  sentences, UK spelling, no melodrama.

## IAM (live mode only)

The execution role gets a single inline read-only policy:
`guardduty:GetFindings`, `guardduty:ListFindings`, `cloudtrail:LookupEvents`,
`ec2:DescribeInstances`, plus whatever Bedrock model-invocation permissions
the current docs require. Nothing else. Add a CI-friendly check
(`scripts/verify_readonly.sh`) that greps the codebase for mutating boto3
calls and fails on any hit — the guardrail should be enforced, not asserted.

## Working method

- Read `PLAN.md` and execute phases **in order**. Tick checkboxes as you go;
  update acceptance-criteria notes with actual results.
- Plan before coding each phase; keep commits small with conventional
  messages (`feat:`, `fix:`, `docs:`, `test:`).
- A phase is done when its tests pass **and** an `agentcore dev` smoke run
  behaves (Phases 0–2 local; 3–4 deployed).
- Golden verdict outputs live in `tests/golden/`. Update them deliberately
  with a commit message explaining why — never silently.
- Do not add scope. Stretch goals only after Phase 4 is complete.

## Definition of done

Phase 4 complete, plus the README's "What I learned" section filled with at
least three honest, specific observations about AgentCore's sharp edges —
things a security engineer would want to know, not marketing copy.
