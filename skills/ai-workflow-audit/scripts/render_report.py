#!/usr/bin/env python3
"""Render the visual consolidated report (Step 5): an 11-page A4-landscape PDF.

Usage:
  python3 render_report.py --data <narrative.json> --manifest <project-root>/ai-audit/_project.json --out <report>.pdf
  python3 render_report.py --data <narrative.json> [--single-respondent] <report.md | folder> [...] --out <report>.pdf
  add --html-only <file.html> to write only the HTML (no browser needed)

The numbers (scores, averages, ranges, Critical/High counts, projected scores, questionnaire
aggregates) come from the audit reports through summarize_audits.py. The narrative JSON holds only
wording and judgment taken from the consolidated Markdown report, or with a single audit report from that report
(references/visual-report.md). One report counts as one respondent.
The JSON is validated first: the findings matrix must add up to each report's stated Critical and
High counts, every repo and action it names must exist, and it may hold no URL, email address or
ranking of people. All text is HTML-escaped; the page has no scripts, web fonts or external URLs.

The PDF is printed by a local headless Chrome, Chromium or Edge ($AI_AUDIT_CHROME overrides the
search). Never overwrites: an existing --out or fallback HTML is an error.
Exit codes: 0 PDF written · 1 usage or no reports · 2 invalid data or the output exists ·
3 no browser found (HTML written next to --out) · 4 the browser failed (HTML written next to --out) ·
5 too many repos for the fixed layout (nothing written).
Standard library only.
"""
import argparse
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summarize_audits as sa  # noqa: E402

PAGES = 11
LEVELS = ("Strong", "Partial", "Weak", "Absent (N/A)", "Not available", "Not visible")
VERDICTS = ("Aligned", "Overstated", "Understated", "Mixed", "Single source")
STATUS = ("yes", "no", "partial")
TONES = ("navy", "blue", "red", "orange", "green")
CLAIMS = {"X1": "Works from a shared instruction file, rules or skills",
          "X2": "Tests or CI run before merge",
          "X3": "A rule, hook or check was added after a mistake"}
BANNED = re.compile(r"champion|top performer|leaderboard", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}")
URL = re.compile(r"(?i)\b(?:https?|ftp|file)://|\bwww\.")

# Required narrative fields: path -> type. "[]" marks a list of objects checked with the sub-spec.
SPEC = {
    "project": str, "md_report": str, "audit_date": str, "prepared": str,
    "severity": {"critical": str, "high": str},
    "cover": {"headline": str, "subhead": str, "lede": str, "way_forward": str},
    "summary": {"title": str, "lede": str, "tiles": [{"label": str, "value": str, "note": str, "tone": str}],
                "strongest": {"title": str, "text": str}, "blind_spot": {"title": str, "text": str},
                "first_fix": {"title": str, "text": str}, "audit_says": str, "questionnaire_says": str},
    "comparison": {"title": str, "lede": str, "themes": [{"theme": str, "audit_level": str, "audit": str,
                                                         "q_level": str, "questionnaire": str, "verdict": str}]},
    "knowledge": {"title": str, "lede": str, "stat": {"value": str, "label": str},
                  "rows": [{"practice": str, "knows": str, "in_place": str, "evidence": str}],
                  "panel_title": str, "panel": [{"status": str, "title": str, "text": str}], "conclusion": str},
    "disagreements": {"title": str, "lede": str, "items": [{"topic": str, "questionnaire": str, "evidence": str,
                                                           "so_what": str, "action": int}]},
    "scorecard": {"title": str, "lede": str, "works": [str]},
    "findings": {"title": str, "rows": [{"severity": str, "finding": str, "repos": list, "action": int}]},
    "questionnaire": {"title": str, "lede": str},
    "actions": {"title": str, "lede": str, "groups": [{"name": str, "items": [{"n": int, "title": str, "involves": str,
                                                                            "effort": str}]}]},
    "roadmap": {"title": str, "steps": [{"label": str, "title": str, "text": str, "actions": list}],
                "decisions": [{"title": str, "text": str}]},
    "about": {"limits": [str]},
}
# Hard limits, measured by rendering a worst case at each limit with every text field at its maximum
# length (scripts/test_render.py repeats that check whenever a browser is available). Past them the
# fixed pages would clip content silently, so the data is rejected and the agent shortens or groups.
MAX_REPOS = 10
COUNTS = {"findings.rows": 16, "disagreements.items": 6, "actions (all groups)": 10, "actions.groups": 3,
          "knowledge.rows": 6, "knowledge.panel": 4, "roadmap.decisions": 6, "about.limits": 12, "scorecard.works": 3,
          "questionnaire.notes": 2, "about.sources": 1}
# Length limits (characters) per text field.
LIMITS = {"cover.headline": 70, "cover.subhead": 70, "cover.lede": 200, "cover.way_forward": 260,
          "summary.title": 80, "summary.lede": 420, "comparison.lede": 260, "comparison.themes.audit": 110,
          "comparison.themes.questionnaire": 110, "knowledge.rows.evidence": 110, "knowledge.rows.practice": 60,
          "disagreements.items.evidence": 260, "disagreements.items.questionnaire": 150,
          "disagreements.items.so_what": 60, "findings.rows.finding": 85, "actions.groups.items.involves": 190,
          "summary.strongest.text": 170, "summary.blind_spot.text": 170, "summary.first_fix.text": 170,
          "summary.audit_says": 150, "summary.questionnaire_says": 150, "roadmap.decisions.text": 90,
          "roadmap.decisions.title": 45, "roadmap.title": 90, "roadmap.steps.label": 25, "roadmap.steps.title": 35,
          "roadmap.steps.text": 90, "summary.strongest.title": 30, "summary.blind_spot.title": 30, "summary.first_fix.title": 30,
          "summary.tiles.label": 30, "summary.tiles.value": 12, "summary.tiles.suffix": 6, "summary.tiles.note": 45,
          "comparison.title": 90, "comparison.themes.verdict_note": 25, "knowledge.title": 90, "knowledge.lede": 200,
          "knowledge.stat.value": 6, "knowledge.stat.label": 90, "knowledge.rows.knows_note": 12,
          "knowledge.panel_title": 60, "knowledge.panel_subtitle": 90, "knowledge.panel.title": 40, "knowledge.panel.text": 120,
          "knowledge.conclusion": 160, "disagreements.title": 90, "disagreements.lede": 160, "disagreements.items.topic": 30,
          "scorecard.title": 90, "scorecard.lede": 200, "scorecard.works": 90, "findings.title": 90, "findings.note": 160,
          "questionnaire.title": 90, "questionnaire.lede": 260, "questionnaire.notes": 160, "actions.title": 90,
          "actions.lede": 160, "actions.groups.name": 30, "actions.groups.items.title": 32, "actions.groups.items.effort": 12,
          "actions.groups.items.themes": 40, "about.limits": 150, "about.sources": 150, "project": 30, "severity.critical": 120,
          "severity.high": 120}


class TooLarge(Exception):
    pass


class Invalid(Exception):
    pass


# ---------------------------------------------------------------- validation

def check_spec(data, spec, path, errs):
    for key, want in spec.items():
        p = f"{path}.{key}" if path else key
        if key not in data:
            errs.append(f"missing {p}")
            continue
        v = data[key]
        if isinstance(want, dict):
            if not isinstance(v, dict):
                errs.append(f"{p} must be an object")
            else:
                check_spec(v, want, p, errs)
        elif isinstance(want, list):
            if not isinstance(v, list) or not v:
                errs.append(f"{p} must be a non-empty list")
                continue
            for i, item in enumerate(v):
                if isinstance(want[0], dict):
                    if not isinstance(item, dict):
                        errs.append(f"{p}[{i}] must be an object")
                    else:
                        check_spec(item, want[0], f"{p}[{i}]", errs)
                elif not isinstance(item, want[0]):
                    errs.append(f"{p}[{i}] must be a {want[0].__name__}")
        elif want is int:
            if not isinstance(v, int) or isinstance(v, bool):
                errs.append(f"{p} must be a whole number")
        elif not isinstance(v, want):
            errs.append(f"{p} must be a {want.__name__}")


def strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v, path)


def finding_counts(rows, repos):
    """{repo: {"critical": n, "high": n}} from the findings matrix rows."""
    out = {r: {"critical": 0, "high": 0} for r in repos}
    for row in rows:
        sev = row["severity"].lower()
        for cell in row["repos"]:
            name, n = (cell, 1) if isinstance(cell, str) else (cell.get("repo"), cell.get("count", 1))
            if name in out and sev in ("critical", "high"):
                out[name][sev] += n
    return out


