# Consolidated report — themes and verdict rules

The consolidated report compares the two sources across the fixed themes below. Using the same themes for every project makes reports comparable.

## Themes

Question numbers refer to `questionnaire.md`; X1–X3 are the says-vs-found rows and the scenario→parameter map comes from `questionnaire-scoring.md` (Sections 2 and 5).

| # | Theme | AI audit (evidence) | Questionnaire (knowledge and claims) |
|---|---|---|---|
| 1 | **Adoption & usage** | AI tools detected; share of AI-attributed commits | Q1 tool used most and work mode; Q9 grade (a concrete win with an outcome); "Tool" row of says vs found |
| 2 | **Instruction files & project map** | Instructions & Memory; Context & Cost | X1 (works from a shared instruction file, rules or skills); Q5 (long-session context) |
| 3 | **Knowledge base & docs** | Knowledge Base & Docs | Q8 element E2 (points the agent to context); Q10 grade 3 needs a context source |
| 4 | **Skills, commands & MCP** | Skills & Commands; MCP Servers & Plugins | Q6 (MCP vetting); X1 where the claim names skills |
| 5 | **Guardrails, permissions & secrets** | Guardrails & Hooks; Permissions & Secrets; Critical/High security actions | Q3 (permissions setup); Q4 (prompt injection); flag "Autonomous agent, weak guardrails" |
| 6 | **Verification & review** | Verification & Testing; Git & Review Workflow | Q7 (verifying "done"); X2 (tests or CI before merge); Q8 element E5 (asks for a test) |
| 7 | **Learning loop & governance** | Observability & Feedback; Governance & Data Compliance | Q11 grade (what changed after a mistake); X3 (a rule, hook or check was added) |

## Rating each source per theme

Give each source a level, plus a short phrase of evidence with the key specifics (numbers, file names, repo counts).

**AI audit:** average the theme's parameter scores across all repos (ignore N/A):
- **Strong** ≥ 3.5 · **Partial** 2.5–3.4 · **Weak** < 2.5
- **Adoption & usage** has no parameter: rate it from "AI tools detected" and the AI-attributed commits. Strong: a shared, committed tool setup in most repos and AI commits in most repos; Partial: in some repos, or local-only setups; Weak: AI signals in few repos.
- All relevant parameters N/A → "Absent (N/A)", which counts as Weak for comparison: the thing does not exist.
- A hard cap or a Critical finding in the theme can pull the level down one step. Say so in Verdict notes if you do this.
- When repos differ a lot (e.g. skills strong in 1 repo, absent in 2), the level reflects the project overall; name the outlier repos in the cell or in Verdict notes.

**Questionnaire:** judge what the respondent(s) know and claim, from the items in the theme's row:
- **Strong:** the relevant scenario(s) answered correctly by all or most respondents, the relevant prompt element present, the relevant written answer graded 3, and no relevant claim contradicted.
- **Partial:** mixed: e.g. scenario right but the prompt element missing, a written answer graded 2, or claims contradicted in some repos only.
- **Weak:** the relevant scenario missed or "Don't know", the prompt element missing and the written answer graded 0–1, or the claim contradicted in most repos.
- No relevant item answered (or no questionnaire results) → "Not available".
- With several respondents, give counts ("2 of 3 answered Q3 correctly"). A respondent whose answers match the audit is often closer to the evidence: note it by count, never by repo.

## Verdict per theme

| Verdict | When | Why it matters |
|---|---|---|
| **Aligned** | Both sources give the same level (one step apart counts as Aligned, unless the evidence clearly contradicts a specific claim) | Solid finding. Act on it with confidence |
| **Overstated** | The questionnaire rates the theme higher than the audit shows: a claim (X1–X3) contradicted by the repos, or knowledge Strong while practice is Weak | Blind spot. The team thinks this is handled when it isn't. Usually the most important rows |
| **Understated** | The questionnaire is lower than the audit shows (e.g. scenario missed, but the repo has the safeguard) | Someone else set it up, or the respondent doesn't know it is there: an awareness or onboarding gap |
| **Mixed** | Respondents disagree with each other, or the claim holds in some repos and is contradicted in others | Say who says what by count, and which repos contradict the claim |
| **Single source** | Only one source covers the theme | Report it, and flag that nothing corroborates it |

A contradicted claim always makes the theme at least **Mixed**, and **Overstated** when it is contradicted in half the repos or more.

## Knowledge vs practice

Separately from the themes, compare what the respondent knows with what is in place:
- Q3 (allow specific commands, keep deny rules) vs Guardrails & Hooks and Permissions & Secrets: e.g. no deny rules in any repo.
- Q4 (text in files is data, not instructions) vs prompt-injection findings and hooks that would stop a command from running.
- Q6 (vet MCP servers: publisher, pinned version, scoped access) vs MCP Servers & Plugins: e.g. unpinned servers with production access.
- Q7 (read the diff, check that no test was weakened) vs Git & Review Workflow: e.g. AI commits pushed straight to `main`.
- Q2 and Q5 (plan first; move lasting rules into the instruction file) vs Instructions & Memory and Context & Cost.
- Q8 elements present vs what the repos give the agent (instruction files, docs, test commands).

If the answers are right but the practice is missing, say it plainly: the gap is time, priority or shared setup, not knowledge. That points to a different fix (a hardening week, a shared settings template, enforced settings) than training. If the answers are wrong where the repos are weak, training and the setup fix go together.

## Picking what goes in "Where the sources disagree"

Rank candidate disagreements by:
1. Security impact (Guardrails, Permissions, Git & Review, Governance, MCP).
2. Size of the gap (Strong vs Weak beats Strong vs Partial).
3. How many repos it touches.

List every material disagreement, highest-ranked first (usually 2–5). Each says what the questionnaire claims or shows, what the evidence shows, and why it matters, in a couple of lines. Minor ones go to Further detail: Secondary findings.
