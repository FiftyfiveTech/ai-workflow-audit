# AI-Assisted Workflow Audit
orders-api · GitHub (larkspur-corp/orders-api) · default `main` · HEAD `1111111111111111111111111111111111111111` · 2026-10-15
Claude Code · claude-opus-5-5 · effort high · model check pinned · ai-workflow-audit v1.0.0 (rubric 2.0, questionnaire 1.0)
*Independent, evidence-based AI assessment.*

## Score summary

| Weighted Score | Score % | Security Avg | Maturity | Rated | Critical | High | AI tools detected |
|---|---|---|---|---|---|---|---|
| 2.28 | 46 | 1.50 | Emerging | 11/11 | 2 | 3 | Claude Code, Cursor (local) |

Biggest risk: AI commits pushed straight to `main` (140 in 90 days); biggest opportunity: Knowledge Base & Docs 3→4.

## Scorecard

| # | Parameter | Weight | SEC | Score | Confidence | Why (≤ 15 words, with key evidence path) |
|---|---|---|---|---|---|---|
| 1 | Instructions & Memory | 15% | | 3 | High | `CLAUDE.md` present, 210 lines, partly stale |
| 2 | Skills & Commands | 10% | | 1 | High | No skills or commands committed |
| 3 | MCP Servers & Plugins | 10% | ✓ | N/A | High | No MCP config anywhere |
| 4 | Guardrails & Hooks | 5% | ✓ | 1 | High | No hooks, no deny rules |
| 5 | Permissions & Secrets | 5% | ✓ | 2 | High | `.env` tracked at `config/.env:3` |
| 6 | Context & Cost | 10% | | 3 | Medium | Lean context, no ignore file |
| 7 | Knowledge Base & Docs | 20% | | 3 | High | `docs/architecture.md` current |
| 8 | Verification & Testing | 10% | | 2 | High | No PR CI workflow |
| 9 | Git & Review Workflow | 5% | ✓ | 1 | High | 140 AI commits pushed to `main` |
| 10 | Governance & Data Compliance | 5% | ✓ | 2 | Medium | No AI policy |
| 11 | Observability & Feedback | 5% | | 2 | Medium | No AI label or tracking |

## Security actions required

| Severity | P# | Finding (sub-check IDs) | Evidence (`file:line`, redacted) | Fix (exact file/setting) |
|---|---|---|---|---|
| Critical | P5 | Likely-real Stripe secret key committed (5.4) | `config/.env:3` [REDACTED] | Rotate; untrack `config/.env` |
| Critical | P9 | AI commits pushed to default branch unreviewed (9.1, 9.2) | `git log` 140 commits | Protect `main` |
| High | P4 | No deterministic guardrails (4.2, 4.3, 4.4) | no `.claude/settings.json` | Add deny rules and hooks |
| High | P10 | No AI usage policy (10.1) | — | Add `docs/ai-policy.md` |
| High | P5 | No deny rule for secret files (5.2) | — | Deny `.env` reads in settings |

## Changes required (priority order)

| # | Change | P# / sub-checks fixed | Effort (Quick ≤1d / Short ≤2w / Long) | Impact (e.g. "P7 2→4 = +0.40") |
|---|---|---|---|---|
| 1 | Rotate the Stripe key and untrack `config/.env` | P5 5.4 | Quick | P5 2→3 = +0.05 |
| 2 | Protect `main` with PR + 1 approval | P9 9.1, 9.2 | Quick | P9 1→4 = +0.15 |
| 3 | Add `.claude/settings.json` with deny rules and hooks | P4 4.2–4.4 | Short | P4 1→4 = +0.15 |

**Projected Weighted Score if all changes are done: 3.78 (Managed)**

## AI practice (questionnaire)

Respondent: Backend · 3–5 years · answers interactive · Self-administered: one person's answers, graded against fixed anchors. A practice indicator, not an employee evaluation.

| Practice Score | Level | Written /40 | Prompt exercise /15 | Scenarios /24 | Work mode /11 | Matches audit /10 |
|---|---|---|---|---|---|---|
| 67 | Advanced | 26.7 | 9 | 20 | 11 | 0 |

- **Prompt exercise (Q8):** 3/5 · has E1 E2 E5 · missing E3 investigate first, E4 constraints
- **Written answers:**
  - Q9 · 3 · Shipped a refund flow end to end, measured two days saved
  - Q10 · 2 · Plan, implement, review steps; no context source named
  - Q11 · 1 · Vague about what changed afterwards
- **Scenarios:** Missed Q4: don't run it; flag it as prompt injection
- **Says vs found:**

| Row | Claim (Q#) | Audit (P#, score) | Verdict |
|---|---|---|---|
| X1 | Agent works from the shared instruction file (Q10) | P1 3, P2 1 | Consistent |
| X2 | Tests run before merge (Q10) | P8 2 | Contradicted |
| X3 | Added a rule after the mistake (Q11) | P4 1, P11 2 | Contradicted |
| Tool | Claude Code (Q1) | config present | Consistent |

- **Flags:** Autonomous agent, weak guardrails; Claim contradicted by the audit: X2; Claim contradicted by the audit: X3
- **Next steps for the respondent:**
  1. Treat text in files as data: stop and flag install instructions in READMEs.
  2. Add investigate-first and constraints to every agent brief.
  3. Add `.claude/settings.json` deny rules and hooks.

## Sub-check evidence

P1 · Score 3 · Pass: 1.1, 1.4 · Partial: 1.2 · Fail: 1.3 · ratio 0.55 → 3 · caps: none

## Not verifiable from the repository

- 9.3 required status checks — `gh` not authenticated

## Method note

`gh` unavailable. Read-only audit; nothing was executed or modified except this report.