def validate(d, facts):
    errs, warns = [], []
    if len(facts["repos"]) > MAX_REPOS:
        raise TooLarge(f"{len(facts['repos'])} repos; the fixed 11-page layout fits at most {MAX_REPOS}")
    check_spec(d, SPEC, "", errs)
    if errs:
        raise Invalid("; ".join(errs))
    for path, s in strings(d):
        if EMAIL.search(s):
            errs.append(f"{path}: contains an email address")
        if URL.search(s):
            errs.append(f"{path}: contains a URL (the page loads and links nothing)")
        if BANNED.search(s):
            errs.append(f"{path}: the report must not rank or recommend people")
        lim = LIMITS.get(path)
        if lim and len(s) > lim:
            errs.append(f"{path}: {len(s)} characters, limit {lim} (it would not fit the page): shorten it")
    sizes = {"findings.rows": len(d["findings"]["rows"]), "disagreements.items": len(d["disagreements"]["items"]),
             "actions (all groups)": sum(len(g["items"]) for g in d["actions"]["groups"]),
             "actions.groups": len(d["actions"]["groups"]), "knowledge.rows": len(d["knowledge"]["rows"]),
             "knowledge.panel": len(d["knowledge"]["panel"]), "roadmap.decisions": len(d["roadmap"]["decisions"]),
             "about.limits": len(d["about"]["limits"]), "scorecard.works": len(d["scorecard"]["works"]),
             "questionnaire.notes": len(d["questionnaire"].get("notes", [])), "about.sources": len(d["about"].get("sources", []))}
    for k, n in sizes.items():
        if n > COUNTS[k]:
            errs.append(f"{k}: {n} entries, at most {COUNTS[k]} fit the page: group or merge them "
                        "(the Markdown report keeps every detail)")
    repos = [r["repo"] for r in facts["repos"]]
    actions = [it["n"] for g in d["actions"]["groups"] for it in g["items"]]
    if len(set(actions)) != len(actions):
        errs.append("actions: numbers must be unique")
    themes = [t["theme"] for t in facts["themes"]]
    got = [t["theme"] for t in d["comparison"]["themes"]]
    if got != themes:
        errs.append(f"comparison.themes must be exactly, in order: {themes}")
    for t in d["comparison"]["themes"]:
        for k in ("audit_level", "q_level"):
            if t[k] not in LEVELS:
                errs.append(f"comparison '{t['theme']}' {k} must be one of {LEVELS}")
        if t["verdict"] not in VERDICTS:
            errs.append(f"comparison '{t['theme']}' verdict must be one of {VERDICTS}")
    for r in d["knowledge"]["rows"]:
        if r["knows"] not in STATUS or r["in_place"] not in STATUS:
            errs.append(f"knowledge row '{r['practice']}': knows and in_place must be one of {STATUS}")
    for r in d["knowledge"]["panel"]:
        if r["status"] not in STATUS:
            errs.append(f"knowledge panel '{r['title']}': status must be one of {STATUS}")
    for t in d["summary"]["tiles"]:
        if t["tone"] not in TONES:
            errs.append(f"summary tile '{t['label']}': tone must be one of {TONES}")
    if len(d["summary"]["tiles"]) != 2:
        errs.append("summary.tiles must hold exactly 2 tiles (the first 3 are computed)")
    if len(d["roadmap"]["steps"]) != 3:
        errs.append("roadmap.steps must hold exactly 3 steps")
    refs = [("disagreements", i["action"]) for i in d["disagreements"]["items"]]
    refs += [("findings", r["action"]) for r in d["findings"]["rows"]]
    refs += [("roadmap", a) for s in d["roadmap"]["steps"] for a in s["actions"]]
    for where, a in refs:
        if a not in actions:
            errs.append(f"{where}: action {a} does not exist")
    for row in d["findings"]["rows"]:
        if row["severity"] not in ("Critical", "High"):
            errs.append(f"findings row '{row['finding']}': severity must be Critical or High")
        for cell in row["repos"]:
            name = cell if isinstance(cell, str) else cell.get("repo") if isinstance(cell, dict) else None
            if name not in repos:
                errs.append(f"findings row '{row['finding']}': unknown repo {cell!r} (repos: {repos})")
    if not errs:
        counts = finding_counts(d["findings"]["rows"], repos)
        for r in facts["repos"]:
            c = counts[r["repo"]]
            if (c["critical"], c["high"]) != (r["critical"], r["high"]):
                errs.append(f"findings matrix for {r['repo']}: {c['critical']} critical / {c['high']} high, "
                            f"but its report states {r['critical']} / {r['high']}")
    if errs:
        raise Invalid("; ".join(errs))
    return warns


# ---------------------------------------------------------------- helpers

def t(s):
    """Escape, then allow `code` and **bold** only."""
    s = html.escape(str(s), quote=True)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def n2(v):
    return "–" if v is None else f"{v:.2f}"


def band(v):
    if v is None:
        return ""
    return "Ad hoc" if v < 2 else "Emerging" if v < 2.75 else "Defined" if v < 3.5 else "Managed" if v < 4.25 else "Optimized"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def level_chip(level, score=None):
    cls = {"Strong": "strong", "Partial": "partial", "Weak": "weak"}.get(level, "na")
    sc = f' <span class="lvs">{n2(score)}</span>' if score is not None else ""
    return f'<span class="lv lv-{cls}"><i></i>{t(level)}{sc}</span>'


def verdict_chip(v):
    cls = {"Aligned": "al", "Overstated": "ov", "Understated": "un", "Mixed": "mx"}.get(v, "ss")
    return f'<span class="vd vd-{cls}"><i></i>{t(v)}</span>'


def icon(status):
    if status == "yes":
        return '<svg class="ic" viewBox="0 0 20 20"><circle cx="10" cy="10" r="10" fill="#1f9d3a"/><path d="M5.5 10.5l3 3 6-6.5" stroke="#fff" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    if status == "no":
        return '<svg class="ic" viewBox="0 0 20 20"><circle cx="10" cy="10" r="10" fill="#d33a3a"/><path d="M6.5 6.5l7 7M13.5 6.5l-7 7" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></svg>'
    return '<svg class="ic" viewBox="0 0 20 20"><path d="M10 1.5L19 18H1z" fill="#ee8456"/><path d="M10 7.5v5" stroke="#fff" stroke-width="2" stroke-linecap="round"/><circle cx="10" cy="15" r="1.2" fill="#fff"/></svg>'


def num_badge(n, light=False):
    return f'<span class="nb{" nb-l" if light else ""}">{int(n)}</span>'


def effort_chip(e):
    tone = "g" if e.strip().lower() == "quick" else "o" if "longer" in e.lower() else "b"
    return f'<span class="ef ef-{tone}"><i></i>{t(e)}</span>'


def wrap_repo(name):
    return t(name).replace("-", "-<wbr>").replace("_", "_<wbr>")


# ---------------------------------------------------------------- pages

