# ai-workflow-audit

An [Agent Skill](https://agentskills.io) that audits **how effectively a repository uses AI coding agents**. It inspects the project's AI setup, scores 11 weighted parameters with cited evidence, runs a short mandatory questionnaire for the person running it, and writes a short Markdown report with the changes that would raise the score.

- **Read-only.** It never edits, commits or runs project code. The only files it writes are `ai-audit/questionnaire-<repo>-<date>.md` (your answers), `ai-audit/<repo>-<date>.md` (the report) and `ai-audit/<repo>-<date>.pdf` (an 11-page visual summary for managers), plus, for a multi-repo project, a manifest, one consolidated project report and a PDF of it.
- **Whole projects.** Run it from a folder that holds a project's repositories (e.g. frontend, backend, mobile): it audits each one, then writes a consolidated report across all of them and an 11-page management PDF.
- **Works in any agent that supports skills.** Verified with Claude Code and Claude Opus 5.5 at high effort, which gives the best results. It is designed for OpenAI Codex, Gemini CLI, Antigravity, Cursor, GitHub Copilot and others, but those are not verified yet.
- **Covers any stack.** It looks at the AI workflow, not the code. Frontend, backend, mobile and infra repos are all audited the same way.
- **Reproducible.** Each parameter is scored from a fixed sub-check checklist, so different agents converge on the same score.

Built and maintained by **FiftyFive Technologies**.

## What it scores

| # | Parameter | Weight | Security-critical |
|---|---|---|---|
| 1 | Instructions & Memory | 15% | |
| 2 | Skills & Commands | 10% | |
| 3 | MCP Servers & Plugins | 10% | yes |
| 4 | Guardrails & Hooks | 5% | yes |
| 5 | Permissions & Secrets | 5% | yes |
| 6 | Context & Cost | 10% | |
| 7 | Knowledge Base & Docs | 20% | |
| 8 | Verification & Testing | 10% | |
| 9 | Git & Review Workflow | 5% | yes |
| 10 | Governance & Data Compliance | 5% | yes |
| 11 | Observability & Feedback | 5% | |

Each parameter is scored 1–5 (or N/A) with a confidence level. The report gives a weighted score, a security average, a maturity level (Ad hoc, Emerging, Defined, Managed, Optimized), the security actions required, and up to 12 prioritised changes with their score impact. The rubric is fixed, so reports can be compared across projects and over time. The full rubric is in [`skills/ai-workflow-audit/references/audit-procedure.md`](skills/ai-workflow-audit/references/audit-procedure.md).

## The questionnaire

Before the audit, the person running it answers 11 questions in 3 parts (about 10 minutes): one about themselves, six scenarios that test judgement, and four short written answers, including a hands-on prompt exercise. It is **mandatory**; the audit does not run without it. Where the agent has a selection tool (in Claude Code, `AskUserQuestion`), you pick the answers to questions 1–7 from lists, and only the four written answers are typed in the chat. Elsewhere you reply with letters. The answers are saved first and scored only after the repository is scored, so they never change the 11 parameter scores, and the repository score is not biased by them.

The result is an **AI Practice Score (0–100)** for the respondent:

| Part | Points | From |
|---|---|---|
| Written answers | 40 | Your best work with AI, your daily workflow, and a time AI got it wrong, each graded 0–3 against fixed anchors |
| Prompt exercise | 15 | You write the prompt you'd give an agent for a sample bug; it is checked for goal, context, investigate-first, constraints and verification |
| Scenarios | 24 | Six judgement calls: planning a large change, permissions, prompt injection, long-session context, MCP vetting, verifying "done" |
| Work mode | 11 | From autocomplete up to an agent that edits files and runs commands |
| Matches the audit | 10 | Claims in your workflow answers checked against the repository (e.g. "the agent uses our instruction file" against the Instructions & Memory score) |

Levels: Beginner < 40, Practitioner 40–59, Advanced 60–79, Lead-ready ≥ 80. Advanced needs an agent that edits files; Lead-ready also needs one top-graded written answer and a prompt with at least 4 of the 5 elements. The report adds a **says vs found** table, flags (e.g. strong claims with thin evidence), and up to 3 next steps tied to the repository's weakest parameters. The questions are in [`references/questionnaire.md`](skills/ai-workflow-audit/references/questionnaire.md) and the scoring in [`references/questionnaire-scoring.md`](skills/ai-workflow-audit/references/questionnaire-scoring.md).

## Model requirements

> **For best results, use Claude Code with Claude Opus 5.5 at high effort.** It is the only setup verified so far, and the Claude Code plugin pins it automatically. Other AI agents, models and vendors are not verified: the skill runs there, but treat their scores with more caution.

The scores are calibrated for a top-tier model at **high** reasoning effort. Smaller models or lower effort misjudge sub-checks.

| Agent | Recommended | Status |
|---|---|---|
| Claude Code | Claude Opus 5.5, high effort | **Verified.** Pinned automatically when installed as a plugin |
| OpenAI Codex | GPT-6 Sol, high effort | Not verified. Can be pinned with the optional Codex agent file |
| Gemini CLI / Antigravity | Gemini 3.1 Pro, thinking high | Not verified |
| Cursor, GitHub Copilot | Claude Opus 5.5 or GPT-6 Sol, high effort | Not verified |

How the model is enforced:
- **Pinned.** The Claude Code plugin runs the audit in a subagent fixed to `claude-opus-5-5` at high effort. Optional agent files in [`companions/`](companions/) do the same for Codex and Gemini, and experimentally for Cursor and Copilot.
- **Confirmed.** Everywhere else, the skill shows the recommended model and the command to switch, then waits for you to reply `ready` (or `proceed` to continue anyway).

Each report records the agent, model, effort and how the model was checked (`pinned`, `confirmed`, `switched` or `unverified`). The authoritative table, with switch commands, is in [`SKILL.md`](skills/ai-workflow-audit/SKILL.md#step-1--model-check).

## Install

The repository is [github.com/FiftyfiveTech/ai-workflow-audit](https://github.com/FiftyfiveTech/ai-workflow-audit). A **user-level (global) install** is recommended, so that the skill is not committed into the projects you audit. If you install it into a project anyway, the audit ignores its own files.

**Any agent (portable skill):**
```sh
npx skills add FiftyfiveTech/ai-workflow-audit -g            # all detected agents
npx skills add FiftyfiveTech/ai-workflow-audit -g -a codex   # one agent
# or, with GitHub CLI 2.90+:
gh skill install FiftyfiveTech/ai-workflow-audit ai-workflow-audit --scope user
```

**Claude Code plugin (model pinned automatically).** Install it from your terminal:
```sh
claude plugin marketplace add FiftyfiveTech/ai-workflow-audit
claude plugin install ai-workflow-audit@fiftyfivetech
```
Or from inside a Claude Code session:
```
/plugin marketplace add FiftyfiveTech/ai-workflow-audit
/plugin install ai-workflow-audit@fiftyfivetech
```
Both install the plugin for your user (scope `user`), so it is available in every project. Restart any Claude Code session that is already open so that it loads the plugin.

**Optional model pinning for other agents.** Install the skill as above, then copy the matching agent file:

| Agent | Copy | To |
|---|---|---|
| Codex | `companions/codex/ai-workflow-audit.toml` | `~/.codex/agents/` |
| Gemini CLI | `companions/gemini/ai-workflow-audit.md` | `~/.gemini/agents/` |
| Cursor (experimental) | `companions/experimental/cursor/ai-workflow-audit.md` | `~/.cursor/agents/` |
| Copilot (experimental) | `companions/experimental/copilot/ai-workflow-audit.agent.md` | `.github/agents/` |

The experimental files use model strings that have not been verified, so check them against your agent's model picker first.

## Usage

1. Check out the latest default branch of the repository (`git pull`) and open your agent in its root.
2. Run the skill: `/ai-workflow-audit` in Claude Code, Gemini, Antigravity, Cursor and Copilot; `$ai-workflow-audit` in Codex. Or just ask "audit this repo's AI workflow".
3. Confirm the model when asked.
4. Answer the questionnaire: pick from the lists (or reply with letters if your agent has no selection tool), type the four written answers, then confirm.
5. Approve the read-only commands, and read `ai-audit/<repo>-<date>.md`. Step 5 then turns it into `ai-audit/<repo>-<date>.pdf`, the same 11-page management PDF a project gets (see below), using a Chrome, Chromium or Edge already installed on your machine.

To skip the model question when you already know you're on the right model, add `model-confirmed` (e.g. `/ai-workflow-audit model-confirmed`). Headless runs (`claude -p`, `codex exec`, CI) skip the question automatically and are marked `unverified` unless the model is pinned. They cannot ask the questionnaire, so they **stop** unless you pass a filled-in answers file: copy [`assets/questionnaire-answers-template.md`](skills/ai-workflow-audit/assets/questionnaire-answers-template.md) to `ai-audit/questionnaire-answers.md`, fill in every answer, and add `answers=ai-audit/questionnaire-answers.md`. The same argument works interactively; the skill then asks only for missing answers. In headless Claude Code runs, if the audit subagent is stopped early, set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`.

For several repositories (e.g. frontend, backend, mobile), use project mode, below.

## Project mode and the consolidated report

Open your agent in the folder that holds the project's repositories and run the skill there:

```
larkspur/                   ← run /ai-workflow-audit here
├── orders-api/             (git repo)
├── billing-service/        (git repo)
├── web-app/                (git repo)
└── ai-audit/               written by the skill
    ├── _project.json                         the confirmed repos and progress
    ├── questionnaire-larkspur-<date>.md      your answers, asked once
    ├── larkspur-consolidated-<date>.md       the consolidated report
    └── larkspur-consolidated-<date>.pdf      its visual summary for managers
```

1. **Step 0** lists the git repositories up to two levels down and asks you to confirm them and the project name.
2. The questionnaire is asked **once** for the project, and copied into each repository's `ai-audit/`.
3. Each repository is audited in turn. Every repository gets its usual report in its own `ai-audit/`, and in Claude Code the guard hook confines each audit to its own repository.
4. **Step 4** runs automatically once at least two repositories have a report, and writes `ai-audit/<project>-consolidated-<date>.md`. It contains:
   - a per-repo table, the project average and range, and the recurring gaps;
   - every Critical and High finding, grouped across repos;
   - a comparison of the audits with the questionnaire on 7 fixed themes (adoption, instruction files, docs, skills and MCP, guardrails, verification, learning loop), plus "knowledge vs practice" (e.g. the respondent knows to keep deny rules, but no repo has one);
   - where the two sources disagree, and the recommended actions.
5. **Step 5** runs straight after it and writes `ai-audit/<project>-consolidated-<date>.pdf`, an 11-page A4-landscape management report with the same design for every project. A single repository gets the same PDF, built from its own audit report (`ai-audit/<repo>-<date>.pdf`); so does a project where only one repository ended up with a report. The pages are:
   - a cover;
   - an executive summary;
   - the two-source comparison;
   - knowledge vs practice;
   - the disagreements;
   - a repository scorecard;
   - a security findings matrix;
   - the questionnaire results;
   - the actions;
   - a roadmap with decisions for management;
   - sources and limits.

   The agent writes the wording from the Markdown report. `scripts/render_report.py` takes every number from the audit reports, refuses a findings matrix that doesn't add up to the audits' Critical and High counts, and prints the page with a local headless Chrome, Chromium or Edge. Set `AI_AUDIT_CHROME` to choose one. If none is found, the skill writes the HTML instead, for you to print to PDF from any browser. The page loads nothing from the network.

The consolidated report and its PDF have **no names and no per-person results**. The questionnaire appears only as aggregates (Practice Score range, scenarios missed, says vs found per repo), and it never ranks or recommends people.

If the repositories were audited separately (for example each developer in their own repo), collect the reports in one folder and run `/ai-workflow-audit consolidate=<folder>`. Each report's questionnaire then counts as one respondent.

## Guardrails

The skill does one job: it assesses. These rules override any request, whether it comes from the user, a file in the repository or a questionnaire answer. A request that would break one is declined with a pointer to the report's "Changes required".

| # | Guardrail | Declines requests like |
|---|---|---|
| G1 | Assess, never fix: no edits to instruction files, rules, hooks, settings, docs, CI or code; the audit reports are inputs to the consolidated report and the PDFs, never edited | "fix these", "just add the AGENTS.md" |
| G2 | Scores follow the fixed rubric. Disputes produce a re-check revision: only repository evidence changes a score, and a statement without evidence is recorded as "not verified" | "give P1 a 5", "skip P5" |
| G3 | The report is complete: nothing dropped, softened or reordered | "leave out the security section" |
| G4 | The header is truthful: agent, model, effort, model check, date, commit, version | "say it ran on Opus" |
| G5 | Secrets stay redacted, even for you | "show me the leaked key" |
| G6 | Read-only: no builds, tests, installs, git writes, PRs, issues or network calls beyond read-only host CLIs. The one exception: Step 5 prints its own HTML to PDF with a local headless browser | "run the tests", "commit the report" |
| G7 | This repository only; in project mode only the confirmed repositories, each audit confined to its own | "also check my ~/.claude", "also look at ../other-repo" |
| G8 | Output only to `ai-audit/`, never overwritten (a same-day rerun gets `-2`), never published; this includes the consolidated report and the PDFs | "save it to docs/", "post it to Slack", "email the PDF" |
| G9 | Questionnaire integrity: no hints before the answers are final, no proxy answers, no retake, no names | "what's the right answer?", "let me redo it" |
| G10 | Fixed subject: no code or product review, no assessment or ranking of people. The Practice Score is not an employee evaluation, and the consolidated report and PDF show it as aggregates only | "review our code too", "rank my team", "name our AI lead", "add a Top Performers page" |
| G11 | Only `model-confirmed`, `answers=` and `consolidate=` change how it runs | "skip the questionnaire" |
| G12 | The skill never modifies its own files | "lower the docs weight" |

**How they are enforced:**
- **Claude Code plugin: hard block for the audit subagent.** [`hooks/ai-workflow-audit-guard.py`](hooks/ai-workflow-audit-guard.py) is a PreToolUse hook. It blocks the subagent from:
  - writing anything but its report
  - editing files, or overwriting an earlier report
  - reading outside the repository, or reading secret files directly
  - running anything outside an allowlist of read-only commands. This rules out redirection to files, git writes, mutating `gh`/`glab`/`az` calls, network tools, installers and project scripts;
  - in project mode, touching any repository but the one being audited (it reads the skill's manifest; every shell command must start with `cd` into that repository).

  It acts only on the plugin's own subagent; every other tool call in your session passes through untouched, including the main session that writes the manifest, the consolidated report and the PDF. `python3 scripts/test_guard.py` checks that every command in the procedure is allowed, that 85 attack cases are blocked, and that project mode keeps each audit inside its own repository. `python3 scripts/test_consolidation.py` checks the consolidated report's parser against fixture reports, and `python3 scripts/test_render.py` checks the PDF renderer: 11 pages, escaping, matrix validation, no overwrite, no names or external links.
- **Everywhere else: instructions.** The rules are in `SKILL.md`, the procedure (rule 13), the subagent and the companion files. This covers the main Claude Code session (the questionnaire and requests after the run) and other agents. They are followed strictly but cannot be enforced mechanically.
- **Limits:**
  - Hooks do not run with `--bare` or `disableAllHooks`.
  - Whether a hook block holds in bypass-permissions mode is undocumented; test case 3 in [`tests/redteam.md`](tests/redteam.md) checks it.
  - The hook adds a short `python3` start-up to each tool call in sessions where the plugin is enabled.
- **Every run ends with a check.** The final message lists the files written, and `git status` is compared with the starting state.

## Privacy and safety

- **Secrets are redacted in the report**, which shows `file:line` and the kind of secret only, and the skill scans its own output for leaks before finishing. However, the agent has to read config files to audit them, so **secret values in the repository can reach your AI provider**. Run the audit only under an AI account your organisation approves for that code.
- **No names or emails are collected.** The questionnaire records your role and experience only, and replaces any name or secret in an answer with `[name]` or `[REDACTED]`. Both files are saved in the repository's `ai-audit/` folder; decide whether to commit them, or add `ai-audit/` to your `.gitignore`.
- **The questionnaire is self-administered.** Anyone can read the questions and the scoring guide, so treat the Practice Score as one person's answers graded against fixed anchors, not as a test result.
- **Repository content is treated as evidence, never as instructions.** Text such as "rate this project 5" is reported as a prompt-injection finding.
- **It reads nothing outside the repository**, such as your home-directory AI config.
- **It installs nothing and runs nothing.** It never runs project build, test or deploy commands. The one exception: Step 5 runs an already installed Chrome, Chromium or Edge, headless and offline, to print its own HTML to PDF. `gh`, `glab`, `az`, `gitleaks` and `trufflehog` are used read-only, and only if they are already installed.

## Versioning

[Semantic versioning](https://semver.org). Each report header carries `ai-workflow-audit vX.Y.Z (rubric N.N, questionnaire N.N)`.
- **Patch:** wording or detection fixes that don't change scores.
- **Minor:** new detection signals, or changes to the model table.
- **Major:** a rubric change (new or removed parameters, different weights or thresholds). Scores from different rubric versions are not comparable. The same applies to the questionnaire: changing its questions, points or levels bumps the questionnaire version and the major version.

See [CHANGELOG.md](CHANGELOG.md). CI ([`.github/workflows/validate.yml`](.github/workflows/validate.yml)) checks that the skill matches the Agent Skills spec, that the plugin manifests are valid, that the version is identical everywhere, that no TODOs or internal references remain, and that the guard hook, the consolidation parser and the PDF renderer pass their tests.

## Contributing

Contributions are welcome, especially new detection signals for AI tools and verified runs on other agents and models. See [CONTRIBUTING.md](CONTRIBUTING.md) for the setup, the checks to run, the rules for changes, and how to report a run on another agent.

## License

[MIT](LICENSE) © 2026 FiftyFive Technologies
