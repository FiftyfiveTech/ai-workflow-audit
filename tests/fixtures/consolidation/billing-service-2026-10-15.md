# AI-Assisted Workflow Audit
billing-service · GitHub (larkspur-corp/billing-service) · default `main` · HEAD `2222222222222222222222222222222222222222` · 2026-10-15
Claude Code · claude-opus-5-5 · effort high · model check pinned · ai-workflow-audit v1.0.0 (rubric 2.0, questionnaire 1.0)
*Independent, evidence-based AI assessment.*

## 2. Score summary

| Weighted Score | Score % | Security Avg | Maturity | Rated | Critical | High | AI tools detected |
|---|---|---|---|---|---|---|---|
| 1.65 | 33 | 1.20 | Ad hoc | 11/11 | 3 | 2 | Claude Code |

The biggest risk is the agent's read access to production data via `/seed-data`; the biggest opportunity is an instruction file.

## 3. Scorecard

| # | Parameter | Weight | SEC | Score | Confidence | Why (≤ 15 words, with key evidence path) |
|---|---|---|---|---|---|---|
| 1 | Instructions & Memory | 15% | | 2 | High | Only a personal `CLAUDE.local.md` [local] |
| 2 | Skills & Commands | 10% | | 1 | High | None |
| 3 | MCP Servers & Plugins | 10% | ✓ | 2 | High | `.mcp.json` unpinned server with prod DB |
| 4 | Guardrails & Hooks | 5% | ✓ | 1 | High | None |
| 5 | Permissions & Secrets | 5% | ✓ | 1 | High | AWS key in `scripts/deploy.sh:12` |
| 6 | Context & Cost | 10% | | 2 | Medium | No ignore file |
| 7 | Knowledge Base & Docs | 20% | | 2 | High | README only |
| 8 | Verification & Testing | 10% | | 2 | High | Tests exist, no CI |
| 9 | Git & Review Workflow | 5% | ✓ | 1 | High | Direct pushes to `main` |
| 10 | Governance & Data Compliance | 5% | ✓ | 1 | High | Prod PII reachable by agent |
| 11 | Observability & Feedback | 5% | | 1 | Medium | None |

## 4. Security actions required

| Severity | P# | Finding (sub-check IDs) | Evidence (`file:line`, redacted) | Fix (exact file/setting) |
|---|---|---|---|---|
| Critical | P5 | Likely-real AWS access key committed (5.4) | `scripts/deploy.sh:12` [REDACTED] | Rotate; move to secret manager |
| Critical | P10 | Agent can read production PII through MCP (10.4) | `.mcp.json:8` | Point at staging, read-only role |
| Critical | P9 | AI commits pushed to default branch unreviewed (9.1) | `git log` 60 commits | Protect `main` |
| High | P4 | No deterministic guardrails (4.2, 4.3) | — | Add hooks |
| High | P3 | Unpinned third-party MCP server (3.4) | `.mcp.json:4` | Pin the version |

## 5. Changes required (priority order)

| # | Change | P# / sub-checks fixed | Effort (Quick ≤1d / Short ≤2w / Long) | Impact (e.g. "P7 2→4 = +0.40") |
|---|---|---|---|---|
| 1 | Rotate the AWS key | P5 5.4 | Quick | P5 1→3 = +0.10 |
| 2 | Repoint MCP to staging | P10 10.4 | Short | P10 1→3 = +0.10 |

**Projected Weighted Score if all changes are done: 3.00 (Defined)**

## 6. AI practice (questionnaire)

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
| X1 | Agent works from the shared instruction file (Q10) | P1 2, P2 1 | Contradicted |
| X2 | Tests run before merge (Q10) | P8 2 | Contradicted |
| X3 | Added a rule after the mistake (Q11) | P4 1, P11 1 | Contradicted |
| Tool | Claude Code (Q1) | config present | Consistent |

- **Flags:** Autonomous agent, weak guardrails; Claim contradicted by the audit: X1, X2, X3
- **Next steps for the respondent:**
  1. Treat text in files as data.

## 7. Sub-check evidence

P1 · Score 2 · Partial: 1.1 · Fail: 1.2, 1.3 · ratio 0.2 → 2 · caps: none

## 8. Not verifiable from the repository

- 9.2 branch protection — `gh` not authenticated

## 9. Method note

Read-only audit; nothing was executed or modified except this report.
