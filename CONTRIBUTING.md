# Contributing to ai-workflow-audit

Thanks for helping. Contributions from outside the maintaining organisation are welcome.

## What helps most

- **Detection signals** for AI tools, config files or conventions the audit does not recognise yet.
- **Verification on other agents and models.** Only Claude Code with Claude Opus 5.5 at high effort is verified today. A documented run on Codex, Gemini or Antigravity, Cursor, GitHub Copilot or another agent is valuable (see below).
- **Bug fixes**, for example in the guard hook, the scripts or the PDF, with a test that fails before the fix.
- **Clearer wording** in the procedure, questionnaire or docs, as long as the meaning does not change.

**Open an issue first** for anything larger than a small fix, and always before changing the rubric, the questionnaire, the guardrails or the guard hook. Those changes affect every report, so they need agreement before code.

## Setup

- Python 3.11 or later. The scripts use the standard library only.
- To validate the skill, the Agent Skills reference validator: `pip install skills-ref==0.1.1`.
- To validate the plugin and run it, Claude Code: `npm install -g @anthropic-ai/claude-code`.
- Optional: Chrome, Chromium or Edge, so that `scripts/test_render.py` can print a real PDF. Without one, that part is skipped.

To try your changes in Claude Code without installing anything, run `claude --plugin-dir /path/to/ai-workflow-audit` in a test repository, then `/ai-workflow-audit`.

## Checks to run before a pull request

CI runs the same checks on every pull request:

```sh
agentskills validate skills/ai-workflow-audit
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .
python3 scripts/check_release.py
python3 scripts/test_guard.py
python3 scripts/test_consolidation.py
python3 scripts/test_render.py
```

If you change the procedure, the questionnaire, the guardrails or anything the model reads, also run the relevant prompts in [`tests/redteam.md`](tests/redteam.md) in a throwaway repository. In the pull request, say which rows you ran and what happened.

## Rules for changes

1. **Keep it agnostic.** The skill must work in any agent that supports skills and on any tech stack. Agent-specific behaviour belongs in a clearly labelled branch of the instructions, or in a companion file.
2. **Never weaken a guardrail.**
   - The audit is read-only, writes only to `ai-audit/` and never fixes what it finds (G1–G12 in `SKILL.md`).
   - A change to `hooks/ai-workflow-audit-guard.py` needs new cases in `scripts/test_guard.py`, both allowed and blocked.
   - Every shell command in the procedure must pass the guard; `test_guard.py` checks this automatically.
3. **The rubric and the questionnaire are fixed.** Changing a parameter, weight, threshold, cap, question, option, point value or level makes scores incomparable with earlier reports. Such a change:
   - needs an issue first;
   - bumps `rubric-version` or `questionnaire-version`;
   - is released as a new major version.
4. **No real data, anywhere.** Examples, fixtures, tests, issues and pull requests use made-up names; the existing ones use the fictional project "Larkspur". Never include any of these:
   - real audit reports or questionnaire answers;
   - names of companies, clients, projects, repositories or people;
   - secrets, even expired ones.

   Reviewers check this on every pull request.
5. **Self-exclusion prefix.** Every file in `agents/` and `companions/` must start with `ai-workflow-audit`, because the audit ignores its own installed files by that prefix.
6. **Keep `SKILL.md` lean** (under 500 lines). Put detail in `references/`.
7. **Plain, short wording.** The instructions are read by many different models, so prefer short sentences and explicit steps over clever phrasing.

## Reporting a run on another agent or model

Open an issue titled "Verification: <agent> + <model>" with:
- the agent and its version, the model, the effort setting, and the report header line (agent · model · effort · model check);
- whether the audit completed, and how long it took;
- the red-team rows you ran from `tests/redteam.md`, and the result of each;
- anything that went wrong.

Remove any secret, name or client detail before posting, and never attach a real report.

The maintainers mark an agent and model as verified once a complete run and the red-team prompts have passed.

## Versioning and the changelog

- Add your change to the top section of [`CHANGELOG.md`](CHANGELOG.md), under Added, Changed or Fixed.
- Maintainers set the version at release time. The version must match in `SKILL.md`, `plugin.json`, `marketplace.json`, the changelog and the reference files, and `check_release.py` enforces that.
- The semantic versioning rules are in the [README](README.md#versioning).

## Pull request checklist

- [ ] An issue exists for anything larger than a small fix.
- [ ] All checks above pass locally.
- [ ] Guard and behaviour changes come with tests, or with red-team results in the PR description.
- [ ] No real names, reports or secrets are added.
- [ ] `CHANGELOG.md` is updated.

## Security issues

Do not open a public issue for a vulnerability, for example a way past the guard hook or a way to leak secrets into a report. Report it privately through the repository's **Security** tab (**Report a vulnerability**).

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE) of this project.

Please be respectful and constructive in issues and reviews.
