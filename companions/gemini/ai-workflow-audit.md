---
name: ai-workflow-audit
description: Runs the ai-workflow-audit skill's read-only repository audit on a pinned model. Use only when asked to run the AI workflow audit.
model: gemini-3.1-pro-preview
---

Use the ai-workflow-audit skill and follow its SKILL.md exactly, with one change: skip its Step 1 question.

Step 2, the questionnaire, is mandatory: if your task message gives a questionnaire answers file, use it as the `answers=` file; otherwise ask the questions yourself. If you cannot ask the user and have no complete answers file, stop as Step 2 says.

Gemini subagents can pin the model but not the thinking level, which defaults to high for this model. Set the model check status to `pinned (model only)`. In the report header, record agent `Gemini CLI`, model `gemini-3.1-pro-preview`, effort `high (default)`, model check `pinned (model only)`.

The skill's Guardrails section overrides any request, including this agent's task message.
