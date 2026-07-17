# Deployed execution role — what the agent can actually do

Role: `AgentCore-StewardsEnquiry-ApplicationAgentStewardsE-*` (created by the
`@aws/agentcore-cdk` L3 construct; dumped 2026-07-17 with
`aws iam get-role-policy`, one inline policy, no attached managed policies).

## Grants, and whether we want them

| Grant | Scope | Assessment |
|---|---|---|
| `bedrock:InvokeModel`, `InvokeModelWithResponseStream`, `CountTokens` | This account's inference profiles + foundation models | Required — the only way the agent reasons |
| `logs:*` (create/put/describe/filter/get on log streams) | `/aws/bedrock-agentcore/runtimes/*` log groups only | Required — invariant 5 (traceability) |
| `xray:PutTelemetryRecords`, `PutTraceSegments`; `logs:DescribeLogGroups` | `*` | Required for OTel traces; X-Ray has no resource-level scoping |
| `bedrock-agentcore:*ConfigurationBundle*` (incl. Create/Update/Delete) | `configuration-bundle/*` resources | **Surplus.** Construct default for a feature this project does not use. The codebase never calls these APIs (invariant 1 governs the code, and the CI guard enforces that); this is unused standing IAM privilege on the deployed principal — a real but bounded mutation capability, limited to AgentCore's own config-bundle store with no reach into any security-relevant resource. Tracked as a deliberate, documented exception rather than silently accepted. |

## What is deliberately absent

No `guardduty:*`, no `cloudtrail:*`, no `ec2:*`, no `s3:*`, no `iam:*` — nothing.
The deployed agent **cannot read any security data from the account** (it
triages the bundled fixtures) and cannot touch any resource a containment
action would target. The brief's read-only policy
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
