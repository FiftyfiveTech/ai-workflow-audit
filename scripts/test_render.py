#!/usr/bin/env python3
"""Tests for Step 5, the visual report: summarize_audits.py --json and scripts/render_report.py.
Run from the repo root: python3 scripts/test_render.py

Uses the fixture reports in tests/fixtures/consolidation/ and the example narrative JSON in
skills/ai-workflow-audit/assets/visual-report-example.json. The PDF check runs only when a
Chrome, Chromium or Edge is found (set AI_AUDIT_CHROME to point at one); otherwise it is skipped.
"""
import copy, json, os, pathlib, re, shutil, subprocess, sys, tempfile

root = pathlib.Path(__file__).resolve().parent.parent
skill = root / "skills/ai-workflow-audit"
summarize, render = skill / "scripts/summarize_audits.py", skill / "scripts/render_report.py"
example = json.loads((skill / "assets/visual-report-example.json").read_text())
fx = root / "tests/fixtures/consolidation"
larkspur = [str(fx / f"{r}-2026-10-15.md") for r in ("orders-api", "billing-service", "web-app")]
tmp = pathlib.Path(tempfile.mkdtemp(prefix="render-test-"))
failures = []


def run(script, *args):
    r = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, timeout=240)
    return r.returncode, r.stdout, r.stderr


def data_file(d, name):
    p = tmp / f"{name}.json"
    p.write_text(json.dumps(d))
    return p


def html_of(d, name, *inputs):
    """Render d to HTML; returns (exit code, html or '', stderr)."""
    out = tmp / f"{name}.html"
    code, _, err = run(render, "--data", data_file(d, name), *(inputs or ("--single-respondent", *larkspur)), "--html-only", out)
    return code, out.read_text() if out.exists() else "", err


def expect(cond, label):
    if not cond:
        failures.append(label)


# 1. summarize_audits.py --json: the numbers the renderer uses.
code, out, _ = run(summarize, "--json", "--single-respondent", *larkspur)
f = json.loads(out) if code == 0 else {}
expect(code == 0, f"--json exited {code}")
expect(f.get("average") == 2.36 and f.get("range") == [1.65, 3.15], "--json: average and range")
expect((f.get("critical"), f.get("high")) == (5, 7), "--json: Critical/High totals")
expect(f.get("projected_average") == 3.48, "--json: projected average")
expect("Guardrails & Hooks" in f.get("recurring", []) and "Instructions & Memory" not in f.get("recurring", []), "--json: recurring gaps")
themes = {t["theme"]: t for t in f.get("themes", [])}
expect(len(themes) == 7 and themes.get("Guardrails, permissions & secrets", {}).get("avg") == 1.5, "--json: theme averages")
q = f.get("questionnaire", {})
expect(q.get("respondents") == 1 and (q.get("score_min"), q.get("score_max")) == (67, 77), "--json: single-respondent Practice Score range")
expect(q.get("claims", {}).get("X2", {}).get("contradicted_in") == ["orders-api", "billing-service"], "--json: X2 contradicted in")
expect(all("practice" not in r and "score_practice" not in r for r in f.get("repos", [])), "--json: a Practice Score is paired with a repo")
code, out, _ = run(summarize, "--json", fx)
fm = json.loads(out) if code == 0 else {}
expect(fm.get("questionnaire", {}).get("respondents") == 3, "--json folder: one respondent per report")
expect("contradicted_in" not in json.dumps(fm.get("questionnaire", {})), "--json folder: several respondents must give counts only")
expect(any("questionnaire" in w for w in fm.get("warnings", [])), "--json folder: WARN lines are kept in 'warnings'")
expect(re.search(r"@|champion", out, re.I) is None, "--json: output holds an email or ranks people")

