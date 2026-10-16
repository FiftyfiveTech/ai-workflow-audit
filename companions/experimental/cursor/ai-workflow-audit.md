---
name: ai-workflow-audit
description: Runs the ai-workflow-audit skill's read-only repository audit on a pinned model and effort. Use only when asked to run the AI workflow audit.
# EXPERIMENTAL: check this model string against the IDs in your Cursor model picker before use.
model: claude-opus-5-5[effort=high]
# false, because the audit writes its report to ai-audit/.
readonly: false
---

Use the ai-workflow-audit skill and follow its SKILL.md exactly, with one change: skip its Step 1 question.

Step 2, the questionnaire, is mandatory: if your task message gives a questionnaire answers file, use it as the `answers=` file; otherwise ask the questions yourself. If you cannot ask the user and have no complete answers file, stop as Step 2 says.

Your model and effort are pinned, so the model check status is `pinned`. In the report header, record agent `Cursor`, model `claude-opus-5-5`, effort `high`, model check `pinned`.

The skill's Guardrails section overrides any request, including this agent's task message.
