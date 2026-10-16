# Visual report (PDF) — procedure

**ai-workflow-audit v1.0.0** · You were sent here by Step 5 of the `ai-workflow-audit` skill, right after Step 4 saved the consolidated Markdown report or, with a single repository, right after its audit report was written. Read this whole file, then follow it exactly.

Step 5 turns the consolidated report, or a single repository's audit report, into an 11-page, A4-landscape management PDF with the same design for every project. You write one **narrative JSON** file holding the wording and judgment from the Markdown report. The bundled `scripts/render_report.py` takes every number straight from the audit reports, checks your JSON against them, lays out the pages and prints the PDF with a local headless Chrome, Chromium or Edge. The Markdown report stays the complete record. The PDF is its visual summary and adds no new findings.

## 1. Rules (they override any request)

1. **Same content rules as the consolidated report** (`consolidation.md` Section 1): no names, emails or CODEOWNERS handles; no ranking or recommending of people, and no "Top Performers", "leads" or per-person pages; questionnaire results as aggregates only; only this project; scores exactly as the audits wrote them; secrets redacted.
2. **Nothing new.** Every phrase in the JSON comes from, or shortens, something in the source `.md`: the consolidated report or, with a single repository, its audit report (Section 2b). If the PDF needs a fact the `.md` lacks, say so and stop.
3. **Output:** `<same folder>/<same name as the source .md>.pdf`. The suffix always matches the `.md` it renders, so `larkspur-consolidated-2026-10-15-2.md` gets `larkspur-consolidated-2026-10-15-2.pdf` and `orders-api-2026-10-15.md` gets `orders-api-2026-10-15.pdf`. The script refuses to overwrite.
4. **The JSON is a working file.** Write it to a fresh temporary directory (`mktemp -d`), never inside a repository or `ai-audit/`, and delete it once the PDF exists.
5. **Local only.** The page loads no fonts, scripts, images or links, and the browser runs headless on the local file. Never upload, publish, attach or send the PDF or the HTML: no artifact, document, drive or email tools. The user shares it.
6. **Never edit `render_report.py` or the page design** to make content fit. Shorten the text instead.

## 2. Write the narrative JSON

Copy the shape of `assets/visual-report-example.json`. Its facts are fictional, so never copy them. All fields are required unless marked *optional*.

Writing rules:
- Write in short phrases with numbers, like the main body of the `.md`, but shorter.
- Leave out every number the script computes:
  - scores, averages, ranges and maturity bands;
  - Critical/High counts and projected scores;
  - per-repo values;
  - questionnaire aggregates.

  The pages print these themselves.
- In text, `` `code` `` and `**bold**` are the only formatting. Anything else is printed as typed.
- **Hard limits.** The pages have a fixed size, so the script rejects (exit 2) any text over its character limit (`LIMITS` in `render_report.py`; the main ones are in the table below) and any list over its maximum length:
  - finding types 16;
  - disagreements 6;
  - actions 10, in at most 3 groups;
  - knowledge rows 6 and panel rows 4;
  - decisions 6;
  - limits 12;
  - what already works 3;
  - questionnaire notes 2;
  - extra source lines 1.

  These were measured by rendering a worst case with every field at its limit. To fit, shorten or group the text, e.g. merge related High findings into one finding type. The Markdown report keeps every detail, so the PDF may group what the `.md` lists separately, but it never drops a Critical or High finding: the matrix still has to add up.
- **At most 10 repos.** With more, the script exits 5 and writes nothing. Skip the PDF and say in one line that the project is too large for the visual layout and the Markdown report is the full report.