class Doc:
    def __init__(self, d, f):
        self.d, self.f = d, f
        self.q = f["questionnaire"]
        self.respondents = self.q.get("respondents", 0)
        self.nrepos = len(f["repos"])
        self.level_of = {x["theme"]: x["audit_level"] for x in d["comparison"]["themes"]}
        self.one = self.nrepos == 1
        self.across = f["repos"][0]["repo"] if self.one else f"avg of {plural(self.nrepos, 'repo')}"

    def page(self, n, eyebrow, title, lede, body, cls=""):
        foot = (f'<footer><span>{t(self.d["project"])} · AI Adoption Audit · Management report</span>'
                f'<span>Audit date {t(self.d["audit_date"])} · {plural(self.nrepos, "repo")} · '
                f'{plural(self.respondents, "questionnaire respondent")}</span><span>{n} / {PAGES}</span></footer>')
        head = f'<div class="eb">{t(eyebrow)}</div><h2>{t(title)}</h2>' + (f'<p class="lede">{t(lede)}</p>' if lede else "")
        return f'<section class="page {cls}">{head}{body}{foot}</section>'

    # 1
    def cover(self):
        d, f, c = self.d, self.f, self.d["cover"]
        x = lambda v: 30 + (min(max(v, 1), 5) - 1) / 4 * 940
        ticks = "".join(f'<line x1="{x(i)}" y1="62" x2="{x(i)}" y2="74" stroke="#5b6b86"/>'
                        f'<text x="{x(i)}" y="92" class="tk">{i}</text>' for i in range(1, 6))
        today, proj = f["average"], f["projected_average"]
        svg = f'<line x1="{x(1)}" y1="68" x2="{x(5)}" y2="68" stroke="#3b4d6b" stroke-width="1.5"/>{ticks}'
        if today is not None:
            if proj is not None:
                svg += f'<line x1="{x(today)}" y1="68" x2="{x(proj)}" y2="68" stroke="#8ab4f0" stroke-width="3"/>'
            close = proj is not None and abs(x(proj) - x(today)) < 360
            if proj is not None:
                px, pa = (x(proj) - 6, "start") if close and proj >= today else (x(proj) + 6, "end") if close else (x(proj), "middle")
                svg += (f'<circle cx="{x(proj)}" cy="68" r="8" fill="#8ab4f0"/>'
                        f'<text x="{px:.1f}" y="42" class="lp" text-anchor="{pa}">Projected {n2(proj)} · if all audit changes are done</text>')
            tx, ta = (x(today) + 6, "end") if close and proj >= today else (x(today) - 6, "start") if close else (x(today), "middle")
            svg += (f'<circle cx="{x(today)}" cy="68" r="8" fill="#fff" stroke="#0f2242" stroke-width="2"/>'
                    f'<text x="{tx:.1f}" y="42" class="lt" text-anchor="{ta}">Today {n2(today)} · {self.across}</text>')
        kpis = [(self.nrepos, "Repo audited" if self.one else "Repos audited"), (self.respondents, "Questionnaire respondent" + ("" if self.respondents == 1 else "s")),
                (f["critical"], "Critical findings"), (f["high"], "High findings")]
        kp = "".join(f'<div class="ck"><b>{v}</b><span>{t(lbl)}</span></div>' for v, lbl in kpis)
        return (f'<section class="page cover"><div class="eb">AI adoption audit · management report</div>'
                f'<h1>{t(d["project"])}</h1><div class="hl">{t(c["headline"])}</div><div class="hl2">{t(c["subhead"])}</div>'
                f'<p class="clede">{t(c["lede"])}</p>'
                f'<div class="scale"><div class="sl">{"AI maturity score" if self.one else "Average AI maturity score across " + plural(self.nrepos, "repo")} · scale 1–5</div>'
                f'<svg viewBox="0 0 1000 100" class="ssvg">{svg}</svg></div>'
                f'<p class="wf"><b>The way forward:</b> {t(c["way_forward"])}</p>'
                f'<div class="cbar">{kp}<div class="cd">Audit date {t(d["audit_date"])}<br>Report prepared {t(d["prepared"])}</div></div></section>')

    # 2
    def summary(self):
        d, f, s = self.d, self.f, self.d["summary"]
        bands = " · ".join(f"{v} {k}" for k, v in f["bands"].items())
        rng = f"Range {n2(f['range'][0])}–{n2(f['range'][1])}" if f["range"] else ""
        prng = f"Range {n2(f['projected_range'][0])}–{n2(f['projected_range'][1])} if all audit changes are done" if f["projected_range"] else "No projection in the reports"
        if self.one:
            r0 = f["repos"][0]
            rng, bands = "", r0.get("maturity") or ""
            prng = (f"{r0['projected_band']} if all audit changes are done" if r0.get("projected_band")
                    else "If all audit changes are done" if r0.get("projected") is not None else "No projection in the report")
        tiles = [("AI maturity score" if self.one else "Average AI maturity score", n2(f["average"]), "/ 5",
                  " · ".join(x for x in (rng, bands) if x), "navy"),
                 ("Projected", n2(f["projected_average"]), "/ 5", prng, "blue"),
                 ("Critical findings", str(f["critical"]), "", f"Plus {f['high']} high" + ("" if self.one else f" · across {plural(self.nrepos, 'repo')}"), "red")]
        tiles += [(x["label"], x["value"], x.get("suffix", ""), x["note"], x["tone"]) for x in s["tiles"]]
        th = "".join(f'<div class="tile tn-{tone}"><div class="tl">{t(lbl)}</div><div class="tv">{t(v)}'
                     f'{f"<small>{t(suf)}</small>" if suf else ""}</div><div class="tnote">{t(note)}</div></div>'
                     for lbl, v, suf, note, tone in tiles)
        star = '<svg class="ic" viewBox="0 0 20 20"><circle cx="10" cy="10" r="10" fill="#1f9d3a"/><path d="M10 4.5l1.7 3.5 3.8.5-2.8 2.6.7 3.8L10 13.1 6.6 14.9l.7-3.8-2.8-2.6 3.8-.5z" fill="#fff"/></svg>'
        cards = [("g", star, "Strongest area", s["strongest"]), ("o", icon("partial"), "Biggest blind spot", s["blind_spot"]),
                 ("r", icon("no"), "First thing to fix", s["first_fix"])]
        ch = "".join(f'<div class="card cd-{k}"><div class="ck2">{ic}<span>{t(lbl)}</span></div><h3>{t(c["title"])}</h3>'
                     f'<p>{t(c["text"])}</p></div>' for k, ic, lbl, c in cards)
        src = (f'<div class="srcs"><div class="sh">What each source says</div>'
               f'<div class="sr"><div><b>AI audit</b><small>{plural(self.nrepos, "repo")}</small></div><p>{t(s["audit_says"])}</p></div>'
               f'<div class="sr"><div><b>Questionnaire</b><small>{plural(self.respondents, "respondent")}</small></div><p>{t(s["questionnaire_says"])}</p></div></div>')
        return self.page(2, "Executive summary", s["title"], s["lede"], f'<div class="tiles">{th}</div><div class="cards">{ch}</div>{src}')

    # 3
    def comparison(self):
        c, f = self.d["comparison"], self.f
        avg = {x["theme"]: x["avg"] for x in f["themes"]}
        counts = {}
        for x in c["themes"]:
            counts[x["verdict"]] = counts.get(x["verdict"], 0) + 1
        chips = "".join(f'<span class="cc"><b>{n}</b>{verdict_chip(v)}</span>' for v, n in counts.items())
        legend = ('<span class="lg">Levels: ' + level_chip("Strong") + level_chip("Partial") + level_chip("Weak")
                  + ' · audit scores out of 5</span>')
        note = lambda x: f'<small>{t(x["verdict_note"])}</small>' if x.get("verdict_note") else ""
        rows = "".join(
            f'<tr><td class="th">{t(x["theme"])}</td>'
            f'<td>{level_chip(x["audit_level"], avg.get(x["theme"]))}<p>{t(x["audit"])}</p></td>'
            f'<td>{level_chip(x["q_level"])}<p>{t(x["questionnaire"])}</p></td>'
            f'<td>{verdict_chip(x["verdict"])}{note(x)}</td></tr>'
            for x in c["themes"])
        body = (f'<div class="chips">{chips}{legend}</div><table class="cmp"><thead><tr><th>Theme</th><th>AI audit · repo evidence</th>'
                f'<th>Questionnaire · knowledge and claims</th><th>Verdict</th></tr></thead><tbody>{rows}</tbody></table>')
        return self.page(3, "Two-source comparison", c["title"], c["lede"], body)

    # 4
    def knowledge(self):
        k, q = self.d["knowledge"], self.q
        label = {"yes": "In place.", "no": "Not in place.", "partial": "Partly in place."}
        rows = "".join(
            f'<tr><td class="th">{t(r["practice"])}</td><td class="kn">{icon(r["knows"])}<b>{t(r.get("knows_note", ""))}</b></td>'
            f'<td><div class="ev">{icon(r["in_place"])}<p><b>{label[r["in_place"]]}</b> {t(r["evidence"])}</p></div></td></tr>'
            for r in k["rows"])
        left = (f'<div class="kstat"><b>{t(k["stat"]["value"])}</b><span>{t(k["stat"]["label"])}</span></div>'
                f'<table class="kt"><thead><tr><th>Practice (scenario)</th><th>Respondent knows</th><th>Repo evidence</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')
        panel = "".join(f'<div class="pr">{icon(r["status"])}<div><b>{t(r["title"])}</b><p>{t(r["text"])}</p></div></div>'
                        for r in k["panel"])
        els = ""
        if q.get("element_names"):
            miss = q.get("elements_missing", {})
            els = ('<div class="els"><span class="elh">Prompt exercise:</span>' + "".join(
                f'<span class="el {"el-m" if e in miss else "el-p"}"><i></i>{e} {t(nm)}</span>'
                for e, nm in q["element_names"].items()) + "</div>")
        right = (f'<h3 class="ph">{t(k["panel_title"])}</h3>'
                 + (f'<div class="psub">{t(k["panel_subtitle"])}</div>' if k.get("panel_subtitle") else "")
                 + f'{panel}{els}<div class="concl">{t(k["conclusion"])}</div>')
        return self.page(4, "Knowledge vs practice", k["title"], k["lede"], f'<div class="two"><div>{left}</div><div>{right}</div></div>')

    # 5
    def disagreements(self):
        g = self.d["disagreements"]
        rows = "".join(
            f'<tr><td>{num_badge(i + 1)}</td><td class="th">{t(x["topic"])}</td><td><p class="dq"><i></i>{t(x["questionnaire"])}</p></td>'
            f'<td><p class="de"><i></i>{t(x["evidence"])}</p></td><td><div class="sw"><b>{t(x["so_what"])}</b>'
            f'<span>Action {num_badge(x["action"])}</span></div></td></tr>' for i, x in enumerate(g["items"]))
        body = (f'<table class="dis"><thead><tr><th></th><th>Topic</th><th>The questionnaire says</th><th>The evidence shows</th>'
                f'<th>So what</th></tr></thead><tbody>{rows}</tbody></table>')
        return self.page(5, "Where the sources disagree", g["title"], g["lede"], body)

    # 6
    def scorecard(self):
        s, f = self.d["scorecard"], self.f
        pavg = {p["name"]: p["avg"] for p in f["params"]}
        short = {"Instructions & Memory": "Instructions", "Context & Cost": "Context & Cost", "Knowledge Base & Docs": "Docs",
                 "Skills & Commands": "Skills", "MCP Servers & Plugins": "MCP", "Guardrails & Hooks": "Guardrails",
                 "Permissions & Secrets": "Permissions", "Verification & Testing": "Verification",
                 "Git & Review Workflow": "Git & Review", "Governance & Data Compliance": "Governance",
                 "Observability & Feedback": "Observability"}
        themes = sorted((x for x in f["themes"] if x["params"]), key=lambda x: -(x["avg"] or 0))
        bars = ""
        for x in themes:
            lv = self.level_of.get(x["theme"], "Not available")
            cls = {"Strong": "strong", "Partial": "partial", "Weak": "weak"}.get(lv, "na")
            sub = " · ".join(f"{short[p]} {n2(pavg[p]) if pavg[p] is not None else 'N/A'}" for p in x["params"])
            w = ((x["avg"] or 0) / 5) * 100
            bars += (f'<div class="br"><div class="bl">{t(x["theme"])}</div><div class="bt"><div class="bf bf-{cls}" style="width:{w:.1f}%"></div>'
                     f'<span class="bv" style="left:{w:.1f}%">{n2(x["avg"])} <small>{t(lv)}</small></span><div class="bs">{t(sub)}</div></div></div>')
        grid = "".join(f'<span style="left:{i * 20}%">{i}</span>' for i in range(6))
        left = (f'<h3 class="ch">Audit score by theme</h3><div class="csub">Out of 5; {"score per theme" if self.one else "average per theme across " + plural(self.nrepos, "repo")},'
                f' coloured by the level the report assigns</div><div class="lgd">{level_chip("Strong")}{level_chip("Partial")}{level_chip("Weak")}</div>'
                f'<div class="bars"><div class="grid">{grid}</div>{bars}</div>')
        X = lambda v: (min(max(v, 1), 5) - 1) / 4 * 100
        rows = ""
        for r in sorted(f["repos"], key=lambda r: (r["score"] is None, r["score"] or 0)):
            dots = ""
            if r["score"] is not None:
                if r["projected"] is not None:
                    a, b = sorted((X(r["score"]), X(r["projected"])))
                    dots += (f'<i class="seg" style="left:{a:.1f}%;width:{b - a:.1f}%"></i>'
                             f'<i class="dp" style="left:{X(r["projected"]):.1f}%"></i><em class="vp" style="left:{X(r["projected"]):.1f}%">{n2(r["projected"])}</em>')
                dots += f'<i class="dt" style="left:{X(r["score"]):.1f}%"></i><em class="vt" style="left:{X(r["score"]):.1f}%">{n2(r["score"])}</em>'
            arrow = (f'{t(r["maturity"])} → {t(r.get("projected_band") or band(r["projected"]))}'
                     if r["projected"] is not None else t(r["maturity"]))
            rows += (f'<tr><td><b>{t(r["repo"])}</b><small>{arrow}</small></td><td class="trk"><div>{dots}</div></td>'
                     f'<td><span class="cb cb-c">{r["critical"]}</span></td><td><span class="cb cb-h">{r["high"]}</span></td></tr>')
        pa, pp = f["average"], f["projected_average"]
        pd = ""
        if pa is not None:
            if pp is not None:
                a, b = sorted((X(pa), X(pp)))
                pd += (f'<i class="seg" style="left:{a:.1f}%;width:{b - a:.1f}%"></i><i class="dp big" style="left:{X(pp):.1f}%"></i>'
                       f'<em class="vp" style="left:{X(pp):.1f}%">{n2(pp)}</em>')
            pd += f'<i class="dt big" style="left:{X(pa):.1f}%"></i><em class="vt" style="left:{X(pa):.1f}%">{n2(pa)}</em>'
        bands = ", ".join(f"{v} {k}" for k, v in f["bands"].items())
        axis = "".join(f'<span style="left:{X(i):.1f}%">{i}</span>' for i in range(1, 6))
        right = (f'<h3 class="ch">{"Score today and projected" if self.one else "Score by repository"}</h3><div class="csub">Out of 5 · dark dot today, light dot projected if all audit changes are done</div>'
                 f'<table class="rt"><thead><tr><th>Repo</th><th class="trk"><div class="ax">{axis}</div></th><th>Crit.</th><th>High</th></tr></thead>'
                 f'<tbody>{rows}' + ("" if self.one else f'<tr class="tot"><td><b>Project average</b><small>{t(bands)}</small></td><td class="trk"><div>{pd}</div></td>'
                 f'<td><b>{f["critical"]}</b></td><td><b>{f["high"]}</b></td></tr>') + '</tbody></table>')
        rec = [p for p in f["params"] if p["name"] in f["recurring"]]
        box = f'<div class="box"><div class="bh">{"Weakest areas" if self.one else "Recurring gaps"} and what already works</div>'
        if rec:
            box += (f'<div class="bi">{icon("no")}<p>{"Scored ≤ 2" if self.one else "≤ 2 in at least half the repos"}: ' + " · ".join(
                f'{t(p["name"])} <b>{n2(p["avg"])}</b>' for p in rec) + "</p></div>")
        else:
            box += f'<div class="bi">{icon("yes")}<p>{"No parameter scores ≤ 2." if self.one else "No parameter scores ≤ 2 in half the repos or more."}</p></div>'
        box += "".join(f'<div class="bi">{icon("yes")}<p>{t(w)}</p></div>' for w in s["works"]) + "</div>"
        return self.page(6, "Repository scorecard", s["title"], s["lede"],
                         f'<div class="two sc"><div>{left}</div><div>{right}{box}</div></div>', cls="dense" if self.nrepos > 7 else "")

    # 7
    def findings(self):
        g, f, sev = self.d["findings"], self.f, self.d["severity"]
        repos = [r["repo"] for r in f["repos"]]
        head = "".join(f"<th class='rc'>{wrap_repo(r)}</th>" for r in repos)
        body = ""
        for level, cls in (("Critical", "c"), ("High", "h")):
            rows = [r for r in g["rows"] if r["severity"] == level]
            if not rows:
                continue
            label = "Critical · fix now" if level == "Critical" else "High · fix soon"
            body += f'<tr class="grp"><td colspan="{len(repos) + 2}"><span class="sv sv-{cls}"><i></i>{label}</span></td></tr>'
            for row in rows:
                cnt = {}
                for cell in row["repos"]:
                    name, n = (cell, 1) if isinstance(cell, str) else (cell["repo"], cell.get("count", 1))
                    cnt[name] = cnt.get(name, 0) + n
                cells = "".join(f'<td class="rc"><span class="sq {"sq-" + cls if r in cnt else ""}">'
                                f'{cnt[r] if cnt.get(r, 0) > 1 else ""}</span></td>' for r in repos)
                body += f'<tr><td class="fl">{t(row["finding"])}</td>{cells}<td class="rc">{num_badge(row["action"])}</td></tr>'
        tot = "".join(f'<td class="rc"><b>{r["critical"]}</b> / <b>{r["high"]}</b></td>' for r in f["repos"])
        body += f'<tr class="tot"><td><b>Total per repo · critical / high</b></td>{tot}<td class="rc"><b>{f["critical"]} / {f["high"]}</b></td></tr>'
        lede = f'Critical: {sev["critical"]} (fix now). High: {sev["high"]} (fix soon).'
        note = (f'<p class="note">{icon("yes")}<span>Each square is one audit finding; the rows add up to the {"audit&#39;s" if self.one else "audits&#39;"} stated totals '
                f'({f["critical"]} critical, {f["high"]} high).' + (f' {t(g["note"])}' if g.get("note") else "") + "</span></p>")
        return self.page(7, "Security findings", g["title"], lede,
                         f'<table class="mx"><thead><tr><th>Finding</th>{head}<th class="rc">Fixed by action</th></tr></thead>'
                         f'<tbody>{body}</tbody></table>{note}', cls="p-mx" if len(repos) > 8 else "dense" if len(g["rows"]) > 13 else "")

    # 8
    def questionnaire(self):
        g, q = self.d["questionnaire"], self.q
        if not q.get("respondents"):
            title, lede = "No questionnaire results", "None of the audit reports holds questionnaire results."
            body = ('<div class="box"><div class="bi">' + icon("partial") + '<p>No report has questionnaire results, so the '
                    'Questionnaire column of the comparison is "Not available" and every verdict is "Single source".</p></div></div>')
            return self.page(8, "Questionnaire results", title, lede, body)
        single = q["single"]
        if q["score_min"] is not None:
            score = (f"{q['score_min']:g}–{q['score_max']:g}" if q["score_min"] != q["score_max"] else f"{q['score_min']:g}")
            if not single and q["score_avg"] is not None:
                score = f"{q['score_avg']:.0f}"
        else:
            score = "–"
        levels = ", ".join(f"{k} ×{v}" if not single else k for k, v in q["levels"].items()) or "–"
        missed = q.get("scenarios_missed", {})
        right_n = 6 - len(missed) if single else None
        el = q.get("elements")
        kt = [(score, "/ 100", "Practice Score" + (" range across repos" if single and q["score_min"] != q["score_max"] else "" if single else " average"),
               ("only 'matches the audit' differs between repos" if single else f"range {q['score_min']:g}–{q['score_max']:g}") if q["score_min"] is not None else ""),
              (levels, "", "Level" + ("" if single else "s"), "self-administered; not an employee evaluation"),
              (f"{right_n}/6" if single else str(sum(missed.values())), "", "Scenarios right" if single else "Scenario misses (all respondents)", ""),
              ((f"{el:g}" if el is not None else "–"), "/ 5", "Prompt exercise elements", "")]
        tiles = "".join(f'<div class="qk"><b>{t(v)}<small>{t(s)}</small></b><span>{t(lbl)}</span><em>{t(n)}</em></div>' for v, s, lbl, n in kt)
        names = {"written": "Written answers", "prompt": "Prompt exercise", "scenarios": "Scenarios", "workmode": "Work mode"}
        parts = ""
        for k, mx in q["parts_max"].items():
            v = q["parts"].get(k)
            w = 0 if v is None else v / mx * 100
            parts += (f'<div class="pb"><span>{names[k]}</span><div class="pt"><div style="width:{w:.0f}%"></div></div>'
                      f'<b>{"–" if v is None else f"{v:g}"} / {mx}</b></div>')
        prof = []
        for key, lbl in (("roles", "Role"), ("experience", "Experience"), ("work_mode", "Work mode")):
            if q.get(key):
                prof.append(f"<b>{lbl}:</b> " + ", ".join(t(k) if single else f"{t(k)} ×{v}" for k, v in q[key].items()))
        left = (f'<div class="qks">{tiles}</div><h3 class="ch">Score parts{" (average)" if not single else ""}</h3>{parts}'
                f'<p class="prof">{" · ".join(prof)}</p>')
        sc = ""
        for k, topic in q["scenario_topics"].items():
            c = missed.get(k, 0)
            st = ("yes" if not c else "no") if single else ("yes" if not c else "partial")
            res = ("Right" if not c else "Missed") if single else (f"{c} of {self.respondents} missed" if c else "All right")
            sc += f'<tr><td>Q{k}</td><td>{t(topic)}</td><td class="mut">{t(q["scenario_params"][k])}</td><td class="kn">{icon(st)}<b>{res}</b></td></tr>'
        gr = ""
        for k, lbl in (("9", "a concrete win"), ("10", "how the team works"), ("11", "after a mistake")):
            v = q["grades"].get(k)
            dots = "".join(f'<i class="{"on" if v is not None and i < round(v) else ""}"></i>' for i in range(3))
            gr += f'<div class="gr"><span>Q{k} {lbl}</span><span class="dots">{dots}</span><b>{"n/a" if v is None else f"{v:g}"} / 3</b></div>'
        cl = ""
        for row, lbl in CLAIMS.items():
            c = q["claims"][row]
            where = (", ".join(c.get("contradicted_in", [])) or "—") if single else ""
            cl += (f'<tr><td><b>{row}</b> {t(lbl)}</td><td>{c["consistent"]}</td><td class="{"bad" if c["contradicted"] else ""}">{c["contradicted"]}</td>'
                   f'<td>{c["not checkable"]}</td><td>{c["no claim"]}</td>' + (f'<td class="mut">{t(where)}</td>' if single else "") + "</tr>")
        flags = "; ".join(f"{t(k)} ×{v}" for k, v in q["flags"].items()) or "none"
        right = (f'<h3 class="ch">Scenarios</h3><table class="qt"><tbody>{sc}</tbody></table>'
                 f'<h3 class="ch">Written answers (graded 0–3)</h3>{gr}'
                 f'<h3 class="ch">Says vs found (claims checked against each repo\'s audit)</h3>'
                 f'<table class="qt claims"><thead><tr><th></th><th>Consistent</th><th>Contradicted</th><th>Not checkable</th><th>No claim</th>'
                 + ("<th>Contradicted in</th>" if single else "") + f'</tr></thead><tbody>{cl}</tbody></table>'
                 f'<p class="prof"><b>Flags (per report):</b> {flags}</p>')
        notes = "".join(f'<div class="bi">{icon("partial")}<p>{t(n)}</p></div>' for n in g.get("notes", []))
        body = f'<div class="two qq"><div>{left}{f"<div class=box>{notes}</div>" if notes else ""}</div><div>{right}</div></div>'
        return self.page(8, "Questionnaire results", g["title"], g["lede"], body)

    # 9
    def actions(self):
        a, rows_f = self.d["actions"], self.d["findings"]["rows"]
        body = ""
        for grp in a["groups"]:
            body += f'<tr class="grp"><td colspan="5">{t(grp["name"])}</td></tr>'
            for it in grp["items"]:
                c = sum(1 for r in rows_f if r["action"] == it["n"] and r["severity"] == "Critical")
                h = sum(1 for r in rows_f if r["action"] == it["n"] and r["severity"] == "High")
                fx = (f'<span class="sv sv-c"><i></i>{c} Critical</span>' if c else "") + (f'<span class="sv sv-h"><i></i>{h} High</span>' if h else "")
                fx += "".join(f'<small>{t(x)}</small>' for x in it.get("themes", []))
                body += (f'<tr><td>{num_badge(it["n"])}</td><td class="th">{t(it["title"])}</td><td class="mut">{t(it["involves"])}</td>'
                         f'<td class="fx">{fx}</td><td>{effort_chip(it["effort"])}</td></tr>')
        return self.page(9, "Recommended actions", a["title"], a["lede"],
                         f'<table class="act"><thead><tr><th>#</th><th>Action</th><th>What it involves</th><th>What it fixes</th>'
                         f'<th>Effort</th></tr></thead><tbody>{body}</tbody></table>'
                         f'<p class="note">Chips count finding types (rows on the security page) that the action closes.</p>')

    # 10
    def roadmap(self):
        r, f, rows = self.d["roadmap"], self.f, self.d["findings"]["rows"]
        steps = ""
        for i, s in enumerate(r["steps"]):
            steps += (f'<div class="st st-{i}"><div class="stl">{t(s["label"])}</div><h3>{t(s["title"])}</h3><p>{t(s["text"])}</p>'
                      f'<div>{"".join(num_badge(x) for x in s["actions"])}</div></div>' + ('<div class="arr">→</div>' if i < 2 else ""))
        order = [x for s in r["steps"] for x in s["actions"]]
        open_ = lambda done: (sum(1 for x in rows if x["severity"] == "Critical" and x["action"] not in done),
                              sum(1 for x in rows if x["severity"] == "High" and x["action"] not in done))
        bars, done = [("Today", open_(set()))], set()
        for x in order:
            before = open_(done)
            done.add(x)
            after = open_(done)
            if after != before:
                bars.append((f"After {x}", after))
        top = max(1, max(c + h for _, (c, h) in bars))
        step = 5 if top <= 25 else 10
        ymax = -(-top // step) * step
        W, H, L, B = 560, 210, 34, 180
        bw = min(56, (W - L - 10) / len(bars) * 0.6)
        gap = (W - L - 10) / len(bars)
        sy = lambda v: B - v / ymax * (B - 20)
        svg = "".join(f'<line x1="{L}" x2="{W}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="#e6e6e6"/><text x="{L - 8}" y="{sy(v) + 4:.1f}" class="ya">{v}</text>'
                      for v in range(0, ymax + 1, step))
        for i, (lbl, (c, h)) in enumerate(bars):
            x = L + 10 + i * gap + (gap - bw) / 2
            if c:
                svg += f'<rect x="{x:.1f}" y="{sy(c):.1f}" width="{bw:.1f}" height="{B - sy(c):.1f}" fill="#d33a3a"/>'
            if h:
                svg += f'<rect x="{x:.1f}" y="{sy(c + h):.1f}" width="{bw:.1f}" height="{sy(c) - sy(c + h):.1f}" fill="#ee8456"/>'
            if c and h:
                svg += f'<line x1="{x:.1f}" x2="{x + bw:.1f}" y1="{sy(c):.1f}" y2="{sy(c):.1f}" stroke="#fff" stroke-width="1.5"/>'
            svg += (f'<text x="{x + bw / 2:.1f}" y="{sy(c + h) - 7:.1f}" class="bvl">{c} / {h}</text>'
                    f'<text x="{x + bw / 2:.1f}" y="{B + 17}" class="bxl{" b" if i == 0 else ""}">{t(lbl)}</text>')
        crit0 = bars[0][1][0]
        step1 = set(r["steps"][0]["actions"])
        crit1 = open_(step1)[0]
        acts = ", ".join(str(x) for x in r["steps"][0]["actions"])
        stats = (f'<div class="bigs"><div><b>{crit0} → {crit1}</b><span>critical finding types after step 1 (action{"s" if len(step1) > 1 else ""} {acts})</span></div>'
                 + (f'<div><b>{n2(f["average"])} → {n2(f["projected_average"])}</b><span>projected {"score" if self.one else "average"} if all audit changes are done</span></div>'
                    if f["projected_average"] is not None else "") + "</div>")
        chart = (f'<h3 class="ch">Open findings as each action is completed</h3><div class="csub">Critical / high finding types left open '
                 f'(rows on the security page), using the action mapping on the actions page</div>'
                 f'<div class="lgd"><span class="sv sv-c"><i></i>Critical</span><span class="sv sv-h"><i></i>High</span></div>'
                 f'<svg viewBox="0 0 {W} {H}" class="rsvg">{svg}</svg>{stats}')
        dec = "".join(f'<div class="dc"><span class="dn">{i + 1}</span><div><b>{t(x["title"])}</b><p>{t(x["text"])}</p></div></div>'
                      for i, x in enumerate(r["decisions"]))
        right = (f'<div class="sh">Decisions needed from management</div>{dec}'
                 f'<p class="note">The chart counts finding types, not per-repo instances; {"the audit states" if self.one else "the audits state"} {f["critical"]} critical and {f["high"]} high.</p>')
        return self.page(10, "Roadmap & decisions", r["title"], "",
                         f'<div class="steps">{steps}</div><div class="two rm"><div>{chart}</div><div>{right}</div></div>')

    # 11
    def about(self):
        d, f, a, sev = self.d, self.f, self.d["about"], self.d["severity"]
        setups = sorted({" · ".join(x for x in (r.get("agent"), r.get("model"), r.get("check") and f"model check {r['check']}") if x)
                         for r in f["repos"]})
        src = [f"<b>{plural(self.nrepos, 'audit report')}</b> ({t(', '.join(r['repo'] for r in f['repos']))}; {t('; '.join(setups))})."]
        if self.respondents:
            src.append(f"<b>Questionnaire results</b> from {plural(self.respondents, 'respondent')}"
                       + (" (one answers file reused for every repo)." if self.q.get("single") else " (one per report)."))
        else:
            src.append("<b>No questionnaire results</b> in any report.")
        src.append(f"<b>Full detail:</b> <code>{t(d['md_report'])}</code>, the Markdown report this page set summarises.")
        src += [t(x) for x in a.get("sources", [])]
        conf = ("No names or emails. The questionnaire is self-administered: one person's answers graded against fixed anchors, "
                "a practice indicator, not an employee evaluation. This report describes security findings; share it internally only.")
        if self.q.get("single"):
            conf += " The questionnaire sections describe one person's answers."
        guide = [('<span class="sv sv-c"><i></i>Critical</span>', f"{t(sev['critical'])}. Fix now."),
                 ('<span class="sv sv-h"><i></i>High</span>', f"{t(sev['high'])}. Fix soon."),
                 (verdict_chip("Aligned"), "The sources agree, whether the picture they give is good or bad."),
                 (verdict_chip("Overstated"), "The questionnaire claims or knows more than the repos show."),
                 (verdict_chip("Understated"), "The questionnaire is lower than the repos show: an awareness gap."),
                 (verdict_chip("Mixed"), "Answers or repos point in different directions."),
                 (verdict_chip("Single source"), "Only one source covers the theme."),
                 (level_chip("Strong") + level_chip("Partial") + level_chip("Weak"),
                  "Level per source and theme. Audit levels come from the average score (Strong ≥ 3.5, Partial 2.5–3.4, Weak < 2.5), "
                  "stepped down where a critical finding sits in the theme.")]
        gh = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in guide)
        lim = "".join(f"<li>{t(x)}</li>" for x in a["limits"])
        body = (f'<div class="two ab"><div><div class="sh">Sources</div>{"".join(f"<p>{x}</p>" for x in src)}'
                f'<div class="conf"><b>Confidentiality.</b> {conf}</div><div class="sh">Reading guide</div><table class="gd">{gh}</table></div>'
                f'<div><div class="sh">Limits of this report</div><ul>{lim}</ul></div></div>')
        return self.page(11, "About this report", "Sources, definitions and limits", "", body)

    def render(self):
        pages = [self.cover(), self.summary(), self.comparison(), self.knowledge(), self.disagreements(), self.scorecard(),
                 self.findings(), self.questionnaire(), self.actions(), self.roadmap(), self.about()]
        title = f'{t(self.d["project"])} · AI Adoption Audit · Management report'
        return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>'
                f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">'
                f'<style>{CSS}</style></head><body>{"".join(pages)}</body></html>')


