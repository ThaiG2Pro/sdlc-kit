#!/usr/bin/env python3
"""
Shared preToolUse hook: keep the shell READ-ONLY for non-developer agents.

WHY THIS EXISTS
  An agent's `write` tool is path-restricted (toolsSettings.write.allowedPaths) and the
  `fs_write` hook (check-write-path.py) enforces those globs. But the `shell` / executeBash
  tool bypasses all of that — it can mutate the filesystem through:
    - redirection to a real file:   echo x > src/app.ts   ·   foo >> file   ·   ... | tee f
    - in-place editors:             sed -i ... · perl -i ...
    - an interpreter eval:          node -e "fs.writeFileSync(...)"  ·  python3 -c "open(...,'w')"
    - file ops:                     cp / mv / rm / touch / mkdir / dd / truncate / ln / install
    - working-tree mutation:        git add/commit/checkout/restore/reset/stash · patch
  Only the DEVELOPER agent (S4) may write code. The orchestrators and the read-phase agents
  must treat the shell as read-only for the filesystem — they run guards (node .kiro/tools/*.mjs),
  openspec, and read-only inspection (cat/grep/ls/…). They write artifacts ONLY via the
  path-guarded `write` tool, never via the shell.

DUAL-PLATFORM (one source, two hosts):
  • Kiro  — each agent wires its own hook and passes the agent NAME as argv[1]:
      "preToolUse": [ { "matcher": "execute_bash",
        "command": "python3 .kiro/agents/scripts/check-shell-command.py <agent>",
        "timeout_ms": 3000 } ]
    (Today only sdlc-full / sdlc-fast wire this; the developer agent has no shell guard.)
  • Claude Code — ONE PreToolUse(Bash) hook in .claude/settings.json fires for EVERY actor with
    NO argv. The acting role arrives in the stdin JSON as `agent_type` — present only when a
    Task-spawned subagent acts, ABSENT when the MAIN SESSION (the orchestrator) acts:
      { "matcher": "Bash",
        "hooks": [ { "type": "command",
          "command": "python3 .claude/agents/scripts/check-shell-command.py" } ] }
    Because the single hook sees all actors, it grants the developer exception INTERNALLY and
    treats the main session (no agent_type) as the read-only orchestrator.

ACTOR → CLASS → POLICY (identical regex denylist for both hosts):
  developer                              → ALLOW (the only code-writing role; full shell)
  orchestrator (Kiro sdlc-*, Claude main)→ READ-ONLY except an isolation branch/worktree create
                                           OR a plain `git switch <branch>` (resume) — see _BRANCH_*
  restricted   (analyst/architect/qa/…)  → READ-ONLY, no exceptions

CONTRACT: reads the hook JSON on stdin; exit 0 = allow, exit 2 = block (fail-closed on parse error).
Self-test: `python3 check-shell-command.py --self-test` (covers Kiro + Claude vectors).
"""
import json
import os
import re
import sys

# Which host fired this hook (script lives at .kiro/agents/scripts/ vs .claude/agents/scripts/).
# Decides the bare-main-session policy: on Claude a session with NO agent_type is the USER'S default
# session (unrestricted — the SDLC orchestrator now runs as the named `sdlc-full`/`sdlc-fast` agent,
# not the bare main session). On Kiro the actor always arrives via argv[1], so a missing actor is a
# misconfiguration → fail closed (restricted).
IS_CLAUDE_HOST = "/.claude/" in os.path.abspath(__file__).replace("\\", "/")

# Harmless redirections that do NOT touch project files — stripped before the write-redirect check.
_DEVNULL = re.compile(r"""(?:\d*|&)>>?\s*/dev/null""")          # 2>/dev/null, >/dev/null, &>/dev/null
_FD_DUP = re.compile(r"""\d*>&\d+""")                            # 2>&1, 1>&2


