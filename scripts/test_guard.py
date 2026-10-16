#!/usr/bin/env python3
"""Tests for hooks/ai-workflow-audit-guard.py. Run from the repo root: python3 scripts/test_guard.py

Every shell command in the audit procedure must pass the guard; every case in DENY must be blocked;
calls from any other agent must pass through untouched. Project mode (a folder holding several repos,
with the skill's manifest) gets the same checks, plus isolation from the sibling repository.
"""
import json, os, pathlib, re, subprocess, sys, tempfile

root = pathlib.Path(__file__).resolve().parent.parent
guard = root / "hooks/ai-workflow-audit-guard.py"
proc = (root / "skills/ai-workflow-audit/references/audit-procedure.md").read_text()

repo = pathlib.Path(tempfile.mkdtemp(prefix="guard-test-"))
subprocess.run(["git", "init", "-q", str(repo)], check=True)
(repo / "ai-audit").mkdir()
(repo / "ai-audit/old-repo-2026-01-01.md").write_text("earlier report\n")
data_dir = tempfile.mkdtemp(prefix="guard-data-")
env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(root), CLAUDE_PLUGIN_DATA=data_dir)


def run(tool, tool_input, agent="ai-workflow-audit:ai-workflow-audit", agent_id="a1", cwd=None):
    payload = {"session_id": "s1", "cwd": str(cwd or repo), "hook_event_name": "PreToolUse",
               "tool_name": tool, "tool_input": tool_input}
    if agent:
        payload.update(agent_type=agent, agent_id=agent_id)
    r = subprocess.run([sys.executable, str(guard)], input=json.dumps(payload), capture_output=True,
                       text=True, env=env, timeout=20)
    return r.returncode, r.stderr.strip()


def bash(c, **kw):
    return run("Bash", {"command": c}, **kw)


# Commands taken from the procedure (code blocks plus inline backticked commands), with placeholders filled.
blocks = re.findall(r"```sh\n(.*?)```", proc, re.S)
procedure_cmds = []
for b in blocks:
    procedure_cmds += [l.strip() for l in b.strip().splitlines() if l.strip()]
procedure_cmds = [c for c in procedure_cmds if not c.startswith(("python3 -c \"s=[P1",))]
procedure_cmds += [
    "git status --porcelain --ignored", "date +%F", "git remote get-url origin",
    "git symbolic-ref refs/remotes/origin/HEAD", "git rev-parse HEAD",
    "git log --since=90.days --format='%an' | sort -u | wc -l",
    "gh repo view --json nameWithOwner,defaultBranchRef,visibility",
    "gh api repos/{owner}/{repo}/branches/main/protection",
    "gh pr list --state merged --limit 10 --json number,reviews,author",
    "gitleaks git --redact --no-banner -v .",
    "trufflehog git file://. --no-update --json | grep -oE '\"(file|commit|line)\":[^,]*'",
    "git show HEAD:AGENTS.md | head -50", "git config --get core.hooksPath",
    "python3 -c \"s=[3,2,'N/A',1,1,2,3,2,1,1,2]; print(len(s))\"",
    "python3 -c \"print(round((4-2)*0.20,2))\"",
    "cd " + str(repo) + " && git ls-files | wc -l", "rm -f ai-audit/_notes.md", "mkdir -p ai-audit",
    "cat .env.example", "ls -la .claude 2>/dev/null", "grep -rn 'x' . 2>&1 | head -5", "command -v gh",
    "find . -name '*.md' -not -path './node_modules/*' | head",
]
# The two scoring commands, with their placeholders filled in.
rubric_cmd = re.search(r'(python3 -c "s=\[P1.*?")\n', proc).group(1)
for i, v in enumerate([3, 2, "'N/A'", 1, 1, 2, 3, 2, 1, 1, 2], 1):
    rubric_cmd = re.sub(rf"\bP{i}\b(?=[,\]])", str(v), rubric_cmd, count=1)
qscore = (root / "skills/ai-workflow-audit/references/questionnaire-scoring.md").read_text()
q_cmd = re.search(r'(python3 -c "ev=.*?")\n', qscore).group(1)
for k, v in {"G9": "3", "G10": "2", "G11": "0", "pe=PE": "pe=3", "'M'": "'e'", "'QUIZ'": "'bdacdb'", "x=X": "x=1"}.items():
    q_cmd = q_cmd.replace(k, v)
procedure_cmds += [rubric_cmd, q_cmd]
fill = {"<line>": "12", "<file>": "AGENTS.md", "<path>": "AGENTS.md", "<same combined pattern as Section 4.1>": "AKIA",
        "<same combined pattern as above>": "AKIA"}