CSS = """
@page{size:297mm 210mm;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:Inter,"Helvetica Neue",Arial,"Liberation Sans","DejaVu Sans",sans-serif;color:#1b1e23;font-size:10.5px;line-height:1.42}
.page{width:297mm;height:210mm;padding:11mm 13mm 0;position:relative;overflow:hidden;break-after:page;page-break-after:always}
.page:last-child{break-after:auto;page-break-after:auto}
footer{position:absolute;left:13mm;right:13mm;bottom:6mm;border-top:1px solid #dcdcdc;padding-top:6px;display:flex;justify-content:space-between;font-size:8.5px;color:#7a7f87}
.eb{font-size:9.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#2463c4;margin-bottom:5px}
h2{font-size:22px;font-weight:700;letter-spacing:-.01em;line-height:1.2;margin-bottom:6px}
.lede{font-size:12px;color:#2a2e35;max-width:250mm;margin-bottom:12px}
h3{font-size:13px;font-weight:700}
code{font-family:"DejaVu Sans Mono",Menlo,Consolas,monospace;font-size:.88em;background:#eef0f3;border-radius:3px;padding:0 3px}
small{font-size:inherit}
.mut{color:#4b5059}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12mm}
.sh{font-size:10px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;margin:4px 0 6px}
.note{font-size:9.5px;color:#4b5059;margin-top:8px;display:flex;gap:6px;align-items:center}
.ic{width:15px;height:15px;flex:none;vertical-align:middle}
.nb{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;border-radius:50%;background:#14213d;color:#fff;font-size:9.5px;font-weight:700;margin-right:3px}
/* chips */
.lv,.vd,.sv,.ef,.el{display:inline-flex;align-items:center;gap:5px;border-radius:11px;padding:2px 8px;font-size:9.5px;font-weight:600;margin-right:4px;white-space:nowrap}
.lv i,.vd i,.sv i,.ef i,.el i{width:6px;height:6px;border-radius:50%;display:inline-block}
.lv-strong{background:#e6f5e8}.lv-strong i{background:#1f9d3a}
.lv-partial{background:#fdf3d8}.lv-partial i{background:#f2ae1c}
.lv-weak{background:#fbe5e5}.lv-weak i{background:#d33a3a}
.lv-na{background:#ececec}.lv-na i{background:#9aa0a6}
.lvs{color:#7a7f87;font-weight:500}
.vd{font-size:10.5px;padding:3px 10px}
.vd-al{background:#e7effc}.vd-al i{background:#2f6fd6}
.vd-ov{background:#fdebe2}.vd-ov i{background:#ee8456}
.vd-un{background:#e6f5e8}.vd-un i{background:#1f9d3a}
.vd-mx{background:#ececec}.vd-mx i{background:#8a8f96}
.vd-ss{background:#efeaf8}.vd-ss i{background:#7b5cc4}
.sv-c{background:#fbe5e5}.sv-c i{background:#d33a3a}
.sv-h{background:#fdebe2}.sv-h i{background:#ee8456}
.ef-g{background:#e6f5e8}.ef-g i{background:#1f9d3a}
.ef-b{background:#e7effc}.ef-b i{background:#2f6fd6}
.ef-o{background:#fdebe2}.ef-o i{background:#ee8456}
/* cover */
.cover{background:#0f2242;color:#fff;padding:16mm 18mm}
.cover .eb{color:#8ab4f0;letter-spacing:.12em}
.cover h1{font-size:62px;font-weight:800;letter-spacing:-.02em;margin:16px 0 18px}
.cover code{background:rgba(255,255,255,.14);color:#fff}
.hl{font-size:28px;font-weight:600;line-height:1.25}
.hl2{font-size:28px;font-weight:600;line-height:1.25;color:#8ab4f0}
.clede{font-size:14px;color:#c9d2e0;max-width:220mm;margin-top:16px}
.scale{margin:26px 0 0 6mm;width:225mm}
.sl{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:#a9b4c6;font-weight:600}
.ssvg{width:100%;height:auto;overflow:visible}
.ssvg .tk{fill:#a9b4c6;font-size:13px;text-anchor:middle}
.ssvg .lt{fill:#fff;font-size:15px;font-weight:700}
.ssvg .lp{fill:#8ab4f0;font-size:15px;font-weight:700}
.wf{font-size:14px;color:#e4e9f1;max-width:225mm;margin-top:22px}
.cbar{position:absolute;left:18mm;right:18mm;bottom:14mm;border-top:1px solid #3b4d6b;padding-top:14px;display:flex;align-items:flex-end}
.ck{width:52mm}.ck b{display:block;font-size:30px;font-weight:700}.ck span{font-size:10.5px;color:#c9d2e0}
.cd{margin-left:auto;text-align:right;font-size:10px;color:#c9d2e0;line-height:1.7}
/* summary */
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:7mm;margin:4px 0 14px}
.tile{border-top:3px solid #14213d;padding-top:8px}
.tn-blue{border-color:#8ab4f0}.tn-red{border-color:#d33a3a}.tn-orange{border-color:#ee8456}.tn-green{border-color:#1f9d3a}.tn-navy{border-color:#1f4f9c}
.tl{font-size:10.5px;color:#2a2e35}.tv{font-size:34px;font-weight:700;letter-spacing:-.02em;line-height:1.25}
.tv small{font-size:14px;color:#7a7f87;font-weight:500;margin-left:3px}.tnote{font-size:9.5px;color:#6b7078}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:6mm;margin-bottom:14px}
.card{background:#f4f4f2;border-radius:6px;border-top:3px solid #1f9d3a;padding:10px 13px 12px}
.cd-o{border-color:#ee8456}.cd-r{border-color:#d33a3a}
.ck2{display:flex;gap:7px;align-items:center;font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#4b5059;margin-bottom:5px}
.card h3{font-size:15px;margin-bottom:4px}.card p{font-size:11px;color:#3a3f47}
.sr{display:grid;grid-template-columns:42mm 1fr;border-top:1px solid #dcdcdc;padding:8px 0;align-items:center}
.sr b{display:block;font-size:11.5px}.sr small{font-size:9px;color:#7a7f87}.sr p{font-size:11px}
/* comparison */
.chips{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.cc{display:inline-flex;align-items:center;gap:4px;font-size:15px;margin-right:6px}
.lg{margin-left:auto;font-size:9px;color:#7a7f87;display:flex;align-items:center;gap:2px}
table{border-collapse:collapse;width:100%}
th{font-size:8.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#6b7078;text-align:left;padding:5px 6px;border-bottom:1px solid #cfcfcf}
td{padding:6px 6px;border-bottom:1px solid #e3e3e3;vertical-align:top}
td.th{font-weight:700;font-size:11px}
.cmp td p{font-size:9.8px;margin-top:3px;color:#33373e}
.cmp td small{display:block;font-size:9px;color:#7a7f87;margin-top:3px}
.cmp th:nth-child(1){width:44mm}.cmp th:nth-child(4){width:34mm}
/* knowledge */
.kstat{display:flex;align-items:center;gap:10px;margin-bottom:8px}.kstat b{font-size:42px;line-height:1}.kstat span{font-size:10.5px;color:#4b5059;max-width:70mm}
.kt td{padding:9px 6px}.kt td.th{width:44mm}
.kn{white-space:nowrap}.kn b{margin-left:5px;font-size:11px}
.ev{display:flex;gap:6px}.ev p{font-size:10px;color:#3a3f47}
.ph{font-size:14px;margin-bottom:2px}.psub{font-size:10px;color:#6b7078;margin-bottom:6px}
.pr{display:flex;gap:9px;border-top:1px solid #dcdcdc;padding:8px 0}.pr b{font-size:12px}.pr p{font-size:10.5px;color:#3a3f47}
.els{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin:8px 0}.elh{font-weight:700;font-size:10.5px;margin-right:4px}
.el-p{background:#e6f5e8}.el-p i{background:#1f9d3a}.el-m{background:#fbe5e5}.el-m i{background:#d33a3a}
.concl{background:#f4f4f2;border-radius:6px;padding:11px 14px;font-size:11px;margin-top:8px}
/* disagreements */
.dis td{padding:9px 6px}.dis td:nth-child(1){width:9mm}.dis td.th{width:42mm;font-size:12px}
.dis p{font-size:10.3px;position:relative;padding-left:13px}.dis p i{position:absolute;left:0;top:4px;width:7px;height:7px;border-radius:50%}
.dq i{background:#2f6fd6}.de i{background:#ee8456}
.sw{background:#f4f4f2;border-radius:6px;padding:7px 10px}.sw b{display:block;font-size:10.5px}.sw span{font-size:9px;color:#7a7f87;display:flex;align-items:center;gap:5px;margin-top:3px}
.dis td:nth-child(5){width:62mm}
/* scorecard */
.ch{font-size:13px;margin-top:4px}.csub{font-size:9.5px;color:#6b7078;margin-bottom:5px}
.lgd{display:flex;gap:4px;margin-bottom:6px}
.bars{position:relative;padding:14px 0 0 50mm}
.grid{position:absolute;left:50mm;right:22mm;top:0;bottom:0}
.grid span{position:absolute;top:0;bottom:0;border-left:1px solid #ececec;font-size:8.5px;color:#9aa0a6;padding-left:0;transform:translateX(-50%);text-indent:-2px}
.br{position:relative;height:16mm}
.bl{position:absolute;left:-50mm;width:48mm;text-align:right;top:3px;font-size:11px}
.bt{position:relative;margin-right:22mm;height:100%}
.bf{height:7.5mm;border-radius:0 4px 4px 0}
.bf-strong{background:#1f9d3a}.bf-partial{background:#f2ae1c}.bf-weak{background:#d33a3a}.bf-na{background:#9aa0a6}
.bv{position:absolute;top:5px;margin-left:6px;font-weight:700;font-size:11.5px;white-space:nowrap}.bv small{font-weight:500;font-size:9.5px;color:#4b5059}
.bs{font-size:9px;color:#7a7f87;margin-top:2px}
.rt td{padding:5px 4px;vertical-align:middle}.rt td small{display:block;font-size:8.5px;color:#7a7f87}
.rt td:nth-child(1){width:40mm}.rt td:nth-child(3),.rt td:nth-child(4),.rt th:nth-child(3),.rt th:nth-child(4){width:11mm;text-align:center}
.trk div{position:relative;height:16px;margin:0 16px}
.trk .ax{height:12px}.ax span{position:absolute;transform:translateX(-50%);font-weight:500}
.trk i{position:absolute;top:50%;transform:translate(-50%,-50%);border-radius:50%;display:block}
.trk i.seg{transform:translateY(-50%);height:2px;background:#8ab4f0;border-radius:0}
.trk i.dt{width:9px;height:9px;background:#1f4f9c}.trk i.dp{width:9px;height:9px;background:#8ab4f0}
.trk i.big{width:12px;height:12px}
.trk em{position:absolute;top:50%;font-style:normal;font-size:9.5px;transform:translateY(-50%)}
.trk em.vt{margin-left:-36px;font-weight:700}.trk em.vp{margin-left:9px;color:#4b5059}
.cb{display:inline-block;min-width:20px;padding:1px 5px;border-radius:4px;font-weight:700;font-size:10px;border-left:3px solid}
.cb-c{background:#fbe5e5;border-color:#d33a3a}.cb-h{background:#fdebe2;border-color:#ee8456}
.tot td{border-top:2px solid #14213d;font-size:11px}.tot td.rc{white-space:nowrap}
.box{background:#f4f4f2;border-radius:6px;padding:10px 13px;margin-top:10px}
.bh{font-size:9.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;margin-bottom:5px}
.bi{display:flex;gap:7px;margin:5px 0}.bi p{font-size:10.3px}
/* matrix */
.mx td,.mx th{padding:4px 4px}.mx .rc{text-align:center;width:17mm}.mx th.rc{font-size:8px;letter-spacing:.02em;text-transform:none;vertical-align:bottom}
.mx td.fl{font-size:10.5px}
.sq{display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;border-radius:4px;background:#f0f0ee;color:#fff;font-size:9px;font-weight:700}
.sq-c{background:#d33a3a}.sq-h{background:#ee8456}
.grp td{border-bottom:1px solid #e3e3e3;padding-top:8px}
.p-mx .mx .rc{width:12mm}.p-mx .sq{width:13px;height:13px}
.p-mx .mx td,.dense .mx td{padding-top:2px;padding-bottom:2px}.p-mx .mx td.fl,.dense .mx td.fl{font-size:10px}
.dense .rt td{padding:2px 4px}.dense .rt td b{font-size:10.5px}.dense .rt td small{display:inline;margin-left:6px;font-size:8px}
.dense .box{margin-top:6px;padding:7px 12px}.dense .bi{margin:3px 0}
/* questionnaire */
.qks{display:grid;grid-template-columns:repeat(2,1fr);gap:5mm;margin-bottom:10px}
.qk{border-top:3px solid #1f4f9c;padding-top:6px}.qk b{display:block;font-size:24px;line-height:1.2}.qk b small{font-size:11px;color:#7a7f87;font-weight:500;margin-left:3px}
.qk span{display:block;font-size:10.5px}.qk em{display:block;font-style:normal;font-size:9px;color:#7a7f87}
.pb{display:grid;grid-template-columns:30mm 1fr 15mm;align-items:center;gap:8px;margin:5px 0;font-size:10.5px}
.pt{height:8px;background:#ececec;border-radius:4px;overflow:hidden}.pt div{height:100%;background:#2f6fd6;border-radius:4px}
.pb b{text-align:right}
.prof{font-size:10px;color:#3a3f47;margin-top:8px}
.qt td{padding:4px 5px;font-size:10px}.qt td:first-child{white-space:nowrap}
.qt.claims td:not(:first-child),.qt.claims th:not(:first-child){text-align:center}.qt td.bad{color:#d33a3a;font-weight:700}
.gr{display:grid;grid-template-columns:40mm 1fr 14mm;align-items:center;font-size:10.5px;margin:3px 0}.gr b{text-align:right}
.dots i{display:inline-block;width:10px;height:10px;border-radius:50%;background:#e3e3e3;margin-right:4px}.dots i.on{background:#2f6fd6}
.qq .ch{margin-top:8px}
/* actions */
.act td{padding:7px 6px;vertical-align:middle}.act td:nth-child(1){width:9mm}.act td.th{width:52mm;font-size:11.5px}
.act td.mut{font-size:10px}.act .grp td{font-weight:700;color:#2463c4;font-size:10px;letter-spacing:.06em;text-transform:uppercase;border-bottom:2px solid #14213d}
.fx{width:50mm}.fx small{display:block;font-size:9px;color:#6b7078;margin-top:3px}.act td:nth-child(5){width:26mm}
/* roadmap */
.steps{display:flex;align-items:stretch;gap:4mm;margin:6px 0 12px}
.st{flex:1;border-radius:6px;padding:10px 13px;border-top:3px solid}
.st-0{background:#fbe9e9;border-color:#d33a3a}.st-1{background:#e7effc;border-color:#2463c4}.st-2{background:#e6f5e8;border-color:#1f9d3a}
.stl{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#d33a3a}
.st-1 .stl{color:#2463c4}.st-2 .stl{color:#1f9d3a}
.st h3{font-size:14px;margin:2px 0}.st p{font-size:10.5px;color:#3a3f47;margin-bottom:6px}
.arr{align-self:center;font-size:18px;color:#7a7f87}
.rsvg{width:100%;height:auto}.rsvg .ya{font-size:10px;fill:#7a7f87;text-anchor:end}
.rsvg .bvl{font-size:11px;font-weight:700;text-anchor:middle;fill:#1b1e23}.rsvg .bxl{font-size:10.5px;text-anchor:middle;fill:#4b5059}.rsvg .bxl.b{font-weight:700;fill:#1b1e23}
.bigs{display:grid;grid-template-columns:1fr 1fr;gap:6mm}.bigs div{border-top:3px solid #dcdcdc;padding-top:6px}
.bigs b{display:block;font-size:24px}.bigs span{font-size:9.5px;color:#4b5059}
.dc{display:flex;gap:10px;border-top:1px solid #dcdcdc;padding:8px 0}.dc b{font-size:11.5px}.dc p{font-size:10.3px;color:#3a3f47}
.dn{flex:none;width:22px;height:22px;border-radius:4px;background:#e7effc;color:#2463c4;font-weight:700;display:flex;align-items:center;justify-content:center}
.rm{gap:10mm}
/* about */
.ab p{font-size:11px;margin-bottom:5px}
.conf{background:#f4f4f2;border-left:3px solid #d33a3a;border-radius:4px;padding:8px 12px;font-size:10.3px;margin:8px 0 10px}
.gd td{font-size:10px;padding:4px 4px;vertical-align:middle}.gd td:first-child{width:46mm}
.ab ul{padding-left:16px}.ab li{font-size:10.5px;margin-bottom:5px}
"""


