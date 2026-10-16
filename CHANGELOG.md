# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [semantic versioning](https://semver.org).

## [1.0.0] - Unreleased

First public release.

### Added
- `ai-workflow-audit` Agent Skill: a read-only audit of a repository's AI-assisted development workflow, scored on 11 weighted parameters (rubric 2.0). Its output is one Markdown report per repository, with fixed `##` headings (procedure Section 7.1) so reports can be consolidated.
- Step 1 model check. It pins the model where the agent supports it, and otherwise asks the user to confirm or switch. The result (`pinned`, `confirmed`, `switched` or `unverified`) is recorded in the report header.
- Claude Code plugin and marketplace (`ai-workflow-audit@fiftyfivetech`) with a subagent pinned to Claude Opus 5.5 at high effort.
- Optional companion agent files for Codex and Gemini CLI, plus experimental ones for Cursor and GitHub Copilot.
- Mandatory 11-question practice questionnaire (questionnaire 1.0) for the person running the audit. It is asked before the audit and scored after it, giving:
  - an AI Practice Score (0–100) and a level;
  - flags;
  - a says-vs-found comparison with the audit;
  - next steps.

  Where the agent has a selection tool (in Claude Code, `AskUserQuestion`), questions 1–7 and the confirmation are asked with pickers. Question 1 uses two-step pickers so that every choice fits the 4-option limit, and "Don't know" is typed in Other. Questions 8–11 are free text in the chat. Agents without a selection tool get the same questions as lettered lists. Both ways record the same letters. Headless runs need an `answers=` file.
- Project mode. Run the skill in a folder that holds several repositories:
  - Step 0 confirms the repositories and a project name, and writes the manifest `ai-audit/_project.json`.
  - The questionnaire is asked once and copied into each repository.
  - The pinned subagent audits each repository in turn.
- Step 4, the consolidated project report `ai-audit/<project>-consolidated-<date>.md`.
  - It compares the audits (per-repo table, average and range, recurring gaps, every Critical and High finding) with the questionnaire results across 7 fixed themes.
  - It adds knowledge vs practice, the disagreements and the recommended actions.
  - Questionnaire results appear as aggregates only, with no names and no ranking or recommending of people.
  - `consolidate=<dir>` builds the report from reports collected from separate per-repo runs.
  - Files: `references/consolidation.md`, `consolidation-template.md`, `consolidation-themes.md`, `consolidation-examples.md` and `scripts/summarize_audits.py` (`--json` prints the same facts as JSON).
- Step 5, the visual report `ai-audit/<project>-consolidated-<date>.pdf`. It is an 11-page A4-landscape management PDF of the consolidated report, with the same design for every project. Its pages:
  - a cover with the average score today and projected;
  - an executive summary;
  - the two-source comparison;
  - knowledge vs practice;
  - the disagreements;
  - a repository scorecard;
  - a security findings matrix;
  - the questionnaire results (aggregates only);
  - the actions;
  - a roadmap with an open-findings chart and the decisions for management;
  - sources and limits.

  It has no names, no per-person results and no ranking of people.
- A single-repo audit gets the same PDF, `ai-audit/<repo>-<date>.pdf`, built straight from its audit report, and so does a project or `consolidate=` folder with only one report. On a one-repo PDF the wording drops the project averages, and the one report counts as one respondent.
- `scripts/render_report.py` (standard library only) builds the PDF from the agent's narrative JSON and the audit reports, with `references/visual-report.md` and `assets/visual-report-example.json`:
  - It takes every number from the reports.
  - It rejects a findings matrix that doesn't add up to each report's stated Critical and High counts. It also rejects unknown repos or actions, URLs, email addresses and ranking words.
  - It escapes all text.
  - It prints with a local headless Chrome, Chromium or Edge (`AI_AUDIT_CHROME` overrides the choice).
  - It never overwrites a file. Without a browser it writes the HTML instead.
  - The pages have a fixed size, so it enforces measured caps on text length and list length, and allows at most 10 repos (exit 5 above that). Nothing is clipped silently.
- Guardrails G1–G12 that override any request:
  - assess but never fix;
  - fixed scores (disputes become a re-check revision);
  - a complete report and a truthful header;
  - secrets redacted, even for the user;
  - read-only (G6 allows one local, offline headless-browser print of the skill's own HTML);
  - this repository, or the confirmed project, only;
  - output only to `ai-audit/`, never overwritten, uploaded or sent (G8 also covers the PDF);
  - questionnaire integrity;
  - a fixed subject with no ranking of people;
  - only known arguments;
  - no edits to the skill itself.
- A PreToolUse guard hook for the Claude Code plugin. It hard-blocks the audit subagent from writes outside its report and from non-read-only commands. In project mode the subagent may touch only the manifest's current repository:
  - every shell command must start with `cd` into it;
  - Grep and Glob need a path inside it;
  - a folder that holds repositories but has no manifest fails closed.
- The audit excludes its own installed files (`ai-workflow-audit*`) from all evidence.
- Tests and CI:
  - `scripts/test_guard.py`, `scripts/test_consolidation.py` and `scripts/test_render.py`. Their fixtures and examples use a made-up project, Larkspur.
  - Red-team prompts for manual checks of model behaviour (`tests/redteam.md`).
  - Release checks: the Agent Skills spec, plugin manifests, version consistency, leftover TODOs, and no company name outside the author tag.
