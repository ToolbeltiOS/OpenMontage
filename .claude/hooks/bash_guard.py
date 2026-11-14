#!/usr/bin/env python3
"""Check EVERY command in a Bash call against the deny list, not the first.

WHY THIS EXISTS
---------------
`permissions.deny` matches a prefix of the command string. On 2026-11-08 a
push to a new repository went through as

    cd /Users/mac/Developer/wak3up-docs/credits-site && git push -u origin main

with `Bash(git push:*)` sitting in the deny list, because the string starts
with `cd`. That is not a bug in the rule, it is what prefix matching is: the
same two characters disarm every entry in the list — `rm -rf`, `sudo`,
`git reset`, all of them — and so does `/usr/bin/git push`, `git -C dir
push`, `bash -c 'git push'`, and a command substitution.

So this hook parses the command instead. It splits on every operator a
shell would, looks inside `$(…)` and backticks, strips the wrappers that
hide a binary, and checks each segment on its own. The prefix rules stay in
settings.json as a first line; this is the one that has to be sound.

WHAT IT DENIES
--------------
  * everything in `permissions.deny`, per segment, with the binary's path
    stripped so `/usr/bin/git push` reads as `git push`
  * `bash -c`, `sh -c`, `zsh -c`, `eval`, `xargs`, `find -exec` — the
    wrappers whose whole purpose is to run a command this parser cannot see
  * git: `push`, `reset --hard`, `checkout -- .`, `clean -f`, `branch -D`,
    wherever git appears in the segment, including `git -C <dir>`
  * `rm` with recursion and force in any spelling of the flags
  * anything at all, if the hook cannot parse its own input — it fails
    closed, because a guard that cannot read the call cannot clear it

Exit 2 blocks the call and sends the message back to the model, the way an
Edit denial lands in the run log.

A FALSE DENIAL IS CHEAPER THAN A FALSE ALLOW, but only just: this runs in
front of every Bash call the pipeline makes, so the allowed side is tested
as hard as the denied side — see tests/automation/test_bash_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

SETTINGS = Path(__file__).resolve().parents[1] / "settings.json"

#: Wrappers that run another command. Stripped until a real binary appears,
#: because `nohup env FOO=1 /usr/bin/git push` is a push.
WRAPPERS = {"env", "nohup", "time", "command", "exec", "caffeinate",
            "stdbuf", "nice", "setsid", "timeout", "sudo_unused"}

#: Shell keywords that stand in FRONT of a command without being one.
#: Found 2026-11-14 while adding the inspection forms: `segments()` yields
#: the body of a loop as `do rm -rf /tmp/x`, `words_of` read the binary as
#: `do`, and every rule in this file missed it. `for i in 1; do git push;
#: done` cleared the guard for a week on that basis. They are stripped like
#: wrappers, so the real binary is what gets checked.
KEYWORDS = {"do", "then", "else", "elif", "!"}

SHELLS = {"bash", "sh", "zsh", "ksh", "dash", "fish"}

#: Run-a-string-for-me binaries. Denied outright: whatever they run is
#: invisible to this parser, which is the whole reason they are reached for.
OPAQUE = {"eval", "xargs"}

ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

#: git subcommands that are denied wherever git appears.
GIT_ALWAYS = {"push"}

OPERATORS = ("&&", "||", ";;", ";", "|&", "|", "&", "\n")


def _balanced(text: str, start: int, open_ch: str, close_ch: str
              ) -> tuple[str, int]:
    """The text inside a bracket that opened just before `start`."""
    depth, i, quote = 1, start, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"":
            quote = c
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return text[start:], len(text)


def segments(command: str) -> list[str]:
    """Every command in a shell line, including the ones inside `$(…)`."""
    out: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i, n = 0, len(command)

    def flush() -> None:
        if "".join(buf).strip():
            out.append("".join(buf).strip())
        buf.clear()

    while i < n:
        c = command[i]
        if quote:
            if c == "\\" and quote == '"' and i + 1 < n:
                buf.append(c)
                buf.append(command[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            buf.append(c)
            i += 1
            continue
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(command[i + 1])
            i += 2
            continue
        if command.startswith("$(", i):
            inner, j = _balanced(command, i + 2, "(", ")")
            out.extend(segments(inner))
            i = j
            continue
        if c == "`":
            j = command.find("`", i + 1)
            inner = command[i + 1:j if j != -1 else n]
            out.extend(segments(inner))
            i = (j + 1) if j != -1 else n
            continue
        if command.startswith("<(", i) or command.startswith(">(", i):
            inner, j = _balanced(command, i + 2, "(", ")")
            out.extend(segments(inner))
            i = j
            continue
        if c in "(){}":
            flush()
            i += 1
            continue
        matched = next((op for op in OPERATORS
                        if command.startswith(op, i)), None)
        if matched:
            flush()
            i += len(matched)
            continue
        buf.append(c)
        i += 1
    flush()
    return out


def words_of(segment: str) -> list[str]:
    try:
        words = shlex.split(segment)
    except ValueError:                      # an unbalanced quote
        words = segment.split()
    while words and ENV_ASSIGNMENT.match(words[0]):
        words.pop(0)
    # `do git push` is a push. Strip the keywords before the wrappers, and
    # keep stripping: `do nohup git push` is both.
    while words and words[0] in KEYWORDS:
        words.pop(0)
    # Unwrap `nohup env FOO=1 nice -n 5 /usr/bin/git push` down to git.
    while words and os.path.basename(words[0]) in WRAPPERS:
        words.pop(0)
        while words and (words[0].startswith("-")
                         or ENV_ASSIGNMENT.match(words[0])
                         or words[0].isdigit()):
            words.pop(0)
        while words and words[0] in KEYWORDS:
            words.pop(0)
    return words


def git_subcommand(words: list[str]) -> tuple[str, list[str]]:
    """git's own subcommand, past `-C dir`, `-c k=v` and the rest."""
    takes_value = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                   "--exec-path", "--super-prefix"}
    i = 1
    while i < len(words):
        word = words[i]
        if word in takes_value:
            i += 2
            continue
        if word.startswith("-"):
            i += 1
            continue
        return word, words[i + 1:]
    return "", []


