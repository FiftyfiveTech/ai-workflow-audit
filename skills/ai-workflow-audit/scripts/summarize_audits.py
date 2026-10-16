#!/usr/bin/env python3
"""Summarise the ai-workflow-audit reports of one project for the consolidated report.

Usage:
  python3 summarize_audits.py --manifest <project-root>/ai-audit/_project.json
  python3 summarize_audits.py [--single-respondent] <report.md | folder> [...]
  add --json to print the same facts as JSON (for render_report.py, the Step 5 visual report)

A folder is searched recursively for audit reports (title contains "AI-Assisted Workflow
Audit"); questionnaire answer files and earlier consolidated reports are skipped. When a repo
has several reports (re-check revisions), the latest one is used. --manifest reads the
reports listed under "done" and implies --single-respondent (project mode asks the
questionnaire once).

Prints a Markdown summary: per-repo table, project average and range, per-parameter
averages, recurring gaps (<= 2 in at least half the repos), Critical/High findings, and the
questionnaire results as aggregates only. It never prints a Practice Score next to a repo,
and never prints names. Prints WARN lines when a report can't be fully parsed.
Standard library only.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

PARAMS = [
    "Instructions & Memory", "Skills & Commands", "MCP Servers & Plugins",
    "Guardrails & Hooks", "Permissions & Secrets", "Context & Cost",
    "Knowledge Base & Docs", "Verification & Testing", "Git & Review Workflow",
    "Governance & Data Compliance", "Observability & Feedback",
]
# Scenario question -> audit parameters it maps to (questionnaire-scoring.md, Section 2).
SCENARIO_PARAMS = {
    "2": "Context & Cost", "3": "Guardrails & Hooks / Permissions & Secrets",
    "4": "Permissions & Secrets", "5": "Context & Cost", "6": "MCP Servers & Plugins",
    "7": "Verification & Testing / Git & Review Workflow",
}
SCENARIO_TOPIC = {
    "2": "planning a large change", "3": "permissions setup", "4": "prompt injection",
    "5": "long-session context", "6": "MCP vetting", "7": "verifying 'done'",
}
ELEMENTS = {"E1": "goal and done-criteria", "E2": "context", "E3": "investigate first",
            "E4": "constraints", "E5": "verification"}
WORK_MODE = {0: "a) no AI", 2: "b) inline autocomplete", 3: "c) copy-paste from chat",
             8: "d) agent edits files", 11: "e) agent edits files and runs commands"}
# The 7 comparison themes and the audit parameters that feed each (consolidation-themes.md).
THEMES = [
    ("Adoption & usage", []),
    ("Instruction files & project map", ["Instructions & Memory", "Context & Cost"]),
    ("Knowledge base & docs", ["Knowledge Base & Docs"]),
    ("Skills, commands & MCP", ["Skills & Commands", "MCP Servers & Plugins"]),
    ("Guardrails, permissions & secrets", ["Guardrails & Hooks", "Permissions & Secrets"]),
    ("Verification & review", ["Verification & Testing", "Git & Review Workflow"]),
    ("Learning loop & governance", ["Governance & Data Compliance", "Observability & Feedback"]),
]
CHECK_STATUSES = ("pinned", "confirmed", "switched", "unverified")
TITLE = "AI-Assisted Workflow Audit"


WARNINGS = None  # a list while collecting warnings for --json; None prints them


def warn(msg):
    if WARNINGS is None:
        print(msg)
    else:
        WARNINGS.append(msg)


def cells(line):
    line = line.strip()
    if not line.startswith("|"):
        return None
    return [c.strip() for c in line.strip("|").split("|")]


def is_rule(c):
    return set("".join(c)) <= set("-: ")


def heading(ln):
    """'## 6. AI practice (questionnaire)' -> 'ai practice (questionnaire)'."""
    return re.sub(r"^\d+[.)]\s*", "", ln[3:].strip()).lower()


def section(lines, title):
    """Lines of the '## <title>...' section (heading numbering ignored)."""
    out, inside = [], False
    for ln in lines:
        if ln.startswith("## "):
            inside = heading(ln).startswith(title.lower())
            continue
        if inside:
            out.append(ln)
    return out


def tables(lines):
    """Every Markdown table in lines, as (header_lowercased, rows)."""
    found, header, rows = [], None, []
    for ln in lines + [""]:
        c = cells(ln)
        if c is None:
            if header is not None:
                found.append((header, rows))
            header, rows = None, []
            continue
        if header is None:
            header = [h.lower() for h in c]
        elif not is_rule(c):
            rows.append(c)
    return found


def num(s):
    m = re.search(r"-?\d+(\.\d+)?", s or "")
    return float(m.group()) if m else None


def fmt(v):
    if v is None:
        return "N/A"
    return f"{v:.2f}".rstrip("0") if isinstance(v, float) and v % 1 else f"{v:g}"


def score2(v):
    """Weighted and security scores always show 2 decimals, as the reports do."""
    return "N/A" if v is None else f"{v:.2f}"


def parse_header(lines, r, warns):
    head = [ln.strip() for ln in lines[1:8]]
    for s in head:
        if s and not s.startswith(("#", "*")) and "·" in s and "ai-workflow-audit v" not in s:
            r["repo"] = re.sub(r"(?i)^repository:\s*", "", s.split("·")[0].strip()).strip("`")
            m = re.search(r"\((?:[^)]*/)?([\w.-]+/[\w.-]+)\)", s)
            r["org_repo"] = m.group(1) if m else None
            h = re.search(r"\b([0-9a-f]{7,40})\b", s.split("·", 1)[1] if "·" in s else "")
            r["head"] = h.group(1) if h else None
            d = re.search(r"\d{4}-\d{2}-\d{2}", s)
            r["date"] = d.group() if d else None
            # Older format: everything on one line, "· audited by <tool> (<model>) · prompt v2.0".
            a = re.search(r"audited by\s*([^·]+?)\s*·\s*prompt", s)
            if a:
                r["agent"] = a.group(1).strip()
            break
    for s in head:
        if "ai-workflow-audit v" in s:
            parts = [p.strip() for p in s.split("·")]
            r["agent"] = parts[0] if parts else None
            r["model"] = parts[1] if len(parts) > 1 else None
            r["effort"] = next((re.sub(r"(?i)^effort\s*", "", p) for p in parts if "effort" in p.lower()), None)
            r["check"] = next((st for p in parts for st in CHECK_STATUSES if st in p.lower()), None)
            v = re.search(r"ai-workflow-audit v([\d.]+)", s)
            r["version"] = v.group(1) if v else None
            break
    if not r.get("repo"):
        warns.append("repo line not found")


def scoped(lines, title, want):
    """The section's lines; if the report has no such heading, the whole report (tables are then
    picked by their header row, via want)."""
    sec = section(lines, title)
    return sec if any(want(h) for h, _ in tables(sec)) else lines


def parse_audit(lines, r, warns):
    summ = scoped(lines, "Score summary", lambda h: any("weighted" in x for x in h))
    for header, rows in tables(summ):
        if rows and any("weighted" in h for h in header):
            row = dict(zip(header, rows[0]))
            get = lambda key: next((v for k, v in row.items() if key in k), None)
            r["score"] = num(get("weighted"))
            r["security_avg"] = num(get("security"))
            r["maturity"] = (get("maturity") or "").strip()
            r["critical"] = int(num(get("critical")) or 0)
            r["high"] = int(num(get("high")) or 0)
            r["tools"] = get("tools") or ""
            break
    if r.get("score") is None:
        warns.append("score summary row not found (or 'Not rated')")
    r["risk_line"] = next((ln.strip() for ln in summ if ln.strip() and not ln.strip().startswith("|")
                           and (summ is not lines or "risk" in ln.lower())), None)

    r["params"] = {}
    for header, rows in tables(scoped(lines, "Scorecard", lambda h: "parameter" in h and "score" in h)):
        if not ("parameter" in header and "score" in header):
            continue
        si = next((i for i, h in enumerate(header) if h == "score"), 4)
        wi = next((i for i, h in enumerate(header) if h.startswith("why")), len(header) - 1)
        for c in rows:
            if not c[0].isdigit():
                continue
            idx = int(c[0])
            name = PARAMS[idx - 1] if 1 <= idx <= 11 else c[1]
            cell = c[si] if si < len(c) else ""
            v = None if "n/a" in cell.lower() else num(cell)
            r["params"][name] = {"score": v, "why": c[wi] if wi < len(c) else ""}
    if len(r["params"]) < 11:
        warns.append(f"scorecard has {len(r['params'])}/11 parameters")

    r["security"] = []
    for header, rows in tables(scoped(lines, "Security actions", lambda h: h[:1] == ["severity"])):
        if header[:1] != ["severity"]:
            continue
        for c in rows:
            if c[0].lower() in ("critical", "high", "medium", "low"):
                r["security"].append({"severity": c[0], "param": c[1] if len(c) > 1 else "",
                                      "finding": c[2] if len(c) > 2 else ""})

    m = re.search(r"Projected Weighted Score[^:]*:\s*\**\s*([\d.]+)\s*\(([^)]+)\)", "\n".join(lines))
    r["projected"] = (float(m.group(1)), m.group(2)) if m else None


def parse_practice(lines, warns):
    sec = section(lines, "AI practice")
    if not sec:
        warns.append("no 'AI practice (questionnaire)' section")
        return None
    text = "\n".join(sec)
    if re.search(r"questionnaire:\s*not available", text, re.I):
        return {"available": False}
    q = {"available": True}
    for ln in sec:
        s = ln.strip().lstrip("-* ").replace("**", "")
        if "·" in s and re.search(r"\b(interactive|file)\b", s) and not s.startswith("|"):
            parts = [p.strip() for p in re.sub(r"(?i)^respondent:\s*", "", s).split("·")]
            q["role"], q["experience"] = parts[0], parts[1] if len(parts) > 1 else None
            q["collected"] = "interactive" if "interactive" in s else "file"
            break
    for header, rows in tables(sec):
        if rows and any("practice score" in h for h in header):
            row = dict(zip(header, rows[0]))
            get = lambda key: next((v for k, v in row.items() if key in k), None)
            q.update(score=num(get("practice score")), level=(get("level") or "").strip(),
                     written=num(get("written")), prompt=num(get("prompt")), scenarios=num(get("scenario")),
                     workmode=num(get("work mode")), matches=num(get("matches")))
        if rows and "row" in header[0] and any("verdict" in h for h in header):
            q["claims"] = {c[0].upper(): c[-1].strip().lower() for c in rows if re.match(r"(?i)x[1-3]$", c[0])}
    if q.get("score") is None:
        warns.append("Practice Score row not found")
    for ln in sec:
        s = ln.replace("**", "")
        if "Prompt exercise" in s and "/5" in s:
            m = re.search(r"(\d)\s*/\s*5", s)
            q["elements"] = int(m.group(1)) if m else None
            miss = s.split("missing", 1)[1] if "missing" in s else ""
            q["missing"] = sorted(set(re.findall(r"E[1-5]", miss)))
        if re.search(r"Scenarios:", s):
            q["missed"] = [] if re.search(r"6\s*/\s*6", s) else sorted(set(re.findall(r"Q([2-7])\b", s)))
        if re.search(r"Flags:", s):
            body = s.split("Flags:", 1)[1].strip()
            q["flags"] = [] if re.match(r"(?i)none", body) else [f.strip(" .") for f in body.split(";") if f.strip(" .")]
    q["grades"] = {k: int(v) for k, v in re.findall(r"\bQ(9|10|11)\s*·\s*([0-3])\b", text)}
    return q


def flag_kind(f):
    fl = f.lower()
    if "thin evidence" in fl:
        return "Strong claims, thin evidence"
    if "weak guardrails" in fl:
        return "Autonomous agent, weak guardrails"
    if "contradicted" in fl:
        return "Claim contradicted by the audit"
    if "influence" in fl:
        return "Answer tried to influence grading"
    return f


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    warns = []
    r = {"file": path, "repo": None, "date": None}
    parse_header(lines, r, warns)
    parse_audit(lines, r, warns)
    r["practice"] = parse_practice(lines, warns)
    return r, warns


def is_report(path):
    name = os.path.basename(path)
    if not name.endswith(".md") or name.startswith(("questionnaire-", "_")) or "-consolidated-" in name:
        return False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return TITLE in "".join(f.readline() for _ in range(3))
    except OSError:
        return False


def collect(args):
    paths = []
    for a in args:
        if os.path.isdir(a):
            for d, _, files in os.walk(a):
                paths += [os.path.join(d, f) for f in sorted(files) if is_report(os.path.join(d, f))]
        elif os.path.isfile(a):
            paths.append(a)
        else:
            warn(f"WARN {a}: not found")
    return paths


def latest_per_repo(reports):
    """Keep the latest report per repo and commit (date, then -2/-3 revision suffix)."""
    def key(r):
        m = re.search(r"-(\d+)\.md$", r["file"])
        return (r.get("date") or "", int(m.group(1)) if m and not re.search(r"\d{4}-\d{2}-\d{2}\.md$", r["file"]) else 1)
    best = {}
    for r in reports:
        k = (r.get("org_repo") or r.get("repo") or r["file"], r.get("head"))
        if k in best:
            old = best[k]
            keep, drop = (r, old) if key(r) >= key(old) else (old, r)
            warn(f"WARN: two reports for {k[0]} at the same commit; using {keep['file']}, ignoring {drop['file']}")
            best[k] = keep
        else:
            best[k] = r
    return list(best.values())


def print_audits(reports):
    print(f"# Audit summary ({len(reports)} repo{'s' if len(reports) != 1 else ''})\n")
    print("| Repo | Score | Maturity | Security avg | Critical / High | Weakest (≤2) | Agent · model · check | Date |")
    print("|---|---|---|---|---|---|---|---|")
    for r in reports:
        weak = sorted((v["score"], k) for k, v in r["params"].items() if v["score"] is not None and v["score"] <= 2)
        weak_s = ", ".join(f"{k} ({fmt(s)})" for s, k in weak[:4]) or "—"
        who = " · ".join(x for x in (r.get("agent"), r.get("model"), r.get("check")) if x) or "unknown"
        print(f"| {r['repo']} | {score2(r.get('score'))} | {r.get('maturity')} | {score2(r.get('security_avg'))} | "
              f"{r.get('critical')} / {r.get('high')} | {weak_s} | {who} | {r.get('date')} |")

    scores = [r["score"] for r in reports if r.get("score") is not None]
    if scores:
        print(f"\n**Project weighted score:** avg {sum(scores)/len(scores):.2f} "
              f"(range {min(scores):.2f}–{max(scores):.2f}, n={len(scores)})")
    mats = Counter(r.get("maturity") for r in reports if r.get("maturity"))
    print("**Maturity bands:** " + (", ".join(f"{v} {k}" for k, v in mats.most_common()) or "none"))
    print(f"**Issues:** {sum(r.get('critical', 0) for r in reports)} critical, "
          f"{sum(r.get('high', 0) for r in reports)} high")
    proj = [r["projected"][0] for r in reports if r.get("projected")]
    if proj:
        print(f"**Projected score if all audit changes done:** avg {sum(proj)/len(proj):.2f} "
              f"(range {min(proj):.2f}–{max(proj):.2f})")
    setups = Counter(f"{r.get('agent')} ({r.get('model') or '?'})" for r in reports)
    if len(setups) > 1:
        print("**Note:** audits were produced by different agents or models: "
              + ", ".join(f"{k} ×{v}" for k, v in setups.items()))
    unverified = [r["repo"] for r in reports if r.get("check") == "unverified"]
    if unverified:
        print("**Note:** model check 'unverified' in: " + ", ".join(unverified))
    versions = Counter(r.get("version") or "older format" for r in reports)
    if len(versions) > 1:
        print("**Note:** mixed report versions: " + ", ".join(f"{k} ×{v}" for k, v in versions.items()))

    print("\n## Per-parameter averages\n")
    print("| Parameter | Avg | Min | Max | N/A repos | Repos ≤ 2 |")
    print("|---|---|---|---|---|---|")
    recurring = []
    for p in PARAMS:
        present = [r["params"][p]["score"] for r in reports if r["params"].get(p, {}).get("score") is not None]
        na = sum(1 for r in reports if p in r["params"] and r["params"][p]["score"] is None)
        low = sum(1 for v in present if v <= 2)
        avg = sum(present) / len(present) if present else None
        print(f"| {p} | {f'{avg:.2f}' if avg is not None else 'N/A'} | "
              f"{fmt(min(present)) if present else '—'} | {fmt(max(present)) if present else '—'} | {na} | {low}/{len(present)} |")
        if present and low >= len(reports) / 2:
            recurring.append(f"{p} (avg {avg:.2f}, ≤2 in {low}/{len(reports)})")
    print("\n**Recurring gaps (≤ 2 in at least half the repos):** " + ("; ".join(recurring) or "none"))

    print("\n## Critical / High security findings by repo\n")
    for r in reports:
        print(f"- **{r['repo']}**" + (f": {r['risk_line'][:300]}" if r.get("risk_line") else ""))
        for s in r["security"]:
            if s["severity"].lower() in ("critical", "high"):
                print(f"  - {s['severity']} (P{s['param'].lstrip('Pp')}): {s['finding'][:220]}")


def print_questionnaire(reports, single):
    qs = [(r["repo"], r["practice"]) for r in reports if r.get("practice") and r["practice"].get("available")]
    missing = [r["repo"] for r in reports if not (r.get("practice") and r["practice"].get("available"))]
    print("\n# Questionnaire summary (aggregate only; never pair a Practice Score with a repo or a person)\n")
    print(f"**Reports with questionnaire results:** {len(qs)}/{len(reports)}"
          + (f" · without: {', '.join(missing)}" if missing else ""))
    if not qs:
        print("No questionnaire results: the Questionnaire column of the comparison is 'Not available'.")
        return
    n = 1 if single else len(qs)
    print(f"**Respondents:** {n}" + (" (single respondent: one answers file reused for every repo)" if single
                                     else " (one per report; reports cannot be de-duplicated without names)"))
    people = [qs[0][1]] if single else [q for _, q in qs]

    def counts(key, conv=lambda v: v):
        return "; ".join(f"{k} ×{v}" for k, v in Counter(conv(p.get(key)) for p in people if p.get(key) is not None).most_common())
    print(f"**Profile:** role {counts('role')} · experience {counts('experience')} · "
          f"work mode {counts('workmode', lambda v: WORK_MODE.get(int(v), fmt(v)))} · answers {counts('collected')}")

    scores = [q["score"] for _, q in qs if q.get("score") is not None]
    if single:
        person = {k: {fmt(q.get(k)) for _, q in qs} for k in ("written", "prompt", "scenarios", "workmode", "elements")}
        for k, vals in person.items():
            if len(vals) > 1:
                print(f"WARN: '{k}' differs between reports although there is one respondent: {sorted(vals)}")
        if scores:
            print(f"**Practice Score:** {fmt(min(scores))}–{fmt(max(scores))} across the {len(qs)} repos "
                  "(only 'Matches audit' changes with each repo's evidence) · level(s): "
                  + ", ".join(sorted({q.get('level') for _, q in qs if q.get('level')})))
        p = qs[0][1]
        print(f"**Parts:** written {fmt(p.get('written'))}/40 · prompt exercise {fmt(p.get('prompt'))}/15 · "
              f"scenarios {fmt(p.get('scenarios'))}/24 · work mode {fmt(p.get('workmode'))}/11 · "
              f"matches audit {', '.join(sorted({fmt(q.get('matches')) for _, q in qs}))}/10 (per repo)")
    else:
        if scores:
            print(f"**Practice Score:** avg {sum(scores)/len(scores):.1f} (range {fmt(min(scores))}–{fmt(max(scores))}, n={len(scores)})")
        print("**Levels:** " + counts("level"))
        for k, mx in (("written", 40), ("prompt", 15), ("scenarios", 24), ("workmode", 11), ("matches", 10)):
            vals = [q[k] for q in people if q.get(k) is not None]
            if vals:
                print(f"- {k}: avg {sum(vals)/len(vals):.1f}/{mx} (min {fmt(min(vals))}, max {fmt(max(vals))})")

    grades = {k: [q["grades"][k] for q in people if k in q.get("grades", {})] for k in ("9", "10", "11")}
    print("**Written answers (0–3):** " + " · ".join(
        f"Q{k} {'avg ' + format(sum(v)/len(v), '.1f') if len(v) > 1 else fmt(v[0]) if v else 'n/a'}" for k, v in grades.items()))
    els = [q["elements"] for q in people if q.get("elements") is not None]
    miss = Counter(e for q in people for e in q.get("missing", []))
    print(f"**Prompt exercise:** {('avg ' + format(sum(els)/len(els), '.1f')) if len(els) > 1 else (fmt(els[0]) if els else 'n/a')}/5 elements"
          + (" · missing: " + ", ".join(f"{e} {ELEMENTS[e]} ×{c}" for e, c in sorted(miss.items())) if miss else ""))
    missed = Counter(m for q in people for m in q.get("missed", []))
    if any("missed" in q for q in people):
        print("**Scenarios missed:** " + ("; ".join(
            f"Q{k} {SCENARIO_TOPIC[k]} ×{c} (maps to {SCENARIO_PARAMS[k]})" for k, c in sorted(missed.items())) or "none"))

    print("\n**Says vs found (per repo, claim checked against that repo's audit):**\n")
    print("| Row | Consistent | Contradicted | Not checkable | No claim |" + (" Contradicted in |" if single else ""))
    print("|---|---|---|---|---|" + ("---|" if single else ""))
    for row in ("X1", "X2", "X3"):
        verdicts = [(repo, q.get("claims", {}).get(row, "")) for repo, q in qs]
        c = Counter(v for _, v in verdicts)
        where = ", ".join(repo for repo, v in verdicts if v == "contradicted") or "—"
        print(f"| {row} | {c['consistent']} | {c['contradicted']} | {c['not checkable']} | {c['no claim']} |"
              + (f" {where} |" if single else ""))
    flags = Counter(flag_kind(f) for _, q in qs for f in q.get("flags", []))
    print("\n**Flags (per report):** " + ("; ".join(f"{k} ×{v}" for k, v in flags.most_common()) or "none"))


def avg(vals):
    return round(sum(vals) / len(vals), 2) if vals else None


def facts(reports, single, info):
    """The facts print_audits and print_questionnaire show, as one dict for --json.
    Same privacy rules: no Practice Score, level or answer is paired with a repo."""
    scores = [r["score"] for r in reports if r.get("score") is not None]
    proj = [r["projected"][0] for r in reports if r.get("projected")]
    params = []
    for p in PARAMS:
        present = [r["params"][p]["score"] for r in reports if r["params"].get(p, {}).get("score") is not None]
        params.append({"name": p, "avg": avg(present), "min": min(present) if present else None,
                       "max": max(present) if present else None,
                       "na": sum(1 for r in reports if p in r["params"] and r["params"][p]["score"] is None),
                       "low": sum(1 for v in present if v <= 2), "rated": len(present)})
    pavg = {p["name"]: p["avg"] for p in params}
    out = {
        **info,
        "repos": [{"repo": r["repo"], "score": r.get("score"), "maturity": r.get("maturity"),
                   "security_avg": r.get("security_avg"), "critical": r.get("critical", 0), "high": r.get("high", 0),
                   "projected": r["projected"][0] if r.get("projected") else None,
                   "projected_band": r["projected"][1].strip() if r.get("projected") else None,
                   "params": {k: v["score"] for k, v in r["params"].items()},
                   "agent": r.get("agent"), "model": r.get("model"), "check": r.get("check"),
                   "date": r.get("date"), "version": r.get("version")} for r in reports],
        "average": avg(scores), "range": [min(scores), max(scores)] if scores else None,
        "bands": dict(Counter(r.get("maturity") for r in reports if r.get("maturity")).most_common()),
        "critical": sum(r.get("critical", 0) for r in reports), "high": sum(r.get("high", 0) for r in reports),
        "projected_average": avg(proj), "projected_range": [min(proj), max(proj)] if proj else None,
        "params": params,
        "recurring": [p["name"] for p in params if p["rated"] and p["low"] >= len(reports) / 2],
        "themes": [{"theme": t, "params": ps,
                    "avg": avg([pavg[p] for p in ps if pavg[p] is not None])} for t, ps in THEMES],
        "mixed_setups": len({(r.get("agent"), r.get("model")) for r in reports}) > 1,
        "unverified": [r["repo"] for r in reports if r.get("check") == "unverified"],
    }
    qs = [(r["repo"], r["practice"]) for r in reports if r.get("practice") and r["practice"].get("available")]
    q = {"reports_with_results": len(qs),
         "without": [r["repo"] for r in reports if not (r.get("practice") and r["practice"].get("available"))]}
    if qs:
        people = [qs[0][1]] if single else [x for _, x in qs]
        ps = [x["score"] for _, x in qs if x.get("score") is not None]
        count = lambda key: dict(Counter(p.get(key) for p in people if p.get(key) is not None).most_common())
        grades = {k: [p["grades"][k] for p in people if k in p.get("grades", {})] for k in ("9", "10", "11")}
        els = [p["elements"] for p in people if p.get("elements") is not None]
        claims = {}
        for row in ("X1", "X2", "X3"):
            verdicts = [(repo, x.get("claims", {}).get(row, "")) for repo, x in qs]
            c = Counter(v for _, v in verdicts)
            claims[row] = {k: c[k] for k in ("consistent", "contradicted", "not checkable", "no claim")}
            if single:
                claims[row]["contradicted_in"] = [repo for repo, v in verdicts if v == "contradicted"]
        q.update({
            "respondents": 1 if single else len(qs), "single": single,
            "score_min": min(ps) if ps else None, "score_max": max(ps) if ps else None, "score_avg": avg(ps),
            "levels": count("level"), "roles": count("role"), "experience": count("experience"),
            "work_mode": {WORK_MODE.get(int(k), fmt(k)): v for k, v in count("workmode").items()},
            "parts": {k: avg([p[k] for p in people if p.get(k) is not None]) for k in ("written", "prompt", "scenarios", "workmode")},
            "parts_max": {"written": 40, "prompt": 15, "scenarios": 24, "workmode": 11},
            "grades": {k: avg(v) for k, v in grades.items()},
            "elements": avg(els),
            "elements_missing": dict(Counter(e for p in people for e in p.get("missing", []))),
            "element_names": ELEMENTS,
            "scenarios_missed": dict(Counter(m for p in people for m in p.get("missed", []))),
            "scenario_topics": SCENARIO_TOPIC, "scenario_params": SCENARIO_PARAMS,
            "claims": claims,
            "flags": dict(Counter(flag_kind(f) for _, x in qs for f in x.get("flags", [])).most_common()),
        })
    out["questionnaire"] = q
    return out


def load(inputs, manifest=None, single=False):
    """Collect and parse the reports. Returns (reports, single, info); info["warnings"] lists every WARN line."""
    global WARNINGS
    WARNINGS = []
    inputs, info = list(inputs), {"project": None, "repos_confirmed": None, "missing_repos": []}
    if manifest:
        with open(manifest, encoding="utf-8") as f:
            man = json.load(f)
        base = os.path.dirname(os.path.dirname(os.path.abspath(manifest)))
        inputs += [p if os.path.isabs(p) else os.path.join(base, p) for p in (man.get("done") or {}).values()]
        single = True
        info.update(project=man.get("project"), repos_confirmed=len(man.get("repos") or []), audited=len(man.get("done") or {}),
                    missing_repos=[os.path.basename(p) for p in man.get("repos") or [] if p not in (man.get("done") or {})])
        if info["missing_repos"]:
            warn("WARN: no report for: " + ", ".join(info["missing_repos"]) + " (say so under Limits)")
    reports = []
    for p in collect(inputs):
        r, w = parse(p)
        for x in w:
            warn(f"WARN {p}: {x}")
        reports.append(r)
    reports = latest_per_repo(reports)
    info["warnings"], WARNINGS = WARNINGS, None
    return reports, single, info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inputs", nargs="*", help="audit reports or folders")
    ap.add_argument("--manifest", help="project manifest (ai-audit/_project.json); implies --single-respondent")
    ap.add_argument("--single-respondent", action="store_true", help="one answers file was reused for every repo")
    ap.add_argument("--json", action="store_true", help="print the facts as JSON instead of Markdown")
    a = ap.parse_args()
    if not a.inputs and not a.manifest:
        ap.print_help()
        return 1
    reports, single, info = load(a.inputs, a.manifest, a.single_respondent)
    if not reports:
        for x in info["warnings"]:
            print(x)
        ap.print_help()
        return 1
    if a.json:
        print(json.dumps(facts(reports, single, info), ensure_ascii=False, indent=1))
        return 0
    if a.manifest:
        print(f"Project: {info['project']} · repos confirmed: {info['repos_confirmed']} · audited: {info['audited']}")
    for x in info["warnings"]:
        print(x)
    print_audits(reports)
    print_questionnaire(reports, single)
    return 0


if __name__ == "__main__":
    sys.exit(main())
