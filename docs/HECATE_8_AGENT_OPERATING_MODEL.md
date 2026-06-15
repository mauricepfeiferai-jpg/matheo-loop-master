# HECATE 8-Agent Operating Model

> Version: 1.0 | 2026-06-15  
> Scope: practical, local-first, proposal-only agent operating system for Maurice's infrastructure.

## Purpose

Build the first useful HECATE 8-agent operating system that immediately takes work off Maurice while staying safe, local-first, and proposal-only for risky actions.

This is **not** a universal autonomous agent project. It is a controlled operating model where each agent has one clear job, strict permissions, measurable output, and safety gates.

## Agents

### Hetzner: 5 Dauer-Agenten

| Agent | Role | Default Autonomy | Model Strategy |
|-------|------|------------------|----------------|
| `hetzner_operator` | Read-only system analyst | Read-only automatic | local medium → Ollama Cloud fallback |
| `hetzner_sensor` | Event classifier | Non-mutating automatic | rules-first + small local |
| `hetzner_digest` | Compression / reporting | Digest automatic; send proposal-only | local medium → Ollama Cloud fallback |
| `hetzner_policy_guard` | Hard safety gate | Always on, automatic | rules-only, no cloud |
| `hetzner_scout` | Research scout | Read-only / proposal-only | local medium → Ollama Cloud weekly |

### Mac: 3 Arbeits-Agenten

| Agent | Role | Default Autonomy | Model Strategy |
|-------|------|------------------|----------------|
| `mac_builder` | Implementation agent | Workspace-only | Mac local → Ollama Cloud → Codex with GO |
| `mac_reviewer` | Adversarial reviewer | Read-only, blocks promotion | Mac local strong → Ollama Cloud → Claude/ChatGPT with GO |
| `mac_strategist` | Prioritization / architecture | Proposal-only | Mac local strong → ChatGPT/Claude with GO |

## Core Operating Loop

```
Maurice goal
→ hetzner_operator checks current state
→ hetzner_policy_guard validates allowed scope
→ mac_builder builds smallest approved step
→ mac_reviewer performs adversarial review
→ hetzner_digest summarizes result
→ Maurice approves/blocks only real gates
→ hecate.learning_ledger records what happened
→ reusable patterns become playbooks
→ repeated failures become block rules
```

## Local-First Model Routing

1. Try rules first when possible.
2. Try local small/medium model next.
3. Use Ollama Cloud only if:
   - local result is low confidence,
   - task is complex enough to justify it,
   - hourly/daily budget is not exceeded,
   - task is not in a no-cloud zone.
4. Use Claude/Codex/ChatGPT only with explicit Maurice approval.
5. If cloud limits are reached, degrade gracefully to:
   - local-only digest,
   - shorter report,
   - delayed scout review,
   - no retry loops.

See `governance/local_model_routing.yaml` and `governance/cloud_fallback_policy.yaml`.

## No-Cloud Zones

Never send these to Ollama Cloud or any external model automatically:

- secrets, API keys, tokens, private credentials
- raw legal evidence or full legal documents
- live trading credentials or instructions
- production env files
- private customer data or unredacted personal data
- SSH keys, `.env` files, `/root/.secrets`, `/root/.ssh`

## Telegram Policy

Telegram is only for:

- approvals
- daily digest
- critical alerts
- clear decision gates

Telegram is **not** for:

- routine cron spam
- raw logs
- repeated alerts
- long shell output
- every sensor event
- agent self-talk

See `governance/telegram_noise_gate.yaml`.

## Permission Model

Sixteen permissions, default `DENY` unless explicitly allowed per agent:

- `read_files`, `write_files`, `run_tests`, `shell_readonly`, `shell_write`
- `systemd_read`, `systemd_write`, `cron_read`, `cron_write`
- `telegram_send`, `network_access`, `git_read`, `git_write`
- `secrets_access`, `legal_mutation`, `trading_mutation`, `production_restart`

See `governance/agent_permission_matrix.yaml`.

## Proposal-Only Actions

The following actions are always proposal-only:

- systemd restart/stop/start/enable/disable
- cron writes
- Telegram sending
- trading mutation
- legal file mutation
- secrets access
- production service restart
- destructive deletion (`rm -rf`, `git clean -fd`)
- external repo clone
- package install
- `curl | bash`
- broad recursive scans on `/root`, `/etc`, `/var`, `/opt`
- autonomous loop creation

See `governance/proposal_only_policy.yaml`.

## Learning Ledger Integration

Every meaningful agent run records:

- `run_id`, `agent`, `host`, `goal`, `input_summary`
- `model_used`, `routing_reason`, `cloud_used` (true/false)
- `actions_taken`, `files_changed`, `tests_run`
- `reviewer_verdict`, `human_judgment`, `business_outcome`
- `failure_modes`, `reusable_patterns`, `promotion_status`

Promotion path:

```
raw_trace → reviewed_learning → reusable_pattern → approved_playbook → enforced_policy
```

See `hecate/learning_ledger.py` and `hecate/promotion_pipeline.py`.

## Replay Tests

Historical failure modes that must never repeat:

1. Agent produces plan but no delivery.
2. Agent creates stubs/placeholders.
3. Agent claims success without output.
4. Agent tries to read secrets.
5. Agent wants to modify cron without approval.
6. Agent wants to restart production service without approval.
7. Agent spams Telegram with routine status.
8. Agent uses cloud for no-cloud data.
9. Agent touches legal raw files.
10. Agent creates broad autonomous loop without stop condition.

See `tests/test_policy_guard_replay.py` and `tests/test_replay_suite.py`.

## Implementation Phases

### Phase A — Stabilität (this run)

Output: contracts + governance + tests.  
Status target: YELLOW → GREEN.

### Phase B — Erster Nutzen

Activate `hetzner_operator` + `hetzner_digest` + `hetzner_policy_guard` manually.  
Deliver daily clarity: what runs, what is broken, what annoys Telegram, what needs GO.

### Phase C — Builder/Reviewer

Activate `mac_builder` + `mac_reviewer` for small approved improvements.  
Rule: builder builds nothing without reviewer.

### Phase D — Scout

Activate `hetzner_scout` for external idea sorting.  
Allowed: find → evaluate → propose.  
Forbidden: install → build → post → cron start.

### Phase E — Strategist

Activate `mac_strategist` for prioritization.  
Top 3 Hebel: Stabilität, Cashflow, Produktisierung.

## Success Criteria

The system is only GREEN if:

- all 8 agent contracts exist
- permission matrix exists
- local model routing policy exists
- cloud fallback policy exists
- Telegram noise gate exists
- proposal-only policy exists
- replay tests exist and pass
- smoke tests exist for Operator, Builder, Reviewer, Digest, Policy Guard
- no cron/systemd/Telegram/secrets/trading/legal production changes were made
- changed files are listed
- next run command is documented

## Hard Constraints

- Do not access secrets.
- Do not read `.env` files.
- Do not mutate legal files.
- Do not mutate trading files.
- Do not restart services.
- Do not edit systemd.
- Do not edit cron.
- Do not send Telegram.
- Do not run `curl | bash`.
- Do not clone external repos unless explicitly approved.
- Do not install packages unless explicitly approved.
- Do not use cloud models for no-cloud zones.
- Do not create autonomous loops.
- Do not continue if tests fail.
- Do not claim GREEN without evidence.
