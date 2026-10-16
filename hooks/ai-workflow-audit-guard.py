#!/usr/bin/env python3
"""PreToolUse guard for the ai-workflow-audit plugin (Claude Code).

Plugin hooks run for every tool call in the session, so this script does nothing
(exit 0) unless the call comes from the plugin's own `ai-workflow-audit` subagent.
For that subagent it enforces the audit's guardrails mechanically:

- Write only the report (`ai-audit/<repo>-<date>[-n].md`) and `ai-audit/_notes.md`,
  never over a file that existed before this agent first wrote it.
- No Edit, MultiEdit or NotebookEdit.
- Read, Grep and Glob stay inside the repository (or the plugin's own files),
  and plain reads of secret files (.env, keys, credentials) are blocked.
- Bash runs only an allowlist of read-only commands, with no file redirection,
  command substitution, git writes, mutating host-CLI calls or network tools.
- Project mode (the session runs in a folder that holds several repos): the skill's
  manifest `ai-audit/_project.json` names the one repo being audited now, and that repo
  is the only one the agent may touch. Every Bash command must start with `cd` into it,
  and Grep/Glob need an explicit path inside it.

A blocked call exits 2 with the reason on stderr, which Claude Code shows to the agent.
Standard library only. Test: python3 scripts/test_guard.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

AGENT_NAMES = {"ai-workflow-audit", "ai-workflow-audit:ai-workflow-audit"}


class Deny(Exception):
    pass


def deny(reason):
    raise Deny(reason)


# ---------------------------------------------------------------- paths

def git_toplevel(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return os.path.realpath(out.stdout.strip())
    except Exception:
        pass
    return None


MANIFEST = os.path.join("ai-audit", "_project.json")
SKIP_DIRS = {"node_modules", "vendor", "dist", "build", "out", "target", ".venv", "venv", "Pods"}


def child_repos(cwd, depth=2):
    """True if a git repository sits up to `depth` levels below cwd."""
    try:
        entries = [e for e in os.scandir(cwd) if e.is_dir(follow_symlinks=False)
                   and e.name not in SKIP_DIRS and not e.name.startswith(".")]
    except OSError:
        return False
    for e in entries:
        if os.path.exists(os.path.join(e.path, ".git")) or (depth > 1 and child_repos(e.path, depth - 1)):
            return True
    return False


def audit_root(cwd):
    """(root, project_mode). Inside a git repo the root is that repo. In a folder that is not a
    repo but has the skill's project manifest, the root is the manifest's `current` repo, which
    must be one of its confirmed repos and a git repo inside this folder."""
    top = git_toplevel(cwd)
    if top:
        return top, False
    man = os.path.join(cwd, MANIFEST)
    if not os.path.isfile(man):
        if child_repos(cwd):
            deny("this folder holds several repositories but has no project manifest; "
                 "the skill must confirm the repositories (project mode) before the audit")
        return os.path.realpath(cwd), False
    try:
        with open(man) as f:
            data = json.load(f)
        cur = os.path.realpath(os.path.join(cwd, data["current"]))
        repos = {os.path.realpath(os.path.join(cwd, r)) for r in data["repos"]}
    except Exception:
        deny("the project manifest ai-audit/_project.json is unreadable or names no current repository")
    if cur not in repos or cur == cwd or not inside(cur, cwd) or git_toplevel(cur) != cur:
        deny("the project manifest's current repository is not a confirmed git repository inside the project folder")
    return cur, True


def plugin_root():
    return os.path.realpath(os.environ.get("CLAUDE_PLUGIN_ROOT")
                            or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inside(path, base):
    return path == base or path.startswith(base.rstrip(os.sep) + os.sep)


def resolve(p, cwd):
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(p)))


SECRET_FILE = re.compile(
    r"(^|/)(\.env(\.(?!example$|sample$|template$)[^/]*)?|[^/]*\.(pem|key|p12|pfx|keystore|jks)"
    r"|id_(rsa|dsa|ecdsa|ed25519)|credentials(\.json)?|secrets?\.(json|ya?ml)|\.npmrc|\.netrc|\.pypirc)$",
    re.I)


def check_path(p, ctx, cwd=None):
    if p.startswith("~") or "$HOME" in p or "${HOME" in p:
        deny(f"'{p}' is outside the repository (the audit reads this repository only)")
    if p in ("/dev/null", "/dev/stdin", "/dev/stdout", "/dev/stderr"):
        return
    full = resolve(p, cwd or ctx["root"])
    if not (inside(full, ctx["root"]) or inside(full, ctx["plugin"])):
        deny(f"'{p}' is outside the repository (the audit reads this repository only)")


# ---------------------------------------------------------------- Write / Read tools

REPORT_RE = re.compile(r"^ai-audit/(?!questionnaire-)[a-z0-9][a-z0-9-]*-\d{4}-\d{2}-\d{2}(-\d+)?\.md$")
NOTES = "ai-audit/_notes.md"


def state_file(data):
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(tempfile.gettempdir(), "ai-workflow-audit-guard")
    key = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("agent_id") or data.get("session_id") or "unknown"))
    return os.path.join(base, f"guard-{key}.json")


def check_write(path, data, ctx):
    full = resolve(path, ctx["cwd"])
    if not inside(full, ctx["root"]):
        deny("the audit writes only its report under ai-audit/ in this repository")
    rel = os.path.relpath(full, ctx["root"]).replace(os.sep, "/")
    if rel != NOTES and not REPORT_RE.match(rel):
        deny(f"'{rel}' is not the audit report: the audit never creates or edits other files, "
             "including the AI setup it assesses")
    if os.path.islink(full):
        deny(f"'{rel}' is a symlink")
    sf = state_file(data)
    try:
        with open(sf) as f:
            mine = set(json.load(f))
    except Exception:
        mine = set()
    if os.path.exists(full) and rel != NOTES and full not in mine:
        deny(f"'{rel}' already exists and was not written by this run; "
             "use the next free suffix (-2, -3, …) instead of overwriting an earlier report")
    mine.add(full)
    os.makedirs(os.path.dirname(sf), exist_ok=True)
    with open(sf, "w") as f:
        json.dump(sorted(mine), f)


def check_read_tool(name, ti, ctx):
    for key in ("file_path", "path", "notebook_path"):
        p = ti.get(key)
        if p:
            check_path(p, ctx, ctx["cwd"])
            if name == "Read" and SECRET_FILE.search(p):
                deny(f"'{p}' is a secret file: report it by path only, and read it only through "
                     "the procedure's masked commands")
    if ctx["project"] and name in ("Grep", "Glob") and not ti.get("path"):
        deny(f"in project mode, give {name} an absolute path inside the repository being audited")
    pat = ti.get("pattern") if name == "Glob" else None
    if pat and (pat.startswith(("/", "~")) or "$HOME" in pat):
        check_path(pat.split("*")[0] or "/", ctx, ctx["cwd"])


# ---------------------------------------------------------------- Bash

def scan(cmd):
    """Replace quoted strings with \\x00<n>\\x00 placeholders. Returns (skeleton, quoted)."""
    out, quoted, i, n = [], [], 0, len(cmd)
    while i < n:
        c = cmd[i]
        if c == "\\" and i + 1 < n:
            out.append(cmd[i:i + 2]); i += 2; continue
        if c == "'":
            j = cmd.find("'", i + 1)
            if j < 0:
                deny("unbalanced quote")
            quoted.append(cmd[i + 1:j]); out.append(f"\x00{len(quoted) - 1}\x00"); i = j + 1; continue
        if c == '"':
            j, buf = i + 1, []
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n:
                    buf.append(cmd[j:j + 2]); j += 2; continue
                buf.append(cmd[j]); j += 1
            if j >= n:
                deny("unbalanced quote")
            s = "".join(buf)
            if "$(" in s or "`" in s:
                deny("command substitution is not allowed")
            quoted.append(s); out.append(f"\x00{len(quoted) - 1}\x00"); i = j + 1; continue
        out.append(c); i += 1
    return "".join(out), quoted


PH = re.compile(r"\x00(\d+)\x00")

READ_ONLY = {
    "ls", "find", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "git", "sed", "awk", "cut",
    "sort", "uniq", "tr", "date", "python3", "python", "node", "perl", "echo", "printf", "test", "[",
    "[[", "true", "false", "stat", "file", "basename", "dirname", "realpath", "readlink", "du", "jq",
    "gh", "glab", "az", "gitleaks", "trufflehog", "cd", "pwd", "rm", "mkdir", "column", "nl", "comm",
    "diff", "which", "type", "command", "exit", "read", "less", "more",
}
GIT_OK = {
    "status", "log", "show", "grep", "ls-files", "ls-tree", "rev-parse", "branch", "symbolic-ref",
    "remote", "config", "diff", "shortlog", "cat-file", "rev-list", "describe", "blame",
    "check-ignore", "for-each-ref", "tag", "count-objects", "name-rev", "whatchanged", "help",
}
RAW_READERS = {"cat", "head", "tail", "less", "more"}
SKIP_WORDS = {"!", "{", "}", "then", "do", "else", "elif", "if", "while", "until", "time"}
HEADER_WORDS = {"for", "case", "select", "done", "fi", "esac", "in"}
RISKY_VAR = re.compile(r"^(PATH|IFS|ENV|BASH_ENV|PAGER|EDITOR|VISUAL|SHELL|HOME|PROMPT_COMMAND|NODE_OPTIONS|"
                       r"GIT_\w*|LD_\w*|DYLD_\w*|PYTHON\w*|PERL\w*|GH_\w*|GLAB_\w*)=")


def check_bash(cmd, ctx):
    skel, quoted = scan(cmd)
    if "`" in skel or "$(" in skel or "<(" in skel or ">(" in skel:
        deny("command or process substitution is not allowed")
    if "<<" in skel:
        deny("here-documents are not allowed")
    rest = re.sub(r"\d?>&\d|&>\s*/dev/null|\d?>>?\s*/dev/null", " ", skel)
    if ">" in rest:
        deny("output redirection to a file is not allowed: the audit writes only its report, with the Write tool")
    for q in quoted:
        if "$HOME" in q or "${HOME" in q:
            deny("'$HOME' is outside the repository")
    cwd = ctx["cwd"] if ctx["project"] else ctx["root"]
    first = True
    for seg in re.split(r"\|\||&&|[;|&\n()]", rest):
        toks = seg.split()
        while toks and toks[0] in SKIP_WORDS:
            toks = toks[1:]
        if not toks or toks[0] in HEADER_WORDS or toks[0] == ";;":
            continue
        while toks and re.match(r"^[A-Za-z_]\w*=", toks[0]):
            if RISKY_VAR.match(toks[0]):
                deny(f"setting {toks[0].split('=')[0]} could make an allowed command run something else")
            toks = toks[1:]
        if not toks:
            continue
        name, args = toks[0], toks[1:]
        if first and ctx["project"]:
            target = PH.sub(lambda m: quoted[int(m.group(1))], args[0]) if name == "cd" and args else ""
            if not target or not inside(resolve(target, cwd), ctx["root"]):
                deny("in project mode, start every command with 'cd <repository root> &&' "
                     "(the shell starts in the project folder, which holds other repositories)")
        first = False
        if "\x00" in name or name.startswith("$"):
            deny("running a command from a variable or a quoted string is not allowed")
        if "/" in name:
            deny(f"run commands by name, not by path ('{name}')")
        if name not in READ_ONLY:
            deny(f"'{name}' is not an allowed read-only command in this audit")
        vals = [PH.sub(lambda m: quoted[int(m.group(1))], a) for a in args]
        for a in vals:
            for p in ([a.split("=", 1)[1]] if a.startswith("--") and "=" in a else [a]):
                if p.startswith(("/", "~")) or "../" in p or p == ".." or "$HOME" in p or "${HOME" in p:
                    check_path(p, ctx, cwd)
        check_command(name, args, vals, ctx)
        if name == "cd" and vals:
            cwd = resolve(vals[0], cwd)


def check_command(name, args, vals, ctx):
    flags = [v for v in vals if v.startswith("-")]
    if name in RAW_READERS:
        for v in vals:
            if not v.startswith("-") and SECRET_FILE.search(v):
                deny(f"'{v}' is a secret file: read it only through the procedure's masked commands")
    elif name == "find":
        bad = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
        if bad & set(vals):
            deny("find may only list files (no -delete, -exec or -fprint)")
    elif name == "sed":
        if any(f in ("-i", "--in-place") or f.startswith(("-i", "--in-place")) for f in flags):
            deny("sed -i edits files")
        if any(f in ("-f", "--file") or f.startswith("--file") for f in flags):
            deny("sed may not run a script file")
        scripts = [vals[i + 1] for i, v in enumerate(vals[:-1]) if v in ("-e", "--expression")]
        if not scripts:
            scripts = [v for v in vals if not v.startswith("-")][:1]
        for v in scripts:
            if re.search(r"(^|[;{\n])\s*[wWe]\b|[/|#][gpiIme0-9]*w\s", v):
                deny("sed scripts may not write or execute (w / e commands)")
    elif name == "awk":
        for v in vals:
            if re.search(r"system\s*\(|getline|\|&|print[f]?\b[^;}]*[>|]", v):
                deny("awk programs may not run commands or write files")
    elif name == "perl":
        if any(f.startswith("-i") or ("i" in f[1:] and not f.startswith("--")) for f in flags):
            deny("perl -i edits files")
        for v in vals:
            if re.search(r"\b(system|exec|open|unlink|rename|qx|require|use|eval)\b|`", v):
                deny("perl may only filter text (no system, exec, open or modules)")
    elif name in ("python3", "python"):
        if not args or args[0] != "-c" or len(vals) < 2:
            deny("python3 may only run a short calculation with -c")
        if re.search(r"import|open\s*\(|__|\bexec\b|\beval\b|compile|\bos\.|\bsys\.|subprocess|globals|getattr|input\s*\(", vals[1]):
            deny("python3 -c may only compute numbers (no imports, files or system calls)")
    elif name == "node":
        if not args or args[0] not in ("-e", "-p") or len(vals) < 2:
            deny("node may only run a short calculation with -e")
        if re.search(r"require|import|process|\bfs\b|child_process|eval|Function|global", vals[1]):
            deny("node -e may only compute numbers")
    elif name == "git":
        check_git(vals)
    elif name in ("gh", "glab"):
        check_host_cli(name, vals)
    elif name == "az":
        verbs = []
        for v in vals:
            if v.startswith("-"):
                break
            verbs.append(v)
        if not verbs or verbs[-1] not in ("list", "show") or "invoke" in verbs:
            deny("az may only run read-only 'list' or 'show' commands")
    elif name == "gitleaks":
        if "--redact" not in vals:
            deny("gitleaks must run with --redact")
        if any(f in ("-r", "--report-path") or f.startswith("--report-path") for f in flags):
            deny("gitleaks may not write a report file")
    elif name == "trufflehog":
        if any(f.startswith(("--webhook", "--output")) for f in flags):
            deny("trufflehog may not send or write results")
    elif name == "rm":
        targets = [v for v in vals if not v.startswith("-")]
        if set(flags) - {"-f"} or not targets or any(
                os.path.relpath(resolve(t, ctx["root"]), ctx["root"]).replace(os.sep, "/") != NOTES for t in targets):
            deny("rm may only delete the audit's own ai-audit/_notes.md")
    elif name == "mkdir":
        targets = [v for v in vals if not v.startswith("-")]
        if set(flags) - {"-p"} or [t.rstrip("/") for t in targets] != ["ai-audit"]:
            deny("mkdir may only create ai-audit/")
    elif name == "date":
        if any(f in ("-s", "--set") or f.startswith("--set") for f in flags):
            deny("date may not set the clock")
    elif name == "sort":
        if any(f == "-o" or f.startswith(("-o", "--output")) for f in flags):
            deny("sort may not write files")
    elif name == "command":
        if not vals or vals[0] not in ("-v", "-V"):
            deny("command may only be used as 'command -v'")


def check_git(vals):
    i = 0
    while i < len(vals) and vals[i].startswith("-"):
        if vals[i] in ("-c", "--config-env") or vals[i].startswith(("-c", "--exec-path", "--config-env")):
            deny("git -c can run commands through config; it is not allowed")
        if vals[i] in ("-C", "--git-dir", "--work-tree"):
            i += 1
        i += 1
    if i >= len(vals):
        return
    sub, rest = vals[i], vals[i + 1:]
    if sub not in GIT_OK:
        deny(f"'git {sub}' is not read-only; the audit uses local git data only and never changes the repository")
    if any(r.startswith(("--output", "-O", "--open-files-in-pager", "--ext-diff", "--textconv")) for r in rest):
        deny(f"'git {sub}' with that option can write files or run programs")
    if sub == "branch" and any(r in ("-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move", "--copy",
                                     "--set-upstream-to", "-u", "--unset-upstream", "--edit-description", "-f", "--force")
                               or r.startswith(("--set-upstream", "--delete", "--move", "--copy")) for r in rest):
        deny("git branch may only list branches")
    if sub == "tag" and rest and not any(r in ("-l", "--list", "-n", "--contains", "--points-at") or r.startswith(("--list", "-n", "--sort", "--format", "--merged", "--no-merged")) for r in rest):
        deny("git tag may only list tags")
    if sub == "config" and not any(r in ("--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin", "--name-only") for r in rest):
        deny("git config may only read values (--get, --list)")
    if sub == "remote" and rest and rest[0] not in ("get-url", "-v", "--verbose"):
        deny("git remote may only show remote URLs")


HOST_READ = {
    "gh": {"api", "repo", "pr", "run", "workflow", "auth", "ruleset", "release", "issue", "secret", "variable", "search", "status"},
    "glab": {"api", "repo", "mr", "ci", "auth", "release", "issue", "variable"},
}
HOST_VERBS_OK = {"view", "list", "status", "checks", "diff", "ls"}


def check_host_cli(name, vals):
    words = [v for v in vals if not v.startswith("-")]
    if not words or words[0] not in HOST_READ[name]:
        deny(f"'{name} {words[0] if words else ''}' is not a read-only call")
    if words[0] == "api":
        if len(words) > 1 and words[1] == "graphql":
            deny(f"'{name} api graphql' is not allowed; use REST GET calls")
        for i, v in enumerate(vals):
            if v in ("-X", "--method") and i + 1 < len(vals) and vals[i + 1].upper() != "GET":
                deny(f"'{name} api' may only send GET requests")
            if v.startswith(("--method=", "-X")) and len(v) > 2 and not v.upper().endswith("GET"):
                deny(f"'{name} api' may only send GET requests")
            if v in ("-f", "-F", "--field", "--raw-field", "--input") or v.startswith(("--field=", "--raw-field=", "--input=")):
                deny(f"'{name} api' may not send fields or a request body")
        return
    if words[0] in ("auth", "status", "search"):
        if words[0] == "auth" and (len(words) < 2 or words[1] != "status"):
            deny(f"'{name} auth' may only check 'status'")
        return
    if len(words) < 2 or words[1] not in HOST_VERBS_OK:
        deny(f"'{name} {' '.join(words[:2])}' is not read-only (only view, list, status, checks, diff)")


# ---------------------------------------------------------------- main

def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        if re.search(r'"agent_type"\s*:\s*"(ai-workflow-audit:)?ai-workflow-audit"', raw):
            print("Blocked by ai-workflow-audit guard: unreadable hook input.", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if data.get("agent_type") not in AGENT_NAMES:
        sys.exit(0)  # not the audit subagent: never interfere with the user's session
    try:
        name, ti = data.get("tool_name", ""), data.get("tool_input") or {}
        cwd = os.path.realpath(data.get("cwd") or os.getcwd())
        root, project = audit_root(cwd)
        ctx = {"cwd": cwd, "root": root, "project": project, "plugin": plugin_root()}
        if name in ("Edit", "MultiEdit", "NotebookEdit"):
            deny("the audit never edits files, including the AI setup it assesses")
        elif name == "Write":
            check_write(ti.get("file_path", ""), data, ctx)
        elif name in ("Read", "Grep", "Glob"):
            check_read_tool(name, ti, ctx)
        elif name == "Bash":
            check_bash(ti.get("command", ""), ctx)
    except Deny as e:
        print(f"Blocked by ai-workflow-audit guard: {e}. Use a read-only alternative, or mark the sub-check Unknown.",
              file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # fail closed for the audit agent
        print(f"Blocked by ai-workflow-audit guard: internal error ({type(e).__name__}).", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
