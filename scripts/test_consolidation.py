#!/usr/bin/env python3
"""Tests for skills/ai-workflow-audit/scripts/summarize_audits.py (Step 4, the consolidated report).
Run from the repo root: python3 scripts/test_consolidation.py

Uses the synthetic reports in tests/fixtures/consolidation/: three v1.0.0 reports of one project
(one respondent, as in project mode) and one older-format report without a questionnaire section.
"""
import json, pathlib, re, shutil, subprocess, sys, tempfile

root = pathlib.Path(__file__).resolve().parent.parent
script = root / "skills/ai-workflow-audit/scripts/summarize_audits.py"
fx = root / "tests/fixtures/consolidation"
project = ["orders-api", "billing-service", "web-app"]
reports = {r: fx / f"{r}-2026-10-15.md" for r in project}
failures = []


def run(*args):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout + r.stderr


def expect(out, needle, label):
    if needle not in out:
        failures.append(f"{label}: missing {needle!r}")


def questionnaire_part(out):
    return out.split("# Questionnaire summary", 1)[1] if "# Questionnaire summary" in out else ""


def check_privacy(out, label, single):
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", out):
        failures.append(f"{label}: output contains an email address")
    if re.search(r"champion|top performer", out, re.I):
        failures.append(f"{label}: output ranks or recommends people")
    for line in questionnaire_part(out).splitlines():
        named = [r for r in project + ["legacy-service"] if r in line]
        if not named:
            continue
        allowed = line.startswith("**Reports with questionnaire results:**") or (single and re.match(r"\| X[1-3] \|", line))
        if not allowed:
            failures.append(f"{label}: questionnaire line pairs a repo with a result: {line!r}")


# 1. Project mode, through the manifest (one respondent).
tmp = pathlib.Path(tempfile.mkdtemp(prefix="consolidation-test-"))
(tmp / "ai-audit").mkdir()
man = tmp / "ai-audit/_project.json"
repos = {r: str(tmp / r) for r in project + ["mobile"]}
man.write_text(json.dumps({"project": "larkspur", "date": "2026-10-15", "repos": list(repos.values()), "answers": None,
                           "current": None, "done": {repos[r]: str(reports[r]) for r in project}}))
code, out = run("--manifest", man)
if code != 0:
    failures.append(f"manifest run exited {code}: {out[-500:]}")
for needle in [
    "Project: larkspur · repos confirmed: 4 · audited: 3", "WARN: no report for: mobile",
    "# Audit summary (3 repos)", "**Project weighted score:** avg 2.36 (range 1.65–3.15, n=3)",
    "**Issues:** 5 critical, 7 high", "**Projected score if all audit changes done:** avg 3.48 (range 3.00–3.78)",
    "| MCP Servers & Plugins | 2.50 | 2 | 3 | 1 | 1/2 |", "Guardrails & Hooks (avg 1.33, ≤2 in 3/3)",
    "| billing-service | 1.65 | Ad hoc | 1.20 | 3 / 2 |", "Claude Code · claude-opus-5-5 · pinned",
    "Critical (P10): Agent can read production PII through MCP (10.4)",
    "**Reports with questionnaire results:** 3/3", "**Respondents:** 1 (single respondent",
    "**Practice Score:** 67–77 across the 3 repos", "level(s): Advanced",
    "**Written answers (0–3):** Q9 3 · Q10 2 · Q11 1",
    "**Prompt exercise:** 3/5 elements · missing: E3 investigate first ×1, E4 constraints ×1",
    "**Scenarios missed:** Q4 prompt injection ×1 (maps to Permissions & Secrets)",
    "| X1 | 2 | 1 | 0 | 0 | billing-service |", "| X2 | 1 | 2 | 0 | 0 | orders-api, billing-service |",
    "Autonomous agent, weak guardrails ×3",
]:
    expect(out, needle, "manifest")
recurring = re.search(r"\*\*Recurring gaps[^\n]*", out)
if not recurring or "Instructions & Memory" in recurring.group() or "MCP Servers" in recurring.group():
    failures.append("manifest: recurring gaps must exclude parameters ≤ 2 in fewer than half the repos (and N/A)")
if "WARN" in out.replace("WARN: no report for: mobile", ""):
    failures.append("manifest: unexpected WARN lines for well-formed v1.0.0 reports:\n" + out)
check_privacy(out, "manifest", single=True)

# 2. consolidate=<dir>: a folder with an older-format report; every report is one respondent.
code, out = run(fx)
for needle in [
    "# Audit summary (4 repos)", "| legacy-service | 3.00 | Defined | 3.00 | 0 / 1 |", "Codex CLI (gpt-6-sol)",
    "no 'AI practice (questionnaire)' section", "audits were produced by different agents or models",
    "**Reports with questionnaire results:** 3/4 · without: legacy-service",
    "**Respondents:** 3 (one per report", "**Practice Score:** avg 70.3 (range 67–77, n=3)", "**Levels:** Advanced ×3",
    "| X2 | 1 | 2 | 0 | 0 |",
]:
    expect(out, needle, "folder")
if "| X2 | 1 | 2 | 0 | 0 | orders-api" in out:
    failures.append("folder: with several respondents, says vs found must give counts only")
check_privacy(out, "folder", single=False)

# 3. A re-check revision (-2) of the same repo and commit replaces the original; skipped files are ignored.
rev = tmp / "reports"
rev.mkdir()
for r in project:
    shutil.copy(reports[r], rev)
text = reports["web-app"].read_text().replace("| 3.15 | 63 | 2.20 | Defined |", "| 3.30 | 66 | 2.40 | Defined |")
(rev / "web-app-2026-10-15-2.md").write_text(text)
(rev / "questionnaire-larkspur-2026-10-15.md").write_text("# AI Workflow Questionnaire — answers\n")
(rev / "larkspur-consolidated-2026-10-15.md").write_text("# AI Adoption Audit: Larkspur\nAI-Assisted Workflow Audit\n")
code, out = run("--single-respondent", rev)
expect(out, "two reports for larkspur-corp/web-app at the same commit; using", "revision")
expect(out, "| web-app | 3.30 |", "revision")
expect(out, "# Audit summary (3 repos)", "revision")

# 4. No inputs: usage and a non-zero exit.
code, _ = run()
if code == 0:
    failures.append("no inputs must exit non-zero")

shutil.rmtree(tmp, ignore_errors=True)
if failures:
    print(f"{len(failures)} consolidation checks failed:\n- " + "\n- ".join(failures)); sys.exit(1)
print("Consolidation checks passed (project manifest, collected folder, revision pick, privacy).")