ALLOW = []
for c in procedure_cmds:
    for k, v in fill.items():
        c = c.replace(k, v)
    ALLOW.append(("Bash", {"command": c}))
ALLOW += [
    ("Write", {"file_path": str(repo / "ai-audit/myrepo-2026-10-14.md")}),
    ("Write", {"file_path": str(repo / "ai-audit/myrepo-2026-10-14.md")}),  # rewrite own report (redaction)
    ("Write", {"file_path": "ai-audit/myrepo-2026-10-14-2.md"}),
    ("Write", {"file_path": str(repo / "ai-audit/_notes.md")}),
    ("Read", {"file_path": str(repo / "AGENTS.md")}),
    ("Read", {"file_path": str(root / "skills/ai-workflow-audit/references/questionnaire-scoring.md")}),
    ("Grep", {"pattern": "TODO", "path": str(repo)}),
    ("Glob", {"pattern": "**/*.md"}),
]

DENY = [
    # G1 no fixing / G8 output only to ai-audit
    ("Write", {"file_path": str(repo / "AGENTS.md")}), ("Write", {"file_path": str(repo / ".claude/settings.json")}),
    ("Write", {"file_path": str(repo / "ai-audit/questionnaire-myrepo-2026-10-14.md")}),
    ("Write", {"file_path": str(repo / "ai-audit/old-repo-2026-01-01.md")}),  # earlier report: no overwrite
    ("Write", {"file_path": "/tmp/report.md"}), ("Edit", {"file_path": str(repo / "AGENTS.md")}),
    ("MultiEdit", {"file_path": str(repo / "AGENTS.md")}), ("NotebookEdit", {"notebook_path": "x.ipynb"}),
    ("Bash", {"command": "echo '# rules' > AGENTS.md"}), ("Bash", {"command": "echo x >> CLAUDE.md"}),
    ("Bash", {"command": "tee AGENTS.md < /dev/null"}), ("Bash", {"command": "sed -i 's/a/b/' AGENTS.md"}),
    ("Bash", {"command": "sed -n 'w out.txt' AGENTS.md"}), ("Bash", {"command": "touch .cursorrules"}),
    ("Bash", {"command": "cp AGENTS.md CLAUDE.md"}), ("Bash", {"command": "mv a b"}), ("Bash", {"command": "rm -rf .claude"}),
    ("Bash", {"command": "rm ai-audit/old-repo-2026-01-01.md"}), ("Bash", {"command": "mkdir .claude"}),
    ("Bash", {"command": "find . -name '*.tmp' -delete"}), ("Bash", {"command": "find . -exec rm {} \\;"}),
    ("Bash", {"command": "cat <<EOF > AGENTS.md\nx\nEOF"}), ("Bash", {"command": "python3 -c \"open('AGENTS.md','w').write('x')\""}),
    ("Bash", {"command": "python3 fix.py"}), ("Bash", {"command": "node -e \"require('fs').writeFileSync('a','b')\""}),
    ("Bash", {"command": "perl -pi -e 's/a/b/' AGENTS.md"}), ("Bash", {"command": "awk '{print > \"out\"}' f"}),
    ("Bash", {"command": "sort -o out.txt f"}),
    # G6 read-only: no execution, installs, git writes, network, mutating host calls
    ("Bash", {"command": "npm test"}), ("Bash", {"command": "npx jest"}), ("Bash", {"command": "pip install x"}),
    ("Bash", {"command": "make build"}), ("Bash", {"command": "./gradlew test"}), ("Bash", {"command": "bash -c 'ls'"}),
    ("Bash", {"command": "sh scripts/deploy.sh"}), ("Bash", {"command": "eval ls"}), ("Bash", {"command": "xargs rm < list"}),
    ("Bash", {"command": "git add ai-audit/x.md"}), ("Bash", {"command": "git commit -m report"}), ("Bash", {"command": "git push"}),
    ("Bash", {"command": "git checkout -b fix"}), ("Bash", {"command": "git stash"}), ("Bash", {"command": "git fetch"}),
    ("Bash", {"command": "git pull"}), ("Bash", {"command": "git reset --hard"}), ("Bash", {"command": "git branch -D main"}),
    ("Bash", {"command": "git tag v1"}), ("Bash", {"command": "git config user.name x"}), ("Bash", {"command": "git -c core.pager=sh log"}),
    ("Bash", {"command": "git diff --output=x.txt"}), ("Bash", {"command": "git remote add x y"}),
    ("Bash", {"command": "gh pr create --title x"}), ("Bash", {"command": "gh issue create -t x"}), ("Bash", {"command": "gh pr comment 1 -b x"}),
    ("Bash", {"command": "gh api -X POST repos/o/r/issues"}), ("Bash", {"command": "gh api repos/o/r/issues -f title=x"}),
    ("Bash", {"command": "gh api graphql -f query='mutation{}'"}), ("Bash", {"command": "gh workflow run ci.yml"}),
    ("Bash", {"command": "gh secret set X"}), ("Bash", {"command": "glab mr create"}), ("Bash", {"command": "az repos policy create"}),
    ("Bash", {"command": "curl https://example.com"}), ("Bash", {"command": "wget x"}), ("Bash", {"command": "ssh host"}),
    ("Bash", {"command": "gitleaks git -v ."}), ("Bash", {"command": "echo $(whoami)"}), ("Bash", {"command": "echo `id`"}),
    ("Bash", {"command": "PATH=/tmp/x git status"}), ("Bash", {"command": "GIT_PAGER=sh git log"}), ("Bash", {"command": "$CMD"}),
    ("Bash", {"command": "/bin/rm x"}),
    # G5 secrets: no plain reads of secret files
    ("Bash", {"command": "cat .env"}), ("Bash", {"command": "head -5 config/.env.local"}), ("Bash", {"command": "tail id_rsa"}),
    ("Read", {"file_path": str(repo / ".env")}), ("Read", {"file_path": str(repo / "certs/server.pem")}),
    # G7 repository only
    ("Bash", {"command": "cat ~/.claude.json"}), ("Bash", {"command": "ls $HOME/.codex"}), ("Bash", {"command": "cat /etc/passwd"}),
    ("Bash", {"command": "ls ../other-repo"}), ("Bash", {"command": "cd /tmp && ls"}), ("Read", {"file_path": os.path.expanduser("~/.claude.json")}),
    ("Read", {"file_path": "/etc/hosts"}), ("Grep", {"pattern": "x", "path": os.path.expanduser("~")}),
    ("Glob", {"pattern": "/Users/**/*.json"}),
]