def _strip_quoted(command: str) -> str:
    """Blank out the CONTENTS of '...'/"..." string literals (replaced char-for-char with spaces,
    so byte offsets used elsewhere still line up) before the _DENY scan runs.

    WHY: a quoted `>`/`rm`/`.php` etc. is inert shell-wise — it is DATA, not a redirect or a command
    name (`grep -o '<Tag>.*</Tag>' x.xml`, `tinker --execute="Foo::bar()->baz()"`, `grep "rm -rf"
    log.txt` are all plain reads that the old raw-text scan flagged because it couldn't tell a
    literal `>`/`->`/keyword inside a string from the real thing). An UNQUOTED `->` is genuinely a
    redirect in real shell semantics (`echo a->b` really does write file `b` — verified empirically),
    so this must stay quote-aware rather than special-casing `->` unconditionally, which would open a
    real bypass. Only `'...'`/`"..."` spans are blanked; `$(...)`/backticks are left alone (real
    command substitution executes even when it visually sits inside a string) so mutations smuggled
    that way are still caught.
    """
    out = []
    quote = None  # None | "'" | '"'
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if quote is None:
            out.append(c)
            if c in ("'", '"'):
                quote = c
        elif quote == '"' and c == "\\" and i + 1 < n:
            out.append("  ")
            i += 2
            continue
        elif c == quote:
            out.append(c)
            quote = None
        else:
            out.append(" ")
        i += 1
    return "".join(out)


# Filesystem-mutating constructs. Each (regex, label). Matched against the de-noised command.
_DENY = [
    (re.compile(r"(?<![0-9&])>>?(?!\s*&)"), "output redirection to a file (`>`/`>>`)"),
    (re.compile(r"\btee\b"), "`tee` (writes a file)"),
    (re.compile(r"\bsed\b[^|;&]*?\s-[a-zA-Z]*i"), "`sed -i` (in-place edit)"),
    (re.compile(r"\bperl\b[^|;&]*?\s-[a-zA-Z]*i"), "`perl -i` (in-place edit)"),
    (re.compile(r"\bnode\b[^|;&]*?\s(?:-e|--eval|-p|--print)\b"), "`node -e/--eval/-p` (inline code → arbitrary write)"),
    (re.compile(r"\bpython3?\b[^|;&]*?\s-c\b"), "`python -c` (inline code → arbitrary write)"),
    (re.compile(r"\b(?:node|python3?)\b[^|;&]*?(?:<<|\s-\s*$|\s-\s)"), "interpreter reading stdin/heredoc (→ arbitrary write)"),
    # Running an arbitrary SCRIPT FILE is the same escalation as `-c`: a non-developer role could
    # author gen_xlsx.py inside its (path-allowed) openspec/ fence and then EXECUTE it here. Block
    # `python/node/… <some-script.(py|js|mjs|…)>`. The kit's OWN generators (under .kiro//.claude/
    # skills|tools — kit-owned, read-only, not authorable by any role) are whitelisted in classify().
    # `(?<!\.)` before the interpreter alternation stops it matching the tail of an unrelated file's
    # OWN extension (`phpstan analyse A.php B.php` was a false positive: "php" inside "A.php" — right
    # after a bare `.` — was misread as the php INTERPRETER, with "B.php" then misread as its script
    # arg; a real interpreter invocation is never glued directly after a `.` with no separator).
    (re.compile(r"(?<!\.)\b(?:python3?|node|deno|bun|ts-node|ruby|perl|php|bash|sh)\b[^|;&]*?\s[^\s|;&]*\.(?:py|js|mjs|cjs|ts|tsx|jsx|rb|pl|php|sh|bash)\b"),
     "running a script file (→ arbitrary write; use the kit generator, not a one-off script)"),
    (re.compile(r"\b(?:cp|mv|rm|rmdir|touch|mkdir|dd|truncate|ln|chmod|chown)\b"), "filesystem-mutating command"),
    # `(?:\S+\s+)*?` non-greedily consumes any git global options (`-c x`, `-C /repo`,
    # `--git-dir=…`) smuggled between `git` and the mutating subcommand — closes the bypass.
    # `switch` is here so dangerous switch forms (`-f`/`--discard-changes`, a trailing pathspec) are
    # denied by default; the orchestrator's SAFE `git switch <branch>` resume form is allowlisted
    # earlier in classify() (via _BRANCH_SWITCH), which returns before this _DENY sweep.
    (re.compile(r"\bgit\s+(?:\S+\s+)*?(?:add|commit|apply|checkout|switch|restore|reset|stash|rm|mv|push|merge|rebase|tag|clean)\b"), "git working-tree mutation"),
    (re.compile(r"\bgit\s+branch\b[^|;&]*\s-(?:d|D|m|M|c|C|-delete|-move|-copy|-force)\b"), "git branch delete/rename"),
    (re.compile(r"\bpatch\b"), "`patch` (applies a diff)"),
    # Package/dependency managers mutate project files (pyproject.toml, lockfiles, node_modules)
    # — that is developer (S4) work, never the orchestrator's. Read-only subcommands (list/show/
    # version/run-a-readonly-script) are NOT matched.
    (re.compile(r"\b(?:uv|pip|pip3|npm|pnpm|yarn|poetry|cargo|composer|bundle|gem|go|mvn|gradle|dotnet|brew|apt|apt-get|pacman|dnf|yum|pipenv|conda|mamba)\b\s+(?:add|remove|rm|install|uninstall|sync|require|get|update|upgrade|init|build|publish|lock|i|ci)\b"), "package/dependency manager mutation"),
]


