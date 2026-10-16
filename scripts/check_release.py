#!/usr/bin/env python3
"""Release checks for ai-workflow-audit. Run from the repo root: python3 scripts/check_release.py"""
import json, pathlib, re, sys, tomllib

root = pathlib.Path(__file__).resolve().parent.parent
skill = root / "skills/ai-workflow-audit"
errors = []

def read(p): return (root / p).read_text()

# 1. One version everywhere.
skill_md = read("skills/ai-workflow-audit/SKILL.md")
fm = skill_md.split("---")[1]
versions = {
    "SKILL.md metadata.version": re.search(r'^\s+version:\s*"?([\d.]+)"?', fm, re.M).group(1),
    "plugin.json": json.loads(read(".claude-plugin/plugin.json"))["version"],
    "marketplace.json": json.loads(read(".claude-plugin/marketplace.json"))["plugins"][0]["version"],
    "CHANGELOG.md (latest)": re.search(r"^## \[([\d.]+)\]", read("CHANGELOG.md"), re.M).group(1),
}
proc = read("skills/ai-workflow-audit/references/audit-procedure.md")
consol = read("skills/ai-workflow-audit/references/consolidation.md") + read("skills/ai-workflow-audit/references/visual-report.md")
quest = read("skills/ai-workflow-audit/references/questionnaire.md")
qscore = read("skills/ai-workflow-audit/references/questionnaire-scoring.md")
qtemplate = read("skills/ai-workflow-audit/assets/questionnaire-answers-template.md")
stamps = set(re.findall(r"ai-workflow-audit v([\d.]+)", proc + quest + qscore + consol))
if len(set(versions.values())) != 1 or stamps != set(versions.values()):
    errors.append(f"Version mismatch: {versions}, report header stamp(s) {sorted(stamps)}")

# 2. Rubric version matches the procedure.
rubric = re.search(r'rubric-version:\s*"?([\d.]+)"?', fm).group(1)
if not set(re.findall(r"\(rubric ([\d.]+)\)", proc)) <= {rubric}:
    errors.append(f"Rubric version in SKILL.md ({rubric}) differs from audit-procedure.md")

# 2b. Questionnaire version matches everywhere, and the question list and answers template agree.
qver = re.search(r'questionnaire-version:\s*"?([\d.]+)"?', fm).group(1)
if set(re.findall(r"questionnaire ([\d.]+)", proc + quest + qscore + qtemplate)) != {qver}:
    errors.append(f"Questionnaire version in SKILL.md ({qver}) differs from the questionnaire files")
if sorted(int(n) for n in re.findall(r"^Q(\d+) ", qtemplate, re.M)) != list(range(1, 12)):
    errors.append("assets/questionnaire-answers-template.md must have exactly Q1-Q11")
if not all(f"\n{n}. " in quest for n in range(1, 12)):
    errors.append("references/questionnaire.md must number questions 1-11")

# 2c. The guard hook is wired up and tested.
hooks = json.loads(read("hooks/hooks.json"))
cmds = [h["command"] for e in hooks["hooks"]["PreToolUse"] for h in e["hooks"]]
if not any("hooks/ai-workflow-audit-guard.py" in c for c in cmds) or not (root / "hooks/ai-workflow-audit-guard.py").is_file():
    errors.append("hooks/hooks.json must run hooks/ai-workflow-audit-guard.py")
if not (root / "scripts/test_guard.py").is_file():
    errors.append("scripts/test_guard.py is missing")

# 2d. Consolidation (Step 4) and its PDF (Step 5) ship with their references and scripts, and never rank or name people.
for f in ("references/consolidation.md", "references/consolidation-template.md", "references/consolidation-themes.md",
          "references/consolidation-examples.md", "scripts/summarize_audits.py", "references/visual-report.md",
          "scripts/render_report.py", "assets/visual-report-example.json"):
    if not (skill / f).is_file():
        errors.append(f"skills/ai-workflow-audit/{f} is missing")
for f in ("references/consolidation-template.md", "references/consolidation-themes.md", "references/consolidation-examples.md",
          "assets/visual-report-example.json"):
    p = skill / f
    if p.is_file() and re.search(r"champion|top performer|leaderboard", p.read_text(), re.I):
        errors.append(f"{f}: the consolidated report must not rank or recommend people")
if "## Step 4" not in skill_md or "references/consolidation.md" not in skill_md:
    errors.append("SKILL.md must have Step 4 pointing to references/consolidation.md")
if "## Step 5" not in skill_md or "references/visual-report.md" not in skill_md:
    errors.append("SKILL.md must have Step 5 pointing to references/visual-report.md")
example = (skill / "assets/visual-report-example.json").read_text() if (skill / "assets/visual-report-example.json").is_file() else ""
for word in ("FiftyFive", "TODO"):
    if word in example:
        errors.append(f"assets/visual-report-example.json: internal reference '{word}'")
if re.search(r"(?i)https?://|fonts\.googleapis|<script", read("skills/ai-workflow-audit/scripts/render_report.py").split('CSS = """', 1)[-1].split('"""', 1)[0]):
    errors.append("render_report.py: the page CSS must not load anything external")

# 3. Manifests and companion files parse; every shipped agent/companion file uses the self-exclusion prefix.
tomllib.loads(read("companions/codex/ai-workflow-audit.toml"))
for p in list((root / "companions").rglob("*")) + list((root / "agents").glob("*")):
    if p.is_file() and not p.name.startswith(("ai-workflow-audit", ".")):
        errors.append(f"{p.relative_to(root)}: name must start with 'ai-workflow-audit' (the audit excludes its own files by this prefix)")

# 4. No unresolved TODOs or internal references inside the skill (including its scripts).
for p in [*skill.rglob("*.md"), *skill.rglob("*.py")]:
    text = p.read_text()
    if "TODO" in text:
        errors.append(f"{p.relative_to(root)}: unresolved TODO")
    if "FiftyFive" in text.replace('author: "FiftyFive Technologies"', ""):
        errors.append(f"{p.relative_to(root)}: 'FiftyFive' appears outside the author tag")

# 5. SKILL.md stays lean (Agent Skills guidance: under 500 lines).
if len(skill_md.splitlines()) > 500:
    errors.append("SKILL.md is over 500 lines")

if errors:
    print("Release checks failed:\n- " + "\n- ".join(errors)); sys.exit(1)
print(f"Release checks passed (v{versions['plugin.json']}, rubric {rubric}, questionnaire {qver}).")