failures = []
for tool, ti in ALLOW:
    code, err = run(tool, ti)
    if code != 0:
        failures.append(f"should ALLOW {tool} {ti}: {err}")
for tool, ti in DENY:
    code, err = run(tool, ti)
    if code != 2 or "Blocked by ai-workflow-audit guard" not in err:
        failures.append(f"should DENY {tool} {ti} (exit {code})")
for tool, ti in DENY[:10]:  # other agents and the main session are never affected
    for agent in (None, "Explore", "general-purpose"):
        code, _ = run(tool, ti, agent=agent)
        if code != 0:
            failures.append(f"should PASS THROUGH for agent {agent}: {tool} {ti}")
(repo / "ai-audit/myrepo-2026-10-14.md").write_text("report from run a1\n")
code, _ = run("Write", {"file_path": str(repo / "ai-audit/myrepo-2026-10-14.md")}, agent_id="a2")
if code != 2:
    failures.append("a second run must not overwrite the first run's report")

# ---------------------------------------------------------------- project mode
proj = pathlib.Path(tempfile.mkdtemp(prefix="guard-project-"))
repo_a, repo_b = proj / "orders-api", proj / "services" / "billing"
for r in (repo_a, repo_b):
    subprocess.run(["git", "init", "-q", str(r)], check=True)
(proj / "ai-audit").mkdir()
manifest = proj / "ai-audit/_project.json"


def set_manifest(**kw):
    data = {"project": "larkspur", "date": "2026-10-15", "repos": [str(repo_a), str(repo_b)],
            "answers": str(proj / "ai-audit/questionnaire-larkspur-2026-10-15.md"), "current": str(repo_a), "done": {}}
    data.update(kw)
    manifest.write_text(json.dumps(data))