# The DEVELOPER (S4) is the only role that may write code — full shell access.
_DEVELOPER = {"developer"}
# Kiro orchestrator agent NAMES. On Claude the orchestrator is the MAIN SESSION (no agent_type →
# actor is None), so None also maps to the orchestrator class below.
_ORCH_AGENTS = {"sdlc-full", "sdlc-fast"}

# The orchestrator may manage a pipeline's isolation branch/worktree — and NOTHING else — via the
# shell (sdlc.config.json git.isolation). This is the single, deliberate exception to the "shell is
# read-only for the orchestrator" rule. Two shapes are allowed:
#   • CREATE a new isolation branch/worktree at pipeline kickoff (_BRANCH_CREATE below).
#   • SWITCH to an EXISTING isolation branch on pipeline resume (_BRANCH_SWITCH below).
# Both only move HEAD / add a sibling working tree — they touch NO tracked file as an authored write.
# `git add/commit/checkout <file>/restore/reset/merge/...` stay BLOCKED for everyone — the
# orchestrator still never writes code.
_CMD_SEP = re.compile(r"(?:[;|&]|\$\(|`|<\(|>\()")   # no chaining/substitution may ride along
_BRANCH_CREATE = [
    re.compile(r"^git\s+checkout\s+-b\s+\S"),         # create + switch to a NEW branch
    re.compile(r"^git\s+switch\s+-c\s+\S"),           # modern equivalent of checkout -b
    re.compile(r"^git\s+worktree\s+add\s+\S"),        # create a new working tree (may carry -b)
]
# Resume: switch to an EXISTING branch. Only `git switch <branch>` — the purpose-built, file-safe
# form: unlike `git checkout <path>` it CANNOT restore/overwrite a working-tree file (that is `git
# restore`), so it never becomes a code-write vector. The pattern permits exactly ONE non-flag arg and
# nothing after it, so destructive flags (`-f`/`--force`/`--discard-changes`/`-C`) and a trailing
# pathspec are excluded. Plain `git checkout <branch>` stays BLOCKED — it is ambiguous with the
# file-restore form — so resume is steered to `git switch`.
_BRANCH_SWITCH = [
    re.compile(r"^git\s+switch\s+(?!-)\S+\s*$"),      # switch to an existing branch (no flags, one arg)
]

# Kit-OWNED helper scripts a restricted role IS allowed to run via an interpreter: they live under
# the platform dir (.kiro//.claude/) in skills/ or tools/, are kit-managed (regenerated on --force,
# never authorable by any role's write-fence), and only emit artifacts into the role's own fence
# (e.g. gen_testcases_xlsx.py → openspec/**/qa/testcases.xlsx). This is what lets qa produce its XLSX
# the SANCTIONED way while a one-off script it authored itself stays blocked. Must contain no shell
# chaining/substitution (checked alongside in classify via _CMD_SEP-free single command).
_KIT_SCRIPT = re.compile(
    r"\b(?:python3?|node)\s+(?:\./)?\.(?:kiro|claude)/(?:skills|tools)/[^\s|;&]+\.(?:py|mjs|js)\b")