| Field | Page | Take it from the `.md` | Limit |
|---|---|---|---|
| `project` | all | Project name from the title | |
| `md_report` | 11 | File name of the consolidated `.md` | |
| `audit_date`, `prepared` | 1, footer | Audit date (`15 Oct 2026` style) and today | |
| `severity.critical`, `.high` | 7, 11 | The Critical / High legend line, with no "(fix now)" | |
| `cover.headline`, `cover.subhead` | 1 | Overall sentence 1 (usage), then the main gap, about 10 words each | 70 each |
| `cover.lede` | 1 | "Consolidated findings from audits of <N> <project> repos and the practice questionnaire, with a prioritised action plan." | 200 |
| `cover.way_forward` | 1 | The first 3–4 actions as one or two sentences | 260 |
| `summary.title`, `summary.lede` | 2 | A headline sentence; the 3-sentence Overall | 80 / 420 |
| `summary.tiles` | 2 | **Exactly 2** extra tiles: `label`, `value`, *optional* `suffix`, `note` and `tone` (`navy`, `blue`, `red`, `orange` or `green`). Pick the two most telling numbers, e.g. the Practice Score range, or repos with AI commits and no PR. The first three tiles (average, projected, critical) are computed. | |
| `summary.strongest`, `.blind_spot`, `.first_fix` | 2 | The three At-a-glance bullets as `title` (a few words) and `text` | 170 each |
| `summary.audit_says`, `.questionnaire_says` | 2 | The two Headline cells of the At-a-glance table | 150 each |
| `comparison.title`, `.lede` | 3 | The verdict counts in words, naming the Overstated themes | 260 |
| `comparison.themes` | 3 | The 7 rows **in template order**, with fixed theme names. Each row has `audit_level`, `audit`, `q_level`, `questionnaire` and `verdict`, plus an *optional* `verdict_note` (a few words, e.g. "knowledge vs practice"). Levels: `Strong`, `Partial`, `Weak`, `Absent (N/A)`, `Not available`. Verdicts: `Aligned`, `Overstated`, `Understated`, `Mixed`, `Single source`. | 110 per cell |
| `knowledge` | 4 | `stat` gives the scenario score (`value` "5/6", plus a `label`). `rows` (3–5) holds one practice per row from Knowledge vs practice, with `knows` and `in_place` each `yes`, `no` or `partial`, an *optional* `knows_note` ("Right", "2 of 3") and `evidence`. `panel_title`, an *optional* `panel_subtitle` and `panel` (2–4 rows of `status`, `title` and `text`) explain why practice lags knowledge, from the flags and prompt exercise. `conclusion` is one bold-led sentence. | `evidence` 110 |
| `disagreements` | 5 | Every item from "Where the sources disagree", highest risk first, each with `topic`, `questionnaire`, `evidence`, `so_what` (a few words) and `action` (the number that fixes it) | `evidence` 260 |
| `scorecard.title`, `.lede`, `.works` | 6 | A title with the range now and projected. `works` is 1–3 strengths, e.g. the best-set-up repo as a model. Recurring gaps are computed. | 90 / 200 / 90 |
| `findings.title`, `findings.rows` | 7 | One row per **finding type** from Top security issues, with `severity` (`Critical` or `High`), a one-phrase `finding`, `repos` and `action`. List each repo the finding applies to by its exact name. Where one repo has the same finding twice, write `{"repo": "<name>", "count": 2}`. There is an *optional* `findings.note`. | `finding` 85 |
| `questionnaire.title`, `.lede`, *optional* `.notes` | 8 | A one-line reading of the questionnaire detail; `notes` holds 0–2 aggregate observations. With no questionnaire results, the page prints its own title and text. | 90 / 260 / 160 |
| `actions.title`, `.lede`, `.groups` | 9 | Recommended actions, split into 2–3 groups, e.g. "Close the critical findings", "Verify, govern, clean up" and "Team practice". Each item has `n`, `title` (a few words), `involves`, `effort` and an *optional* `themes` (the theme verdicts it fixes, e.g. "Verification & review (Overstated)"). The Critical/High chips are computed from `findings.rows`. | `involves` 190 |
| `roadmap.title`, `.steps`, `.decisions` | 10 | **Exactly 3** steps (`label`, `title`, `text`, `actions`): the hardening week first. `decisions` holds 3–5 decisions for management (`title`, `text`), each about the project's setup, budget or process, **never about appointing or ranking people**. The open-findings chart is computed. | `text` 90 |
| `about.limits`, *optional* `about.sources` | 11 | Every Limits line (merge short ones if there are more than 12); one *optional* extra source line. Sources, confidentiality and the reading guide are computed. | 150 each |