# 2. The example renders: 11 pages, self-contained, no scripts, links, emails or rankings.
code, page, err = html_of(example, "example")
expect(code == 0, f"example render exited {code}: {err[-400:]}")
expect(page.count('<section class="page') == 11, "example: expected 11 pages")
expect("<script" not in page.lower(), "example: the page has a script")
expect(not re.search(r"\b(src|href)\s*=|https?://|@import|url\(", page), "example: the page loads or links something external")
expect(not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", page), "example: the page holds an email address")
expect(not re.search(r"champion|top performer|leaderboard", page, re.I), "example: the page ranks or recommends people")
expect("Default-src" in page or "default-src 'none'" in page, "example: the page has no Content-Security-Policy")
expect("billing-service" in page and "2.36" in page and "3.48" in page, "example: numbers from the reports are missing")
expect("<th>Contradicted in</th>" in page, "example: single respondent shows where claims are contradicted")
expect("WARN" not in err, f"example: length warnings on the shipped example: {err}")

# 3. Text is escaped.
d = copy.deepcopy(example)
d["cover"]["headline"] = "<script>alert(1)</script><img src=x>"
code, page, _ = html_of(d, "escape")
expect(code == 0 and "&lt;script&gt;" in page and "<script" not in page and "<img" not in page, "escaping: markup in a field reached the page")

# 4. Invalid data is rejected (exit 2) with a reason.
def rejected(d, name, needle):
    code, page, err = html_of(d, name)
    expect(code == 2 and needle in err and not page, f"{name}: expected exit 2 mentioning {needle!r}, got {code}: {err[-300:]}")

d = copy.deepcopy(example)
d["findings"]["rows"][0]["repos"] = ["billing-service"]
rejected(d, "bad-sum", "findings matrix for orders-api")
d = copy.deepcopy(example)
d["findings"]["rows"][0]["repos"].append("mobile")
rejected(d, "unknown-repo", "unknown repo")
d = copy.deepcopy(example)
d["findings"]["rows"][0]["action"] = 99
rejected(d, "unknown-action", "action 99 does not exist")
d = copy.deepcopy(example)
d["about"]["limits"].append("Ask dev.lead@example.com for access")
rejected(d, "email", "email address")
d = copy.deepcopy(example)
d["scorecard"]["works"].append("See https://example.com/dashboard")
rejected(d, "url", "contains a URL")
d = copy.deepcopy(example)
d["roadmap"]["decisions"].append({"title": "Appoint the Top Performers", "text": "Name two leads."})
rejected(d, "ranking", "must not rank or recommend people")
d = copy.deepcopy(example)
d["comparison"]["themes"].reverse()
rejected(d, "theme-order", "comparison.themes must be exactly")
d = copy.deepcopy(example)
del d["cover"]["way_forward"]
rejected(d, "missing-key", "missing cover.way_forward")
d = copy.deepcopy(example)
d["comparison"]["themes"][0]["verdict"] = "Great"
rejected(d, "verdict", "verdict must be one of")

d = copy.deepcopy(example)
d["cover"]["headline"] = "x" * 71
rejected(d, "too-long", "cover.headline: 71 characters, limit 70")
d = copy.deepcopy(example)
d["disagreements"]["items"] *= 3
rejected(d, "too-many", "disagreements.items: 9 entries, at most 6")


def synthetic(folder, n, critical=2, high=3):
    """n copies of the orders-api fixture under distinct repo names, each stating critical / high findings."""
    folder.mkdir()
    base = (fx / "orders-api-2026-10-15.md").read_text()
    row = "| 2.28 | 46 | 1.50 | Emerging | 11/11 | 2 | 3 |"
    names = [f"notification-gateway-svc-{i:02d}" for i in range(n)]
    for i, name in enumerate(names):
        text = base.replace("orders-api", name).replace("1" * 40, f"{i + 1:040x}")
        (folder / f"{name}-2026-10-15.md").write_text(text.replace(row, row.replace("| 2 | 3 |", f"| {critical} | {high} |")))
    return names


# 4b. Too many repos for the fixed layout: exit 5, nothing written.
big = tmp / "big"
synthetic(big, 11)
code, _, err = run(render, "--data", data_file(example, "big"), big, "--html-only", tmp / "big.html")
expect(code == 5 and "at most 10" in err and not (tmp / "big.html").exists(), f"11 repos: expected exit 5, got {code}: {err[-200:]}")

# 5. Never overwrites.
taken = tmp / "taken.html"
taken.write_text("keep")
code, _, err = run(render, "--data", data_file(example, "ow"), "--single-respondent", *larkspur, "--html-only", taken)
expect(code == 2 and "will not overwrite" in err and taken.read_text() == "keep", "overwrite: an existing output was replaced")

# 6. Several respondents (collected folder, one report without a questionnaire): counts only.
d = copy.deepcopy(example)
next(r for r in d["findings"]["rows"] if r["severity"] == "High")["repos"].append("legacy-service")
code, page, err = html_of(d, "folder", fx)
expect(code == 0, f"folder render exited {code}: {err[-300:]}")
expect("<th>Contradicted in</th>" not in page and "Practice Score average" in page, "folder: several respondents must give counts only")

# 6b. A single audit report (single-repo mode, or a project with one finished report): one respondent, no project average.
one = copy.deepcopy(example)
one["findings"]["rows"] = [dict(r, repos=["web-app"]) for r in one["findings"]["rows"] if "web-app" in r["repos"]]
one["md_report"] = "web-app-2026-10-15.md"
web_app = fx / "web-app-2026-10-15.md"
code, page, err = html_of(one, "single", web_app)
expect(code == 0, f"single report render exited {code}: {err[-300:]}")
expect(page.count('<section class="page') == 11, "single report: expected 11 pages")
expect("<th>Contradicted in</th>" in page, "single report: one report is one respondent")
expect("Project average" not in page and "avg of 1 repo" not in page and "across 1 repo" not in page,
       "single report: project-average wording on a one-repo PDF")
expect("Today 3.15 · web-app" in page and "Repo audited" in page, "single report: cover wording")
code, page, err = html_of(example, "single-bad", web_app)
expect(code == 2 and "findings matrix for web-app" not in err and "unknown repo" in err,
       "single report: findings naming other repos must be rejected")

# 7. The PDF, when a browser is available.
sys.path.insert(0, str(skill / "scripts"))
import render_report  # noqa: E402
if render_report.find_browser():
    pdf = tmp / "larkspur.pdf"
    code, out, err = run(render, "--data", data_file(example, "pdf"), "--single-respondent", *larkspur, "--out", pdf)
    blob = pdf.read_bytes() if pdf.exists() else b""
    expect(code == 0 and blob.startswith(b"%PDF-"), f"pdf: exit {code}, {out}{err[-300:]}")
    pages = len(re.findall(rb"/Type\s*/Page\b(?!s)", blob))
    expect(pages == 11, f"pdf: expected 11 pages, found {pages}")
    expect(not (tmp / "larkspur.html").exists(), "pdf: a fallback HTML was written although the PDF succeeded")
    one_pdf = tmp / "web-app.pdf"
    code, out, err = run(render, "--data", data_file(one, "one-pdf"), web_app, "--out", one_pdf)
    expect(code == 0 and one_pdf.exists() and len(re.findall(rb"/Type\s*/Page\b(?!s)", one_pdf.read_bytes())) == 11,
           f"single report pdf: exit {code}, {out}{err[-300:]}")
    code, _, err = run(render, "--data", data_file(example, "pdf2"), "--single-respondent", *larkspur, "--out", pdf)
    expect(code == 2 and "will not overwrite" in err, "pdf: an existing PDF was overwritten")
    pdf_note = "PDF rendered"
else:
    pdf_note = "PDF check skipped: no Chrome, Chromium or Edge found"

# 7b. Worst case at every cap, every limited text at its maximum length: nothing may run past a page's footer.
def worst_case(names):
    sys.path.insert(0, str(skill / "scripts"))
    lim = render_report.LIMITS
    filler = ("Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt " * 6)

    def fill(node, path=""):
        if isinstance(node, dict):
            return {k: fill(v, f"{path}.{k}" if path else k) for k, v in node.items()}
        if isinstance(node, list):
            return [fill(v, path) for v in node]
        if isinstance(node, str) and path in lim:
            return filler[:lim[path]]
        return node
    c, A = render_report.COUNTS, list(range(1, render_report.COUNTS["actions (all groups)"] + 1))
    rows = c["findings.rows"]
    d = copy.deepcopy(example)
    # every row covers every repo; the synthetic reports state WORST_CRITICAL / rows - WORST_CRITICAL
    d["findings"]["rows"] = [{"severity": "Critical" if i < WORST_CRITICAL else "High", "finding": "f", "repos": names,
                              "action": A[i % len(A)]} for i in range(rows)]
    d["disagreements"]["items"] = [dict(example["disagreements"]["items"][0], action=1)] * c["disagreements.items"]
    per = [len(A) // 3 + (1 if i < len(A) % 3 else 0) for i in range(3)]
    it = iter(A)
    item = dict(example["actions"]["groups"][0]["items"][2], themes=["t"])
    d["actions"]["groups"] = [{"name": "g", "items": [dict(item, n=next(it)) for _ in range(k)]} for k in per]
    d["roadmap"]["steps"] = [dict(example["roadmap"]["steps"][i], actions=A[i::3]) for i in range(3)]
    d["knowledge"]["rows"] = [example["knowledge"]["rows"][0]] * c["knowledge.rows"]
    d["knowledge"]["panel"] = [example["knowledge"]["panel"][0]] * c["knowledge.panel"]
    d["roadmap"]["decisions"] = [example["roadmap"]["decisions"][0]] * c["roadmap.decisions"]
    d["about"]["limits"] = ["l"] * c["about.limits"]
    d["about"]["sources"] = ["s"] * c["about.sources"]
    d["scorecard"]["works"] = ["w"] * c["scorecard.works"]
    d["questionnaire"]["notes"] = ["n"] * c["questionnaire.notes"]
    d["comparison"]["themes"] = [dict(x, verdict_note="v") for x in example["comparison"]["themes"]]
    return fill(d)


WORST_CRITICAL = 5
MEASURE = """<script>onload=function(){var o=[];document.querySelectorAll('section.page').forEach(function(p,i){
var b=p.getBoundingClientRect(),ft=p.querySelector('footer'),f=ft?ft.getBoundingClientRect().top:b.bottom,w=0,r=0;
p.querySelectorAll('*').forEach(function(e){if(e.closest('footer'))return;var x=e.getBoundingClientRect();if(!x.height)return;
w=Math.max(w,x.bottom-f);r=Math.max(r,x.right-b.right)});if(w>0.5||r>0.5)o.push('page '+(i+1)+': +'+Math.round(w)+'px down, +'+Math.round(r)+'px right')});
document.body.setAttribute('data-ov',o.join('; ')||'none')}</script>"""
browser = render_report.find_browser()
if browser:
    worst = tmp / "worst"
    names = synthetic(worst, render_report.MAX_REPOS, WORST_CRITICAL, render_report.COUNTS["findings.rows"] - WORST_CRITICAL)
    code, page, err = html_of(worst_case(names), "worst", worst)
    expect(code == 0, f"worst case: render exited {code}: {err[-400:]}")
    if code == 0:
        probe = tmp / "probe.html"
        probe.write_text(re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', "", page).replace("</body>", MEASURE + "</body>"))
        r = subprocess.run([browser, "--headless", "--disable-gpu", "--no-first-run", f"--user-data-dir={tmp / 'prof'}",
                            "--window-size=1400,1000", "--virtual-time-budget=3000", "--dump-dom", probe.as_uri()],
                           capture_output=True, text=True, timeout=120)
        m = re.search(r'data-ov="([^"]*)"', r.stdout)
        expect(m is not None and m.group(1) == "none", "worst case overflows: " + (m.group(1) if m else "could not measure"))

# 8. No browser: the HTML fallback is written next to --out and the exit code is 3.
env = dict(os.environ, AI_AUDIT_CHROME=str(tmp / "no-such-browser"))
r = subprocess.run([sys.executable, str(render), "--data", str(data_file(example, "nob")), "--single-respondent", *larkspur,
                    "--out", str(tmp / "nob.pdf")], capture_output=True, text=True, timeout=60, env=env)
expect(r.returncode == 3 and (tmp / "nob.html").exists() and not (tmp / "nob.pdf").exists(), f"no browser: exit {r.returncode}")

shutil.rmtree(tmp, ignore_errors=True)
if failures:
    print(f"{len(failures)} visual report checks failed:\n- " + "\n- ".join(failures)); sys.exit(1)
print(f"Visual report checks passed (--json facts, 11 pages, escaping, validation, no overwrite, privacy; {pdf_note}).")