set_manifest()
P_ALLOW = [("Bash", {"command": f"cd {repo_a} && {ti['command']}"}) for tool, ti in ALLOW
           if tool == "Bash" and not ti["command"].startswith("cd ")] + [
    ("Bash", {"command": "cd orders-api && git log --oneline | head"}),
    ("Write", {"file_path": str(repo_a / "ai-audit/orders-api-2026-10-15.md")}),
    ("Write", {"file_path": str(repo_a / "ai-audit/_notes.md")}),
    ("Read", {"file_path": str(repo_a / "AGENTS.md")}),
    ("Read", {"file_path": str(repo_a / "ai-audit/questionnaire-orders-api-2026-10-15.md")}),
    ("Read", {"file_path": str(root / "skills/ai-workflow-audit/references/audit-procedure.md")}),
    ("Grep", {"pattern": "TODO", "path": str(repo_a)}),
    ("Glob", {"pattern": "**/*.md", "path": str(repo_a)}),
]
P_DENY = [
    ("Bash", {"command": "git status"}), ("Bash", {"command": "cat services/billing/AGENTS.md"}),
    ("Bash", {"command": "ls"}), ("Bash", {"command": f"cd {repo_b} && ls"}),
    ("Bash", {"command": f"cd {repo_a} && cat ../services/billing/AGENTS.md"}),
    ("Bash", {"command": f"cd {repo_a} && cd .. && ls"}), ("Bash", {"command": f"cd {proj} && ls"}),
    ("Bash", {"command": f"cd {repo_a} && git -C {repo_b} log"}), ("Bash", {"command": f"cd {repo_a} && echo x > AGENTS.md"}),
    ("Read", {"file_path": str(repo_b / "AGENTS.md")}), ("Read", {"file_path": str(manifest)}),
    ("Grep", {"pattern": "x"}), ("Glob", {"pattern": "**/*.md"}), ("Grep", {"pattern": "x", "path": str(proj)}),
    ("Write", {"file_path": str(manifest)}),
    ("Write", {"file_path": str(proj / "ai-audit/larkspur-consolidated-2026-10-15.md")}),
    ("Write", {"file_path": str(repo_b / "ai-audit/billing-2026-10-15.md")}),
    ("Write", {"file_path": "ai-audit/orders-api-2026-10-15.md"}),  # relative: resolves to the project folder
    ("Write", {"file_path": str(repo_a / "AGENTS.md")}), ("Edit", {"file_path": str(repo_a / "AGENTS.md")}),
]
for tool, ti in P_ALLOW:
    code, err = run(tool, ti, agent_id="p1", cwd=proj)
    if code != 0:
        failures.append(f"project mode should ALLOW {tool} {ti}: {err}")
for tool, ti in P_DENY:
    code, err = run(tool, ti, agent_id="p1", cwd=proj)
    if code != 2 or "Blocked by ai-workflow-audit guard" not in err:
        failures.append(f"project mode should DENY {tool} {ti} (exit {code})")
for tool, ti in P_DENY[:5]:  # the main session (which writes the manifest and the consolidated report) is never affected
    code, _ = run(tool, ti, agent=None, cwd=proj)
    if code != 0:
        failures.append(f"project mode should PASS THROUGH for the main session: {tool} {ti}")
# After the skill moves on, the second repo is the only one reachable.
set_manifest(current=str(repo_b))
for tool, ti, want in [("Read", {"file_path": str(repo_b / "AGENTS.md")}, 0), ("Read", {"file_path": str(repo_a / "AGENTS.md")}, 2),
                       ("Write", {"file_path": str(repo_b / "ai-audit/billing-2026-10-15.md")}, 0)]:
    if run(tool, ti, agent_id="p2", cwd=proj)[0] != want:
        failures.append(f"project mode, current=billing: {tool} {ti} should exit {want}")
# Bad manifests and a multi-repo folder without one fail closed.
outside = pathlib.Path(tempfile.mkdtemp(prefix="guard-outside-"))
subprocess.run(["git", "init", "-q", str(outside)], check=True)
bad = [dict(current=str(outside)), dict(current=str(outside), repos=[str(outside)]), dict(current=None),
       dict(current=str(proj)), dict(current=str(repo_a), repos=[str(repo_b)])]
for kw in bad:
    set_manifest(**kw)
    if run("Read", {"file_path": str(repo_a / "AGENTS.md")}, agent_id="p3", cwd=proj)[0] != 2:
        failures.append(f"project mode with a bad manifest {kw} must block")
manifest.write_text("{not json")
if run("Read", {"file_path": str(repo_a / "AGENTS.md")}, agent_id="p3", cwd=proj)[0] != 2:
    failures.append("project mode with an unreadable manifest must block")
manifest.unlink()
if run("Read", {"file_path": str(repo_a / "AGENTS.md")}, agent_id="p3", cwd=proj)[0] != 2:
    failures.append("a folder holding several repos without a manifest must block the audit agent")
plain = pathlib.Path(tempfile.mkdtemp(prefix="guard-plain-"))  # no git, no child repos: unchanged behaviour
if run("Write", {"file_path": str(plain / "ai-audit/plain-2026-10-15.md")}, agent_id="p4", cwd=plain)[0] != 0:
    failures.append("a plain folder without repositories keeps the single-folder behaviour")

total = len(ALLOW) + len(DENY) + 31 + len(P_ALLOW) + len(P_DENY) + 5 + 3 + len(bad) + 3
if failures:
    print(f"{len(failures)} of {total} guard checks failed:\n- " + "\n- ".join(failures)); sys.exit(1)
print(f"Guard checks passed ({len(ALLOW)} allowed, {len(DENY)} blocked, pass-through and no-overwrite verified; "
      f"project mode: {len(P_ALLOW)} allowed, {len(P_DENY)} blocked, {len(bad) + 2} bad-manifest cases).")