def resolve_actor(data, argv=None):
    """Resolve the acting role across both hosts.
      • Kiro   wires the agent name as argv[1] → that wins.
      • Claude puts `agent_type` in the stdin JSON for a Task subagent; it is ABSENT for the
        main session.
    Returns the role name, or None for the Claude main session (i.e. the orchestrator)."""
    argv = sys.argv if argv is None else argv
    if len(argv) > 1 and str(argv[1]).strip() and not str(argv[1]).startswith("-"):
        return str(argv[1]).strip()
    at = (data.get("agent_type") or "").strip()
    return at or None


def actor_class(actor, claude_host=None):
    """Map a resolved actor to a policy class."""
    if claude_host is None:
        claude_host = IS_CLAUDE_HOST
    if actor in _DEVELOPER:
        return "developer"
    if actor in _ORCH_AGENTS:
        return "orchestrator"   # sdlc-full / sdlc-fast — the orchestrator runs as a named agent
    if actor is None:
        # Claude: bare main session = the user's DEFAULT session → unrestricted (the orchestrator is
        # the named sdlc-* agent above, not this). Kiro: a missing actor is a misconfig → fail closed.
        return "default" if claude_host else "restricted"
    return "restricted"   # analyst / architect / qa / onboarder + any unknown role


def _is_isolation_branch_op(command: str) -> bool:
    """True iff `command` is exactly one isolation branch/worktree op the orchestrator may run —
    a CREATE (`checkout -b` / `switch -c` / `worktree add`) or a SWITCH to an existing branch
    (`git switch <branch>`) — with no shell chaining or command substitution smuggled in."""
    cmd = command.strip()
    if _CMD_SEP.search(cmd):
        return False
    return any(rx.match(cmd) for rx in _BRANCH_CREATE + _BRANCH_SWITCH)


def classify(command: str, cls: str = "restricted"):
    """Return a human-readable reason if `command` would mutate the filesystem for an actor of
    policy class `cls`, else None (allowed)."""
    if not command or not command.strip():
        return None
    if cls in ("developer", "default"):
        return None  # developer = the code-writing role; default = the user's own session — full shell
    if cls == "orchestrator" and _is_isolation_branch_op(command):
        return None  # deliberate exception: isolation branch/worktree create OR switch-to-existing (resume)
    # Sanctioned exception (all restricted roles incl. orchestrator): run a KIT-OWNED generator
    # (.kiro//.claude/ skills|tools) — kit-managed, not role-authorable, writes only into the role's
    # fence. Must be a single command with no chaining/substitution smuggled alongside.
    if not _CMD_SEP.search(command.strip()) and _KIT_SCRIPT.search(command):
        return None
    # Blank quoted string contents (inert data, not real shell syntax), then remove harmless
    # /dev/null + fd-dup redirections, so neither trips the `>` / keyword rules below.
    denoised = _FD_DUP.sub(" ", _DEVNULL.sub(" ", _strip_quoted(command)))
    for rx, label in _DENY:
        if rx.search(denoised):
            return label
    return None


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("--self-test", "--test"):
        return _self_test()
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.stderr.write("BLOCKED: check-shell-command could not parse hook input (fail-closed).\n")
        return 2
    actor = resolve_actor(data)
    cls = actor_class(actor)
    ti = data.get("tool_input") or data.get("toolInput") or {}
    command = ti.get("command") or ti.get("cmd") or data.get("command") or ""
    reason = classify(command, cls)
    if reason:
        who = actor or "the main session (orchestrator)"
        sys.stderr.write(
            f"BLOCKED: {who} may not write via the shell — {reason}.\n"
            f"  Command: {command.strip()[:200]}\n"
            f"  The shell is READ-ONLY for everyone but the developer agent (S4), the only role that\n"
            f"  writes code. Route the change there; write spec artifacts via the Write tool.\n"
        )
        return 2
    return 0


