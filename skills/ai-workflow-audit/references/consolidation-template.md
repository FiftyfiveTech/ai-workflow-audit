# Consolidated report — template

Use these headings in this order. Replace `<…>`. Omit a section only where noted.

## Length: two layers, nothing lost

There is no word limit, and no finding is ever dropped to save space. The report has two layers:

1. **Main body** (At a glance → About this report): a manager can read it in about 5 minutes. Write it in **phrases, not paragraphs**. Each table cell or bullet holds the level or claim plus the one or two numbers that prove it (e.g. "Weak: no hooks in 3/3; secrets in 2 repos"). Leave out justifications, lists of examples, per-repo specifics and "why I rated it this way" reasoning. Those go to layer 2.
2. **Further detail** (appendix): every supporting specific, under fixed sub-headings. Anything a reader might need to act on or check belongs here if it isn't in the main body: which secrets sit where, per-repo counts, the reasoning behind a verdict, repo-specific extras, questionnaire detail. It can be as long as the evidence needs.

Rules that keep both layers tight:
- **Say each thing once.** When the appendix expands a main-body point, the main body just says "(see Further detail: Security)".
- **Group, don't repeat.** A finding that is the same in 3 repos becomes one row that says "all 3 repos".
- **Keep specifics, drop filler.** Keep numbers, file names and repo names. Cut introductions, restated questions, obvious "why it matters" lines and generic advice not tied to this project's evidence.
- **Plain English.** Name parameters ("Guardrails & Hooks"), not bare codes ("P4"). Write "no automated safety checks stop the agent from pushing to main", not "P4=1 hard cap".
- **Completeness check before saving.** Every Critical and High finding from every audit appears somewhere: as a main-body row, or inside a grouped row with its specifics in the appendix. The same goes for every theme verdict, every disagreement and every caveat.

````markdown
# AI Adoption Audit: <Project name>

<audit date, or range> · <N> repo audit(s) · <M> questionnaire respondent(s) · ai-workflow-audit v<version>

## At a glance

**Overall:** <Exactly 3 plain-English sentences, about 60 words: (1) the usage picture, with at most one parenthetical; (2) the 2–3 most important gaps named by theme, not as counts; (3) the root cause, e.g. "the right practices are known but not set up in the repos".>

| Source | Headline |
|---|---|
| AI audit (<N> repos) | Avg <x.xx>/5 (range <min>–<max>) · <k> Emerging, <k> Defined… · <C> critical / <H> high issues |
| Questionnaire (<M>) | <e.g. agent edits files and runs commands; Practice Score 67–77 (Advanced); 5/6 scenarios right; claims contradicted in 2 of 3 repos> |

- **Strongest area:** <theme and evidence>
- **Biggest blind spot:** <theme where the questionnaire claims or knowledge are well above the evidence>
- **First thing to fix:** <one action>

## Two-source comparison

| Theme | AI audit (repo evidence) | Questionnaire (knowledge and claims) | Verdict |
|---|---|---|---|
| Adoption & usage | <Level: key fact> | <Level: key fact> | <Verdict> |
| Instruction files & project map | | | |
| Knowledge base & docs | | | |
| Skills, commands & MCP | | | |
| Guardrails, permissions & secrets | | | |
| Verification & review | | | |
| Learning loop & governance | | | |

(Cells are phrases, about 15 words at most, with the numbers kept. Reasoning goes to Further detail: Verdict notes. If no report has questionnaire results, the Questionnaire column says "Not available" in every row and every verdict is "Single source".)

**Knowledge vs practice:** <2–3 sentences comparing the scenario answers and prompt exercise with what is actually in the repos.>

## Where the sources disagree

1. **<Short title>.** Questionnaire: <claim or answer>. Audit: <evidence, with the headline number>. <Why it matters, only if not obvious.>
2. …
(Every material disagreement, highest risk first, 2–3 sentences each. Longer example lists go to Further detail. Minor ones go to Further detail: Secondary findings. If there are none, write "None: the questionnaire and the audits agree on every theme.")

