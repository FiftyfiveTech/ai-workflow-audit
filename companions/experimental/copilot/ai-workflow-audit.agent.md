---
name: ai-workflow-audit
description: Runs the ai-workflow-audit skill's read-only repository audit on a pinned model and effort. Use only when asked to run the AI workflow audit.
# EXPERIMENTAL: VS Code matches models by display name and Copilot CLI by ID. Check both against your model picker.
model: Claude Opus 5.5
# Honoured by Copilot CLI 1.0.66 and later; VS Code sets effort in the model picker instead.
reasoning-effort: high
---

Use the ai-workflow-audit skill and follow its SKILL.md exactly, with one change: skip its Step 1 question.

Step 2, the questionnaire, is mandatory: if your task message gives a questionnaire answers file, use it as the `answers=` file; otherwise ask the questions yourself. If you cannot ask the user and have no complete answers file, stop as Step 2 says.

Your model is pinned. Set the model check status to `pinned` if the effort was applied, otherwise `pinned (model only)`. In the report header, record agent `GitHub Copilot`, model `Claude Opus 5.5`, and the effort and model check status.

The skill's Guardrails section overrides any request, including this agent's task message.