def deny_patterns() -> list[str]:
    """The Bash prefixes in permissions.deny, as plain command text."""
    try:
        rules = json.loads(SETTINGS.read_text())["permissions"]["deny"]
    except Exception:                       # noqa: BLE001 - never block on this
        return []
    out = []
    for rule in rules:
        match = re.fullmatch(r"Bash\((.*?)(?::\*)?\)", rule)
        if match:
            out.append(match.group(1).strip())
    return out


def offence(segment: str, patterns: list[str]) -> str | None:
    """Why this one command is refused, or None."""
    words = words_of(segment)
    if not words:
        return None
    binary = os.path.basename(words[0])
    rest = words[1:]

    if binary in SHELLS and "-c" in rest:
        return (f"{binary} -c runs a command this guard cannot read. Run it "
                f"directly instead.")
    if binary in OPAQUE:
        return f"{binary} runs a command this guard cannot read."
    if binary == "find" and any(a in ("-exec", "-execdir", "-ok", "-okdir")
                                for a in rest):
        return "find -exec runs a command this guard cannot read."

    if binary == "git":
        sub, args = git_subcommand(words)
        if sub in GIT_ALWAYS:
            return f"git {sub} is denied wherever it appears."
        if sub == "reset" and "--hard" in args:
            return "git reset --hard discards work that is not recoverable."
        if sub == "checkout" and "--" in args:
            return "git checkout -- <path> discards uncommitted changes."
        if sub == "clean" and any(re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", a)
                                  for a in args):
            return "git clean -f deletes untracked files."
        if sub == "branch" and "-D" in args:
            return "git branch -D deletes a branch that may not be merged."

    if binary == "rm":
        flags = "".join(a[1:] for a in rest
                        if a.startswith("-") and not a.startswith("--"))
        long = set(rest)
        recursive = "r" in flags.lower() or {"--recursive"} & long
        forced = "f" in flags or {"--force"} & long
        if recursive and forced:
            return "rm with recursion and force is denied in any spelling."

    normalised = " ".join([binary] + rest)
    for pattern in patterns:
        if normalised == pattern or normalised.startswith(pattern + " "):
            return f"{pattern!r} is in permissions.deny."
    return None


