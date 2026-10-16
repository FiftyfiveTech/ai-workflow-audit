# Larkspur — AI-Assisted Workflow Audit

legacy-service · GitHub (larkspur-corp/legacy-service) · default `develop` · HEAD `4444444444444444444444444444444444444444` · 2026-09-25 · audited by Codex CLI (gpt-6-sol) · prompt v2.0

## Score summary

| Weighted Score | Score % | Security Avg | Maturity | Rated | Critical | High | AI tools detected |
|---|---|---|---|---|---|---|---|
| 3.00 | 60 | 3.00 | Defined | 11/11 | 0 | 1 | OpenAI Codex |

Biggest risk: no hooks.

## Scorecard

| # | Parameter | Weight | SEC | Score | Confidence | Why |
|---|---|---|---|---|---|---|
| 1 | Instructions & Memory | 15% | | 3 | High | AGENTS.md |
| 2 | Skills & Commands | 10% | | 3 | High | x |
| 3 | MCP Servers & Plugins | 10% | ✓ | 3 | High | x |
| 4 | Guardrails & Hooks | 5% | ✓ | 3 | High | x |
| 5 | Permissions & Secrets | 5% | ✓ | 3 | High | x |
| 6 | Context & Cost | 10% | | 3 | High | x |
| 7 | Knowledge Base & Docs | 20% | | 3 | High | x |
| 8 | Verification & Testing | 10% | | 3 | High | x |
| 9 | Git & Review Workflow | 5% | ✓ | 3 | High | x |
| 10 | Governance & Data Compliance | 5% | ✓ | 3 | High | x |
| 11 | Observability & Feedback | 5% | | 3 | High | x |

## Security actions required

| Severity | P# | Finding | Evidence | Fix |
|---|---|---|---|---|
| High | P4 | No hooks (4.2) | — | Add hooks |

## Changes required (priority order)

**Projected Weighted Score if all changes are done: 3.65 (Managed)**
