# Steward's Enquiry — plain-English brief and demo script

## What this is, in one sentence

A security analyst's assistant that investigates AWS security alerts by
itself, but is built so it physically cannot take any action — it can only
recommend, and a human always decides.

## The problem (why this exists)

Security teams drown in alerts. AWS GuardDuty raises a finding whenever
something looks suspicious — a server being password-guessed, a machine
talking to a crypto-mining pool, an identity poking around from Tor. Most
are noise; a few are house fires. A human must read each one, gather
context, and decide. Slow, repetitive, burnout-inducing.

"Let an AI triage them" is the obvious fix — and exactly where the danger
is. An AI that can *investigate* is useful; an AI that can *act* (stop
servers, revoke credentials) is a new incident waiting to happen. The
interesting problem is not making the AI smart — it is giving it enough
authority to be useful and provably not enough to be dangerous.

## What it does, step by step

1. A GuardDuty finding goes in (JSON alert).
2. The agent (Claude on Bedrock) investigates with exactly four tools:
   get_finding, lookup_ip, query_cloudtrail, propose_containment.
3. It reasons like an analyst: corroborate before concluding; check 72h of
   baseline behaviour, not just the incident window.
4. Out comes a schema-validated verdict: true_positive / false_positive /
   benign_true_positive / needs_human, with confidence, tool-cited
   evidence, and proposals stamped pending_approval. Nothing executes.
   The state machine ends at "a human decided".

### The moving parts (what's AWS, and where)

```
 you / SOC analyst
   |  agentcore invoke '{"finding_id": ...}'   (signed with YOUR
   v                                            IAM identity, not the agent's)
+--------------------------------------------------------------------+
| AWS account, eu-west-2                                              |
|                                                                     |
|  +--------------------------------------------------------------+  |
|  | Bedrock AGENTCORE RUNTIME  <-- the managed agent host        |  |
|  | (serverless, one isolated session per triage)                |  |
|  |                                                              |  |
|  |  main.py entrypoint                                          |  |
|  |    \-- triage loop  ----- prompt ---->  Amazon BEDROCK       |  |
|  |         |           <-- reasoning ---  (Claude Sonnet 4.6)   |  |
|  |         |                                                    |  |
|  |         |-- get_finding -------> bundled GuardDuty fixtures  |  |
|  |         |-- lookup_ip ---------> bundled reputation feed     |  |
|  |         |-- query_cloudtrail --> bundled audit events        |  |
|  |         \-- propose_containment: records a proposal.         |  |
|  |                                  EXECUTES NOTHING.           |  |
|  |         v                                                    |  |
|  |  verdict, validated against schema + the actual tool trace   |  |
|  +--------------------------------------------------------------+  |
|     |  every step logged/traced          ^  deployed by            |
|     v                                    |                         |
|  CLOUDWATCH GenAI Observability     CloudFormation (CDK)           |
|  (logs + X-Ray traces)              + S3 code artefact             |
|                                                                     |
|  IAM execution role: may call Bedrock and write logs. Nothing else. |
+--------------------------------------------------------------------+

 Deliberately NOT connected in v1: GuardDuty and CloudTrail themselves.
 The findings/audit data are bundled fixtures in GuardDuty's real JSON
 format, so the demo runs anywhere; live read-only feeds are a documented
 stretch goal behind the STEWARD_LIVE flag.
```

| AWS service | Role here |
|---|---|
| **Bedrock AgentCore Runtime** | Hosts the agent — serverless, session-isolated, billed only while a triage runs. This is "AgentCore". |
| **Amazon Bedrock** | Serves the Claude model that does the reasoning |
| **IAM** | The execution role that *cannot* act — the load-bearing control |
| **CloudWatch (+ X-Ray)** | Logs and the GenAI Observability trace of every tool call |
| **CloudFormation + S3 (via CDK)** | Deployment: immutable code versions, one command |

## Why it's trustworthy — four independent layers

1. **IAM** — the deployed role can invoke the model and write logs. That is
   all. The permission to stop a server does not exist (docs/EXECUTION-ROLE.md).
2. **Code** — propose_containment has no execute path; its status is a
   constant; no parameter can override it.
3. **CI** — scripts/verify_readonly.sh fails the build on any mutating AWS
   call shape; regression-tested against reviewer-found bypasses.
4. **Validation** — verdicts must pass the JSON schema, cross-field policy
   rules, AND be grounded in the actual tool trace. Hallucinated evidence
   or invented proposals → verdict discarded → needs_human. Failure always
   collapses to the safe outcome.

The tor-recon fixture is the philosophy: it *looks* malicious, but the
principal is `svc-scanner` with a history of scheduled 02:00 scans —
plausibly an authorised pentest. Correct answer: needs_human. An agent that
knows when not to be confident is the one you can deploy.

## Demo script

Prep once: `aws sso login --profile <your-profile>`
then `export AWS_PROFILE=<your-profile> AWS_REGION=eu-west-2`

**2 minutes, offline:**

    head -20 fixtures/findings/ssh-bruteforce.json   # a GuardDuty alert
    uv run pytest -q                                 # 121 tests, zero creds
    cat tests/golden/tor-recon.verdict.json          # choosing NOT to be confident

**5 minutes, live cloud triage:**

    agentcore invoke '{"finding_id": "crypto-mining"}'
    # narrate: fetching finding → IP reputation → 72h CloudTrail → proposal
    # point at: pending_approval, requires_approval: true, evidence per tool

**Full proof (~8 min; run beforehand, show output):**

    bash scripts/e2e_remote.sh
    # offline suite → fresh package → deploy (new immutable version)
    # → 3 live triages → verdict classes match committed goldens

**Audit trail:** docs/trace-ssh-bruteforce.json (or the CloudWatch GenAI
Observability console) — every tool call is a span; the code cross-checks
verdicts against this trail automatically.

**If asked "what if it's wrong?"** — that is the design: a wrong verdict
costs a human review, never an outage, because acting was never in its
power.

**Process story:** every PR went through a two-AI-reviewer gate (opus-4.8
verifying + gpt-5.6 on the diff). One review caught the model fabricating
evidence in an early golden ("zero CloudTrail events" — the fixture had
two). That finding became the trace-grounding check in layer 4. The
governance process found the exact failure mode the governance code now
prevents. All on record in the PR threads.