## Repo breakdown
(Omit this section if there is only one repo, and put that repo's score in "At a glance".)

| Repo | Score | Maturity | Critical / High | Two weakest areas |
|---|---|---|---|---|
| <repo> | <x.xx> | <band> | <c> / <h> | <param (score), param (score)> |
| **Project** | **avg <x.xx>** | <band counts> | **<C> / <H>** | |

*Critical / High = number of security findings the audit rated at that severity. Critical: <plain-English meaning, with an example from these findings, e.g. "secrets or production data exposed, or AI code reaching the main branch unreviewed"> (fix now). High: <e.g. "an important safety control is missing"> (fix soon).*

**Recurring gaps** (≤ 2 in at least half the repos): <param (avg), …>

## Top security issues

| Severity | Issue | Where |
|---|---|---|
| Critical | <plain-English issue, one phrase> | <repo names or "all 3 repos"> |
(Cover every Critical and High finding. Group identical findings across repos into one row. Keep the Issue cell to one phrase and the Where cell to repo names; specifics go to Further detail: Security detail. With a single repo, put the Critical / High legend line under this table instead. If there are none, write "None found in any repo.")

## Recommended actions

| # | Action | Fixes | Effort |
|---|---|---|---|
| 1 | <short steps separated by semicolons> | <severity + scope, e.g. "Critical secrets (2 repos)", or the theme verdict, e.g. "Verification & review (Overstated)"> | Quick / Short / Longer, or a range like Quick–Short |
(Order by risk: secrets → production-data exposure → guardrails → branch protection → CI → policy → instruction files → practice. Keep each Action cell to 3–4 steps, about 35 words. Name repos only where a step is specific to them. Extra steps, repo lists and smaller High fixes go to Further detail: Repo-specific notes, labelled with the action number ("Action 3 applies to: …"). Name a concrete lever where the evidence offers one, e.g. one shared settings template for all repos, a hardening week, or the project's best-set-up repo as the model for the others. Enough rows that every Critical finding and every Overstated theme has an action, usually 4–8. Where the questionnaire shows a practice gap (a missed scenario, missing prompt elements), add one team-level practice action; never address it to a person.)

If all audit changes are done, the audits project an average of **<x.xx>** (range <min>–<max>), up from <x.xx>.

## About this report

- **Sources:** <N> audit reports (<repo names>; agent · model · model check); questionnaire results from <M> respondent(s) (<"one answers file reused for every repo" in project mode>).
- **Confidentiality:** no names or emails. The questionnaire is self-administered: one person's answers graded against fixed anchors, a practice indicator, not an employee evaluation. Share internally. <With a single respondent, add: the questionnaire sections describe one person's answers.>
- **Limits:** <every caveat that affects how the report should be read, one short line each: what the audits couldn't verify, repos without a report or without questionnaire results, different agents or models, a model check of `unverified`, one respondent possibly answering for several repos>

## Further detail

(Include every sub-heading that has content. Short bullets. Nothing here repeats the main body word for word; it adds the specifics behind it.)

**Security detail:** <per finding: which repos, what exactly (secret kind, `file:line` as the audit gave it, commit counts), fix specifics>
**Verdict notes:** <reasoning behind any level or verdict that isn't self-evident from the table>
**Repo-specific notes:** <per repo: findings not covered above, notable strengths, per-repo steps for the recommended actions, projected score>
**Questionnaire detail:** <one bullet per topic with an italic label: *Profile:*, *Practice Score:*, *Scenarios:*, *Prompt exercise:*, *Written answers:*, *Says vs found:*, *Flags:*. Aggregates and counts only.>
**Secondary findings:** <minor disagreements or observations that matter but didn't make the main list>
````

## Style notes

- Write for a manager who doesn't know the scoring system.
- Use numbers wherever they exist ("140 AI commits pushed straight to main in 90 days", "2 of 3 repos").
- Paraphrase questionnaire answers; never quote them at length.
- No emoji. Bold the verdict words only in the Verdict column, if it helps scanning.
