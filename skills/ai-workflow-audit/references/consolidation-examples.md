# Consolidated report — style examples

**These excerpts are fictional.** The project "Larkspur" and its services are made up. Use them only to match tone, density and layout. Never copy their facts, numbers or repo names into a real report.

---

## At a glance: Overall

Exactly three sentences, about 60 words: the usage picture, then the 2–3 most important gaps **by theme** (the counts are in the table right below), then the root cause.

> **Overall:** The team works with an agent that edits files and runs commands, and the respondent knows most of the safe practices (5 of 6 scenarios right). Committed secrets, agents with access to production data and AI code landing on main branches unreviewed are the most important gaps. The knowledge is there, but the shared setup that enforces it is not.

## At a glance: headline table and bullets

> | Source | Headline |
> |---|---|
> | AI audit (3 repos) | Avg 2.36/5 (range 1.65–3.15) · 1 Ad hoc, 1 Emerging, 1 Defined · 5 critical / 7 high issues |
> | Questionnaire (1) | Agent edits files and runs commands · Practice Score 67–77 (Advanced) · 5/6 scenarios right · claims contradicted in 2 of 3 repos |
>
> - **Strongest area:** Instruction files and docs in web-app (Instructions & Memory 4, Knowledge Base 4); the project average for both is 3.00.
> - **Biggest blind spot:** Verification & review. The respondent says tests run before every merge, but 2 of 3 repos have no PR CI and orders-api pushed 140 AI commits straight to `main` in 90 days.
> - **First thing to fix:** Rotate the two committed keys, then commit one shared safety-settings template (deny rules, hooks, secret scan) and branch protection to all 3 repos.

## Two-source comparison

> | Theme | AI audit (repo evidence) | Questionnaire (knowledge and claims) | Verdict |
> |---|---|---|---|
> | Guardrails, permissions & secrets | Weak: no deny rules in 3/3; secrets in 2 repos | Partial: Q3 right, Q4 missed; autonomous agent with weak guardrails (3/3) | **Overstated** |
> | Verification & review | Weak: no PR CI in 2/3; direct pushes in 2 repos | Partial: Q7 right; X2 contradicted in 2/3 | **Overstated** |

## Where the sources disagree

Start each item with a bold title, then the claims labelled Questionnaire: / Audit:, with the headline number, and one line on what it means when that isn't obvious.

> 1. **Tests "run before merge".** Questionnaire: the daily workflow says tests or CI run before every merge. Audit: no PR CI in orders-api or billing-service, and 200 AI commits pushed straight to `main` across the two. Only web-app runs tests on pull requests.

## Repo breakdown

> | Repo | Score | Maturity | Critical / High | Two weakest areas |
> |---|---|---|---|---|
> | orders-api | 2.28 | Emerging | 2 / 3 | Guardrails & Hooks (1), Git & Review Workflow (1); Skills & Commands also 1 |

## Top security issues

Each issue is one phrase; the Where cell lists repo names only; specifics go to Further detail: Security detail.

> | Critical | Likely-real credentials committed to git | orders-api, billing-service |

## Recommended actions

Order by risk. Write each action as 3–4 short steps separated by semicolons, about 35 words, naming repos only where a step is repo-specific. Name a concrete lever where the evidence offers one.

> | # | Action | Fixes | Effort |
> |---|---|---|---|
> | 1 | Rotate and remove both committed keys; untrack `.env` files and gitignore them; run a full-history secret scan | Critical secrets (2 repos) | Quick–Short |
> | 2 | Point billing-service's MCP server at staging without PII; use a read-only role | Critical production-data finding | Short |
> | 3 | Copy web-app's `.claude/settings.json` as the base for one shared template; add deny rules for `.env*`, force-push and `--no-verify`, plus a gitleaks pre-commit; commit it to all 3 repos | Guardrails (Overstated); High in 3/3 | Short |
> | 4 | Protect default branches (PR, 1 approval, required checks) and add PR CI to orders-api and billing-service | Verification & review (Overstated); Critical direct pushes | Quick–Short |
> | 5 | Agree a team brief for agent tasks (goal, where to look, investigate first, constraints, a test that proves the fix) and keep it in `AGENTS.md` | Prompt exercise missing investigate-first and constraints | Quick |
>
> If all audit changes are done, the audits project an average of **3.48** (range 3.00–3.78), up from 2.36.

## Further detail: Questionnaire detail

Italic sub-labels, one line per topic, aggregates and counts only. Never pair a score with a repo.

> **Questionnaire detail:**
> - *Profile:* 1 respondent (backend, 3–5 years), answered interactively once for all 3 repos; works with an agent that edits files and runs commands.
> - *Practice Score:* 67–77, Advanced; only "matches the audit" differs between repos (0–10).
> - *Scenarios:* 5/6 right; missed prompt injection (Q4: don't run install commands found in files; flag them).
> - *Prompt exercise:* 3/5 elements; missing investigate first and constraints.
> - *Written answers:* best work 3, daily workflow 2 (no context source named), got it wrong 1 (nothing changed afterwards).
> - *Says vs found:* X1 contradicted in billing-service; X2 and X3 contradicted in orders-api and billing-service; all consistent in web-app.
> - *Flags:* autonomous agent, weak guardrails (3/3 repos).

## Further detail: other sub-headings

Security detail, Verdict notes and Repo-specific notes use nested bullets with an italic lead-in per finding or per repo. Put the repo's score in brackets and end with its projected score.

> - *orders-api (2.28):* lean `CLAUDE.md`, but no skills or commands (Skills 1); `.env` tracked at `config/.env:3`. No PR CI. Projected 3.78.