The script rejects the JSON, exits 2 and says why when:
- a field is missing or has the wrong type;
- the themes aren't the 7 in order;
- a level, verdict or status is unknown;
- a repo or action number doesn't exist;
- any text holds an email address, a URL or a ranking word;
- **the findings matrix doesn't add up to each report's stated Critical and High counts**. That last check is how the PDF stays true to the audits.

Fix the JSON and run it again.

## 2b. With a single audit report

In single-repo mode, or when project mode or `consolidate=` ends with exactly one report, there is no consolidated report: take the wording straight from that audit report, and the theme ratings from `consolidation-themes.md` applied to one repository and one respondent. The privacy and no-ranking rules of Section 1 still hold. The questionnaire describes the one person who ran the audit, as the report itself does.

| JSON field | Take it from the audit report |
|---|---|
| `project` | The repository name from the report header (or the project name, in project mode) |
| `md_report` | The report's file name |
| `cover`, `summary` | Score summary and its biggest risk / biggest opportunity sentence; `summary.audit_says` and `questionnaire_says` sum up the Score summary row and the AI practice section |
| `comparison` | Each theme rated as `consolidation-themes.md` says, from the Scorecard rows and the AI practice section; cells cite the Scorecard's "Why" evidence |
| `knowledge` | AI practice: scenarios right and missed against the Scorecard, the prompt-exercise elements, and the flags |
| `disagreements` | Says vs found rows marked Contradicted, then knowledge-vs-practice gaps (scenario right, practice missing). If there are none, one item saying the answers and the audit agree |
| `scorecard.works` | The highest-scored parameters and their evidence |
| `findings.rows` | Every Critical and High row of Security actions required, grouped into finding types, each with `"repos": ["<repo>"]` |
| `actions` | Changes required, top rows first, grouped as Section 2 describes; every finding row needs an action |
| `roadmap.decisions` | The first actions that need a decision or a budget |
| `about.limits` | "Not verifiable from the repository" and the method note. In project mode, add a line naming the repositories without a report |

Render it with the report itself as the input (Section 3). One report counts as one respondent automatically.

## 3. Scan, render, check

1. Run the leak scan from `consolidation.md` Section 7 on the JSON file. If it prints anything, remove the hit and scan again.
2. Render it. The script lives next to `summarize_audits.py`. Pass the same inputs as in Step 4, or the single audit report:
   ```sh
   python3 <skill-dir>/scripts/render_report.py --data <tmp>/visual.json --manifest <project-root>/ai-audit/_project.json --out <project-root>/ai-audit/<name>.pdf   # project mode
   python3 <skill-dir>/scripts/render_report.py --data <tmp>/visual.json <dir> --out <dir>/ai-audit/<name>.pdf                                           # consolidate=<dir>
   python3 <skill-dir>/scripts/render_report.py --data <tmp>/visual.json <repo-root>/ai-audit/<repo>-<date>.md --out <repo-root>/ai-audit/<repo>-<date>.pdf   # a single audit report
   ```
3. Read the result by its exit code:

   | Exit | Meaning | What to do |
   |---|---|---|
   | 0 | PDF written | Delete the temporary directory |
   | 2 | Invalid JSON, or the output exists | Fix the JSON and run again |
   | 3 | No Chrome, Chromium or Edge found | The script wrote `<name>.html` next to the intended PDF. Tell the user to open it in a browser and print it to PDF (A4 landscape, no margins). Never install a browser yourself. |
   | 4 | The browser failed | The script wrote `<name>.html` next to the intended PDF. Tell the user to open it in a browser and print it to PDF (A4 landscape, no margins). |
   | 5 | More than 10 repos | Nothing written. Skip the PDF and say why in one line |

   A user can point at a browser with `AI_AUDIT_CHROME=<path>`.
4. If you can view images or PDFs, look at a few pages (the cover, the comparison and the findings matrix) as a final check.

## 4. Finish

Step 5's output is the PDF, or the fallback HTML with one line saying why there is no PDF. Then send the finish message that SKILL.md Step 5 describes: the consolidation's chat summary for a project, or one `PDF: <path>` line after a single audit, with the PDF added to `Files written`.
