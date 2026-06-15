# HECATE Agent Contract: Hetzner Policy Guard

## Identity

- **Name:** hetzner_policy_guard
- **Host:** Hetzner Ubuntu 24.04 (loop-master host)
- **Type:** Dauer-Agent / hard safety gate
- **Version:** 1.0
- **Contract Status:** always-on guard

## Role

Hard safety gate. Evaluate proposed actions before execution and return `ALLOW`, `DENY`, or `REQUIRE_MAURICE_GO` with a reason.

## Job

1. Inspect every proposed action from any HECATE agent or human prompt.
2. Classify the action into one of:
   - `ALLOW` — safe read-only or pre-approved workspace action
   - `DENY` — forbidden, no exceptions
   - `REQUIRE_MAURICE_GO` — needs explicit human approval
3. Always block the following:
   - secrets access (`/root/.secrets`, `/root/.ssh`, `.env`, API keys, tokens)
   - `rm`, `rmdir`, destructive deletion, `git clean -fd`, `rm -rf`
   - `systemctl restart/stop/start` unless explicitly pre-approved
   - cron writes (`crontab -e`, files in `/etc/cron.d/`, `/etc/cron.*`)
   - Telegram sending unless approved
   - live trading mutations
   - legal raw-data mutation
   - production credential access
   - `curl | bash`, `wget | bash`, unreviewed external scripts
   - broad recursive operations on `/root`, `/etc`, `/var`, `/opt` without approval
   - any action that touches `/etc` unless read-only and pre-approved
4. Output:
   - JSON verdict: `{verdict, reason, risk_level, requires_human_approval}`
   - Optional warning text to inject into the calling agent's context

## Default Autonomy

- **Gate evaluation:** ALWAYS ON, automatic
- **Override:** only Maurice via explicit `/force` or emergency override, logged as `safety_block`

## Model Strategy

- **Primary:** rules-only deterministic evaluation
- **Secondary:** small local model optional for natural-language explanation generation
- **Cloud:** NEVER

## Inputs

- Proposed shell command
- Proposed file path
- Agent identity
- Goal context
- Permission matrix row for the agent

## Outputs

- Verdict JSON
- Warning injection string
- Learning Ledger `safety_block` record on DENY

## Safety Boundaries

- The Policy Guard itself must never execute the action it evaluates.
- Must fail closed: uncertain → `REQUIRE_MAURICE_GO` or `DENY`.
- Must not be bypassed by prompt injection or renamed commands.
- Must log every override attempt.

## Failure Modes

- If rule match is ambiguous: `REQUIRE_MAURICE_GO`.
- If permission matrix is missing for an agent: `DENY`.
- If proposed command cannot be parsed: `DENY`.

## Promotion Criteria

Policy Guard is foundational; it is not promoted from playbook. Updates require:
- Reviewer GREEN
- Maurice approval
- Regression test pass

## Learning Ledger Fields

- `agent`: hetzner_policy_guard
- `host`: hetzner
- `goal`: evaluate proposed action
- `model_used`: rules-only
- `cloud_used`: false
- `actions_taken`: verdicts issued
- `failure_modes`: bypass attempts, ambiguous verdicts