def _self_test() -> int:
    """Vector table covering both hosts. (argv_agent, agent_type, command, expect_block)."""
    BLOCK, ALLOW = True, False
    vectors = [
        # --- Kiro: agent name via argv ---
        ("sdlc-full", None, "rm -rf build",                 BLOCK),
        ("sdlc-full", None, "echo x > src/app.ts",          BLOCK),
        ("sdlc-full", None, "sed -i s/a/b/ f",              BLOCK),
        ("sdlc-full", None, "git commit -m x",              BLOCK),
        ("sdlc-full", None, "git -c core.hooksPath=/dev/null commit -m x", BLOCK),  # global-opt bypass
        ("sdlc-full", None, "git -C /repo add .",           BLOCK),                 # global-opt bypass
        ("sdlc-full", None, "git --git-dir=/tmp/x reset --hard", BLOCK),            # global-opt bypass
        ("sdlc-full", None, "uv add requests",              BLOCK),
        ("sdlc-full", None, "git checkout -b feat/x",       ALLOW),  # branch-create exception
        ("sdlc-full", None, "git switch -c feat/x",         ALLOW),
        ("sdlc-full", None, "git worktree add ../wt",       ALLOW),
        ("sdlc-full", None, "git switch feat/x",            ALLOW),  # switch to existing isolation branch (resume)
        ("sdlc-full", None, "git switch sdlc/iso-123",      ALLOW),
        ("sdlc-full", None, "git switch -f feat/x",         BLOCK),  # --force/discard flag not allowed
        ("sdlc-full", None, "git switch --discard-changes feat/x", BLOCK),
        ("sdlc-full", None, "git checkout feat/x",          BLOCK),  # bare checkout is ambiguous with file-restore
        ("sdlc-full", None, "git checkout package.json",    BLOCK),  # file-restore = a write, stays blocked
        ("sdlc-full", None, "git switch feat/x -- src/a.ts",BLOCK),  # trailing pathspec not allowed
        ("sdlc-full", None, "git switch a && rm x",         BLOCK),  # chaining defeats exception
        ("sdlc-full", None, "cat f && rm x",                BLOCK),  # chaining defeats exception
        ("sdlc-fast", None, "openspec list",                ALLOW),
        ("sdlc-full", None, "grep -rn foo .",               ALLOW),
        ("sdlc-full", None, "node .kiro/tools/cpp-guard.mjs",ALLOW),
        ("sdlc-full", None, "node .kiro/tools/state-set.mjs --set gates.S2=passed --set current_phase=S3", ALLOW),  # kit state tool (not -e/eval)
        # --- Claude: role via stdin agent_type (no argv) ---
        (None, "developer", "rm -rf build",                 ALLOW),  # developer — full shell
        (None, "developer", "uv add requests",              ALLOW),
        (None, "developer", "echo x > src/app.ts",          ALLOW),
        (None, "developer", "git commit -m x",              ALLOW),
        # Bare main session = the user's DEFAULT session → unrestricted (orchestrator is the named agent below).
        (None, None,        "rm -rf build",                 ALLOW),
        (None, None,        "echo x > src/app.ts",          ALLOW),
        (None, None,        "python3 -c \"print(1)\"",      ALLOW),
        # Orchestrator runs as the named sdlc-full / sdlc-fast agent → read-only + branch-create only.
        (None, "sdlc-full", "rm -rf build",                 BLOCK),
        (None, "sdlc-full", "echo x > src/app.ts",          BLOCK),
        (None, "sdlc-full", "uv add requests",              BLOCK),
        (None, "sdlc-full", "git checkout -b feat/x",       ALLOW),  # branch-create exception
        (None, "sdlc-full", "git switch feat/x",            ALLOW),  # switch to existing isolation branch (resume)
        (None, "sdlc-full", "git switch -f feat/x",         BLOCK),  # --force not allowed
        (None, "sdlc-full", "git checkout feat/x",          BLOCK),  # bare checkout stays blocked
        (None, "sdlc-fast", "git switch bugfix/iso-9",      ALLOW),  # fast-track resume
        (None, "sdlc-fast", "grep -rn foo .",               ALLOW),
        (None, "analyst",   "echo x > openspec/p.md",       BLOCK),  # restricted roles: read-only shell
        (None, "architect", "rm x",                         BLOCK),
        (None, "qa",        "sed -i s/a/b/ f",              BLOCK),
        (None, "onboarder", "echo x > context/p.md",        BLOCK),  # restricted roles: read-only shell
        # --- quote-aware false-positive fixes (real incident: QA re-run burned retries on these) ---
        (None, "qa",        "grep -o '<Tag>.*</Tag>' file.xml",              ALLOW),  # quoted `>` in an XML pattern
        (None, "qa",        'grep -c "rm -rf" CHANGELOG.md',                 ALLOW),  # quoted keyword as search text
        (None, "qa",        'docker exec c1 php artisan tinker --execute="App\\Foo::bar()->baz()"', ALLOW),  # quoted `->`
        (None, "qa",        "phpstan analyse A.php B.php C.php",             ALLOW),  # 2+ bare .php args, no real interpreter
        (None, "qa",        "phpstan analyse Modules/FraudPrevention",       ALLOW),
        (None, "qa",        "echo test -> outfile.txt",                     BLOCK),  # UNQUOTED `->` really is `-` + redirect
        (None, "qa",        'echo "a->b.txt" > out.txt',                    BLOCK),  # quoted arrow, but a REAL trailing redirect
        (None, "qa",        "python3 -c \"import os; os.system('rm -rf /')\"", BLOCK),  # -c flag stays outside quotes
        (None, "qa",        "rm -rf 'my file with spaces'",                 BLOCK),  # command name stays outside quotes
        # --- script-execution guard: running an authored script == arbitrary write ---
        (None, "qa",        "python3 openspec/changes/x/qa/gen_xlsx.py", BLOCK),  # the exact bypass we are closing
        (None, "qa",        "node openspec/changes/x/qa/gen.mjs",        BLOCK),
        ("sdlc-full", None, "python3 openspec/changes/x/foo.py",         BLOCK),  # Kiro host too
        # sanctioned: the kit's OWN generator (kit-managed, writes only into the role fence)
        (None, "qa",        "python3 .claude/skills/qa-test-design/gen_testcases_xlsx.py openspec/changes/x/qa/testcases.json openspec/changes/x/qa/testcases.xlsx", ALLOW),
        ("qa",        None, "python3 .kiro/skills/qa-test-design/gen_testcases_xlsx.py a.json a.xlsx", ALLOW),
        (None, "qa",        "python3 .claude/skills/qa-test-design/gen_testcases_xlsx.py a.json a.xlsx && rm x", BLOCK),  # chaining defeats it
        (None, "developer", "python3 openspec/changes/x/qa/gen_xlsx.py", ALLOW),  # developer runs any script
        (None, None,        "python3 some_script.py",         ALLOW),  # default session — unrestricted
    ]
    fails = 0
    for argv_agent, agent_type, command, expect in vectors:
        data = {} if agent_type is None else {"agent_type": agent_type}
        argv = ["check-shell-command.py"] + ([argv_agent] if argv_agent else [])
        actor = resolve_actor(data, argv=argv)
        blocked = classify(command, actor_class(actor, claude_host=(argv_agent is None))) is not None
        ok = blocked == expect
        fails += not ok
        tag = "PASS" if ok else "FAIL"
        host = "kiro " if argv_agent else "claude"
        sys.stdout.write(f"  [{tag}] {host} actor={str(argv_agent or agent_type or 'MAIN'):10} "
                         f"{'BLOCK' if blocked else 'allow'} :: {command}\n")
    total = len(vectors)
    sys.stdout.write(f"\n  {total - fails}/{total} passed"
                     f"{'' if not fails else f' — {fails} FAILED'}\n")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
