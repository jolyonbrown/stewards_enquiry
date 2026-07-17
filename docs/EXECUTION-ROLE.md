# Deployed execution role — what the agent can actually do

Role: `AgentCore-StewardsEnquiry-ApplicationAgentStewardsE-*` (created by the
`@aws/agentcore-cdk` L3 construct; dumped 2026-07-17 with
`aws iam get-role-policy`, one inline policy, no attached managed policies).

## Grants, and whether we want them

| Grant | Scope | Assessment |
|---|---|---|
| `bedrock:InvokeModel`, `InvokeModelWithResponseStream`, `CountTokens` | **All** inference profiles in the account + all foundation models | Required in kind, **broader than needed in scope** — the agent uses exactly one committed profile. AWS supports pinning to that profile + its destination model ARNs. Follow-up #3. |
| `logs:CreateLogGroup/CreateLogStream/PutLogEvents/Describe*` | `/aws/bedrock-agentcore/runtimes/*` | Required — invariant 5 (traceability) |
| `logs:FilterLogEvents`, `logs:GetLogEvents` | `/aws/bedrock-agentcore/runtimes/*` (all runtimes, not just this one) | **Surplus.** Emitting telemetry needs write, not read; this lets the runtime read sibling runtimes' logs. Immaterial today (this is the only runtime in the account) but wrong in principle. Follow-up #2. |
| `xray:PutTelemetryRecords`, `PutTraceSegments`; `logs:DescribeLogGroups` | `*` | Required for OTel traces; X-Ray has no resource-level scoping |
| `bedrock-agentcore:*ConfigurationBundle*` (incl. Create/Update/Delete) | `configuration-bundle/*` | **Surplus, and the sharpest wart.** Construct default for a feature this project does not use; Create/Update/Delete are write operations on a store that can hold prompts and tool descriptions. The codebase never calls these APIs (CI-enforced), but unused standing write privilege should be removed, not merely documented. Follow-up #1. |

## Follow-ups (open, from PR #3 review)

1. Strip the configuration-bundle statement from the construct-generated
   policy (CDK override/aspect) — remove, don't document.
2. Drop `FilterLogEvents`/`GetLogEvents`, or scope them to this runtime's
   own log group.
3. Pin Bedrock invocation to the one committed inference profile and its
   destination model ARNs.

These are deliberately deferred, not disputed: they require overriding
vendor-construct defaults and a redeploy, and were found on demo day. The
role's *reach* is unchanged by all three: no security-service data, no
containment-target resources.

## What is deliberately absent

No `guardduty:*`, no `cloudtrail:*`, no `ec2:*`, no `s3:*`, no `iam:*` — nothing.
The deployed agent **cannot read any security-service data from the
account** — no findings, no audit trails, no instance inventory (it triages
the bundled fixtures) — and cannot touch any resource a containment action
would target. (Precision note: it *can* read AgentCore runtime log groups —
see the surplus row above — which is operational telemetry, not account
security data.) The brief's read-only policy
(`guardduty:GetFindings`, `guardduty:ListFindings`, `cloudtrail:LookupEvents`,
`ec2:DescribeInstances`) is specified for **live mode only**, which is stretch
goal C — granting it now would be unused standing privilege, so it is not
granted. When live mode lands, that policy gets added and
`scripts/verify_readonly.sh` remains the CI-side control that the code never
outgrows it.

## The layered argument

1. **IAM** (this role): the agent cannot act on the account — the permissions
   to execute containment do not exist.
2. **Code**: `propose_containment` has no execution path and cannot emit any
   status but `pending_approval` (tested, enum-pinned to the schema).
3. **CI**: `verify_readonly.sh` fails the build on any mutating AWS call
   shape, regression-tested against reviewer-found bypasses.
4. **Validation**: verdicts must be schema-valid, policy-valid, and grounded
   in the actual tool trace, or they fail closed to `needs_human`.