# ---------------------------------------------------------------- printing

def find_browser():
    env = os.environ.get("AI_AUDIT_CHROME")
    if env:
        return env if os.path.isfile(env) else None
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge", "msedge", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
        if base:
            cands += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                      os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")]
    home = os.path.expanduser("~")
    for pat in ("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome",
                "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
                "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"):
        cands += sorted(glob.glob(pat.replace("~", home)), reverse=True)
    return next((c for c in cands if os.path.isfile(c)), None)


def print_pdf(browser, html_path, out):
    with tempfile.TemporaryDirectory(prefix="ai-audit-chrome-") as prof:
        cmd = [browser, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
               "--disable-background-networking", "--disable-sync", "--disable-component-update", "--mute-audio",
               f"--user-data-dir={prof}", "--no-pdf-header-footer", "--print-to-pdf-no-header",
               f"--print-to-pdf={os.path.abspath(out)}", "file://" + os.path.abspath(html_path)]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"browser failed: {e}"
    if not os.path.isfile(out):
        return "browser failed: " + (r.stderr.strip().splitlines() or ["no PDF written"])[-1][:300]
    with open(out, "rb") as fh:
        if fh.read(5) != b"%PDF-":
            os.remove(out)
            return "browser wrote something that is not a PDF"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inputs", nargs="*", help="audit reports or folders (as for summarize_audits.py)")
    ap.add_argument("--manifest", help="project manifest (ai-audit/_project.json); implies --single-respondent")
    ap.add_argument("--single-respondent", action="store_true", help="one answers file was reused for every repo")
    ap.add_argument("--data", required=True, help="the narrative JSON (references/visual-report.md)")
    ap.add_argument("--out", help="the PDF to write; must not exist")
    ap.add_argument("--html-only", metavar="HTML", help="write only the HTML here; must not exist")
    a = ap.parse_args()
    if not (a.out or a.html_only) or (not a.inputs and not a.manifest):
        ap.print_help()
        return 1
    reports, single, info = sa.load(a.inputs, a.manifest, a.single_respondent)
    for w in info["warnings"]:
        print(w, file=sys.stderr)
    if not reports:
        print("ERROR: no audit reports found", file=sys.stderr)
        return 1
    single = single or len(reports) == 1
    facts = sa.facts(reports, single, info)
    try:
        with open(a.data, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"ERROR: cannot read {a.data}: {e}", file=sys.stderr)
        return 2
    try:
        for w in validate(data, facts):
            print(w, file=sys.stderr)
    except TooLarge as e:
        print(f"PDF skipped: {e}. The Markdown report is the complete report; say so in one line.",
              file=sys.stderr)
        return 5
    except Invalid as e:
        print(f"ERROR: invalid narrative JSON: {e}", file=sys.stderr)
        return 2
    page = Doc(data, facts).render()
    if a.out and not a.out.lower().endswith(".pdf"):
        print("ERROR: --out must end in .pdf", file=sys.stderr)
        return 2
    targets = [x for x in (a.html_only, a.out, a.out and a.out[:-4] + ".html") if x]
    taken = [x for x in targets if os.path.exists(x)]
    if taken:
        print(f"ERROR: will not overwrite {', '.join(taken)}; use the next free suffix (-2, -3)", file=sys.stderr)
        return 2

    def write_html(path):
        with open(path, "x", encoding="utf-8") as fh:
            fh.write(page)

    if a.html_only:
        write_html(a.html_only)
        print(f"HTML written: {a.html_only}")
        if not a.out:
            return 0
    fallback = a.out[:-4] + ".html"
    browser = find_browser()
    if not browser:
        write_html(fallback)
        print(f"No Chrome, Chromium or Edge found; PDF skipped. HTML written instead: {fallback} "
              "(open it in a browser and print to PDF, A4 landscape, no margins).")
        return 3
    with tempfile.TemporaryDirectory(prefix="ai-audit-render-") as tmp:
        tmp_html = os.path.join(tmp, "report.html")
        with open(tmp_html, "w", encoding="utf-8") as fh:
            fh.write(page)
        err = print_pdf(browser, tmp_html, a.out)
    if err:
        write_html(fallback)
        print(f"{err}. HTML written instead: {fallback} (open it in a browser and print to PDF, A4 landscape, no margins).")
        return 4
    print(f"PDF written: {a.out} ({PAGES} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