# ── THE TWO INSPECTION FORMS ────────────────────────────────────────────
# Added 2026-11-14 after run #5. A non-interactive `claude -p` refuses
# anything `permissions.allow` does not match, and that matcher works on the
# FRONT of the command string, so it cannot see inside a `for` loop, past a
# `VAR=x &&` prefix, or through a `$(…)`. Six read-only inspections were
# refused across run #5's stages on that basis alone, and four of them were
# a stage trying to find out what it had been given:
#
#   P=projects/<slug> && ls -la $P/ && ls -la $P/artifacts/ …
#   ls projects/ && for p in projects/*/artifacts/scene_plan.json; do …
#   .venv/bin/python -I -c "…json.load(open('projects/king-tut/…'))…"
#
# The last one is the expensive one: the edit stage spent a turn trying to
# read a FINISHED film's edit_decisions.json to learn the shape of the
# artifact it was being asked to write, which is the cheapest orientation
# available to it, and was refused.
#
# So these two forms are recognised STRUCTURALLY and allowed by name. A hook
# that returns `allow` overrides the allow-list, so the recognisers run only
# after the whole deny pass above has cleared the command, and each one is
# written to say no when it is unsure:
#
#   FORM A  a `for` loop over paths under `projects/`, whose body runs only
#           read-only binaries and redirects nowhere but /dev/null
#   FORM B  `python -I -c <code>` where the code reads and does not write
#
# Neither form widens what the deny list refuses. What they widen is what a
# stage may LOOK at, and looking is the part we were charging it for.

#: Binaries that read and do not write. `python` is deliberately absent:
#: form B handles it, with the code itself audited.
READ_ONLY = frozenset({
    "echo", "printf", "ls", "cat", "head", "tail", "wc", "du", "stat",
    "file", "find", "grep", "egrep", "fgrep", "sort", "uniq", "cut", "tr",
    "basename", "dirname", "jq", "test", "[", "true", "false", "cd", "pwd",
    "date", "sha256sum", "md5", "shasum", "diff", "column", "nl", "seq",
})

#: `sed` and `awk` read, but `sed -i` writes in place and both can be handed
#: a script that writes. They are read-only ONLY in the plain spellings.
CONDITIONAL = {"sed": ("-i", "--in-place"), "awk": ("-i", "--in-place")}

#: Names that mean the python in form B is not a reader. `open` is checked
#: separately, by mode.
PY_WRITES = (
    "write", "unlink", "remove", "rmtree", "mkdir", "makedirs", "rename",
    "replace", "truncate", "chmod", "chown", "symlink", "system", "popen",
    "subprocess", "Popen", "socket", "urllib", "requests", "httpx",
    "urlopen", "eval(", "exec(", "compile(", "__import__", "shutil",
    "tempfile", "input(", "os.environ", "setattr", "delattr",
)

#: `open(x)` and `open(x, 'r')` read. Anything else may not.
OPEN_CALL = re.compile(r"\bopen\s*\(([^)]*)\)")
READ_MODES = {"", "r", "rb", "rt", "br", "tr"}

#: The target of a redirect, stopping at whatever ends the word. `\S+`
#: was wrong: in `ls $p 2>/dev/null; done` it captures "/dev/null;"
#: and then nothing is ever a redirect to /dev/null.
REDIRECT = re.compile(r"\d?>>?\s*([^\s;&|)]+)")


def _redirects_nowhere(part: str) -> bool:
    """/dev/null is a redirect that cannot keep anything."""
    return all(m.group(1) == "/dev/null" for m in REDIRECT.finditer(part))


def _is_read_only_command(segment: str) -> bool:
    words = words_of(segment)
    if not words:
        return True
    binary = os.path.basename(words[0])
    if binary in CONDITIONAL:
        return not any(flag in words[1:] for flag in CONDITIONAL[binary])
    if binary == "find":
        return not any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir",
                             "-fprint", "-fls") for a in words[1:])
    if binary not in READ_ONLY:
        return False
    return True


FOR_LOOP = re.compile(r"^for\s+\w+\s+in\s+(.+?)\s*$", re.DOTALL)


def _form_a(command: str) -> str | None:
    """A `for` loop over the project tree, with a read-only body.

    The whole line must be read-only, not just the loop: the shape seen in
    the wild is `ls projects/ && for p in projects/*/…; do …; done`.
    """
    parts = segments(command)
    if not any(part.startswith("for ") for part in parts):
        return None
    if not _redirects_nowhere(command):
        return None
    saw_project_glob = False
    for part in parts:
        if part in ("done", "do") or part.startswith("done"):
            continue
        loop = FOR_LOOP.match(part)
        if loop:
            words = loop.group(1).split()
            if not words:
                return None
            for word in words:
                bare = word.strip("\"'")
                if ".." in bare:
                    return None
                if "projects/" not in bare:
                    return None
            saw_project_glob = True
            continue
        body = part[3:].strip() if part.startswith("do ") else part
        if not _is_read_only_command(body):
            return None
    if not saw_project_glob:
        return None
    return ("form A: a for-loop over paths under projects/, body read-only, "
            "no redirect but /dev/null")


def _python_code_is_read_only(code: str) -> bool:
    for name in PY_WRITES:
        if name in code:
            return False
    for call in OPEN_CALL.finditer(code):
        args = [a.strip() for a in call.group(1).split(",")]
        mode = args[1].strip("\"'") if len(args) > 1 else ""
        if mode not in READ_MODES:
            return False
    return True


def _form_b(command: str) -> str | None:
    """`python -I -c <code>` where the code only reads.

    `-I` is required, not cosmetic: it stops python importing from the
    current directory, which is the rule for anything run over a tree whose
    contents a stage downloaded. The code is then audited for writes — the
    point of the form is reading a FINISHED film's artifact to learn its
    shape, and nothing in that needs a write.
    """
    parts = segments(command)
    if len(parts) != 1:
        return None
    words = words_of(parts[0])
    if not words or not os.path.basename(words[0]).startswith("python"):
        return None
    rest = words[1:]
    if "-I" not in rest or "-c" not in rest:
        return None
    code = rest[rest.index("-c") + 1] if rest.index("-c") + 1 < len(rest) else ""
    if not code:
        return None
    if not _python_code_is_read_only(code):
        return None
    if not _redirects_nowhere(command):
        return None
    return "form B: python -I -c, code audited read-only"


def inspection_allowance(command: str) -> str | None:
    """Which named inspection form this is, or None.

    Order does not matter — the forms do not overlap — but BOTH run only
    after the deny pass, so this can never re-admit something refused above.
    """
    return _form_a(command) or _form_b(command)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception as error:              # noqa: BLE001
        # FAIL CLOSED. A guard that cannot read what it was sent cannot say
        # the command is safe, and an unreadable payload is not a thing that
        # happens in normal operation. This was `return 0` for an hour and a
        # probe whose shell mangled a backslash sailed straight through it,
        # which is exactly the shape of the hole being closed here.
        print(f"Blocked by .claude/hooks/bash_guard.py: the hook could not "
              f"read its input ({type(error).__name__}), so it cannot vouch "
              f"for this command.\n  payload: {raw[:300]}", file=sys.stderr)
        return 2
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    patterns = deny_patterns()
    for segment in segments(command):
        why = offence(segment, patterns)
        if why:
            print(f"Blocked by .claude/hooks/bash_guard.py: {why}\n"
                  f"  offending command: {segment}\n"
                  f"  in: {command}", file=sys.stderr)
            return 2

    # NOTHING DENIED. If this is one of the two named inspection forms, say
    # so out loud: a `permissionDecision: allow` overrides the allow-list,
    # which is what these forms need, since the allow-list cannot parse them.
    allowance = inspection_allowance(command)
    if allowance:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason":
                f".claude/hooks/bash_guard.py: {allowance}"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
