#!/usr/bin/env python3
"""
Shared preToolUse hook: validate a write's target path against the actor's allowed globs.

DUAL-PLATFORM (one source, two hosts):
  • Kiro  — each agent wires its own fs_write hook and passes the agent NAME as argv[1]; the
    target path arrives as tool_input.path. The allow-list is the SINGLE SOURCE OF TRUTH in
    .kiro/agents/<agent>.json → toolsSettings.write.allowedPaths (this hook READS it).
  • Claude Code — ONE PreToolUse(Write|Edit|MultiEdit) hook in .claude/settings.json fires for
    EVERY actor with NO argv; the role arrives in the stdin JSON as `agent_type` (ABSENT for the
    MAIN SESSION), and the target path as tool_input.file_path. Claude agents are .md (no JSON
    allow-list), so this hook falls back to the built-in role policy below — UNLESS a Kiro-style
    .kiro/agents/<role>.json is present (a dual-target project), in which case that JSON wins.

ACTOR → ALLOWED PATHS:
  developer                         → code + tests + config (broad)
  analyst / architect / qa          → openspec/** (+ each role's extra dirs) — NO src/
  onboarder / context-refresh       → context/** + openspec/**
  main session (Claude, no agent)   → openspec/** + baton only — the orchestrator NEVER writes code

ROOT-ONLY SHARED WORKSPACE:
  Every shared workspace (context/, memory/, docs/, openspec/) and the shared config files live ONCE
  at the project root — NO per-platform copy and NO symlink. Both hosts write them via the ROOT path
  (`context/…`, `memory/…`, `docs/…`, `openspec/…`); the allow-lists below name ONLY those root paths.
  A write aimed at a platform dir (`.claude/context/…` or `.kiro/context/…`) is therefore BLOCKED on
  both hosts — that path is not a workspace, the root is. "một gốc duy nhất, không symlink".

Glob semantics:
  "dir/**"      → anything under dir/        (prefix match)
  "*.config.ts" → any path ending .config.ts (fnmatch; * spans '/')
  "package.json"→ exact path / basename match

Exit 0 = allowed, Exit 2 = blocked (or misconfigured → deny by default).
Self-test: `python3 check-write-path.py --self-test`.
"""
import json, sys, os, fnmatch

# Capture this script's absolute path BEFORE any chdir (correct even if __file__ is relative).
_SCRIPT = os.path.abspath(__file__)
# Hook robustness: a Bash `cd` in the session can leave this hook's cwd inside a project subdir
# (the host may run hooks from the session cwd), which would break the cwd-relative target-path
# resolution and the .snapshots/ writes below. The installed script lives at
# <root>/<platform>/agents/scripts/, so the project root is three parents up — chdir there so every
# relative path resolves from the root. Affects only THIS subprocess, never the caller's shell, and
# is a no-op when cwd is already the root.
try:
    os.chdir(os.path.join(os.path.dirname(_SCRIPT), "..", "..", ".."))
except OSError:
    pass


# Which host fired this hook? The script is installed at BOTH .kiro/agents/scripts/ and
# .claude/agents/scripts/; its own path tells us which one ran. The policy SOURCE is chosen by
# host (see decide()): on Claude the built-in policy below is authoritative — a stray
# .kiro/agents/<role>.json from a dual-target install must NOT win. (Both the JSON allow-lists and
# the built-in policy now name ROOT paths only — context/**, memory/**, openspec/** — never a
# platform-prefixed path, since the shared workspace lives once at the root with no symlink.)
IS_CLAUDE_HOST = "/.claude/" in _SCRIPT.replace("\\", "/")

# --- Built-in role policy (mirror of the Kiro agent JSON allowedPaths). Authoritative on the
#     Claude host; on Kiro the agent's own JSON wins via load_allowed_paths(). Every shared
#     workspace is ROOT-relative (context/**, memory/**, docs/**, openspec/**) — no per-platform
#     copy/symlink, so a platform-prefixed write target never appears (see the module docstring). ---
def _mem(claude_host):
    # memory/ lives once at the project root (no symlink); both hosts write it via the root path.
    return ["memory/**"]

def _baton(claude_host):
    return ["openspec/**"] + _mem(claude_host)

# The ORCHESTRATOR may write ONLY the CPP baton/state files (all underscore-prefixed) + the
# cross-spec bridge + memory — NEVER the phase DELIVERABLES (proposal.md, design.md, tasks.md,
# specs/**, *-report.md; none underscore-prefixed). This is the deterministic guard that forces the
# orchestrator to DELEGATE S1–S5 to the role agents instead of producing the artifacts itself.
def _orch(claude_host):
    return ["openspec/changes/**/_*.md", "openspec/changes/**/_*.json",
            "openspec/changes/**/_*.jsonl", "openspec/_*.md"] + _mem(claude_host)

_DEVELOPER = [
    "src/**", "app/**", "apps/**", "lib/**", "pkg/**", "internal/**", "cmd/**",
    "prisma/**", "migrations/**", "database/**", "db/**",
    "test/**", "tests/**", "e2e/**", "spec/**", "__tests__/**",
    "docker/**", "scripts/**", "config/**", ".github/**",
    "package.json", "composer.json", "pyproject.toml", "Makefile", "Dockerfile",
    "README.md", "*.config.ts", "*.config.js", "*.config.mjs", "*tsconfig.json",
]


def policy_for(actor, claude_host):
    """Built-in allow-list for an actor on the given host (actor is None for the main session).
    Every shared workspace is named by its ROOT path only (no per-platform copy/symlink)."""
    baton = _baton(claude_host)
    table = {
        "developer": _DEVELOPER + baton,
        "analyst":   ["openspec/**"] + baton,
        "architect": ["openspec/**"] + baton,
        "qa":        ["openspec/**", "test/**", "tests/**", "e2e/**", "spec/**", "__tests__/**"] + baton,
        "onboarder": ["context/**", "openspec/**"] + baton,
        # intake (pre-S1): prepares the ticket INPUT package only — Redmine/Figma → docs/extra-docs/<ticket_id>-<slug>/
        # (incl. the ui/<screen>.md spec files). docs/ lives once at the project root (no symlink). No
        # specs, no code; the analyst authors proposal.md + deltas from this package at S1/S2. It may
        # touch ONLY the underscore-prefixed baton (like the orchestrator), never broad openspec/** —
        # so it cannot ghost-write a deliverable such as proposal.md.
        "intake": ["docs/extra-docs/**"] + _orch(claude_host),
        # context-refresh: incremental re-sync of the context contract (same fence family as onboarder).
        "context-refresh": ["context/**", "openspec/**"] + baton,
        # The orchestrator (sdlc-full / sdlc-fast) writes ONLY baton/state (underscore-prefixed) — never
        # phase deliverables (forces delegation; see _orch). A bare main session (no agent_type) is the
        # user's own DEFAULT session, handled separately in decide() — unrestricted.
        "sdlc-full": _orch(claude_host),
        "sdlc-fast": _orch(claude_host),
    }
    if actor in table:
        return table[actor]
    return list(baton)   # main session (None) + any unknown role → spec/baton only, never src/


def resolve_actor(data, argv=None):
    """Kiro wires the agent name as argv[1] → that wins. Else use Claude's stdin `agent_type`
    (ABSENT for the main session). Returns the role name, or None for the Claude main session."""
    argv = sys.argv if argv is None else argv
    if len(argv) > 1 and str(argv[1]).strip() and not str(argv[1]).startswith("-"):
        return str(argv[1]).strip()
    at = (data.get("agent_type") or "").strip()
    return at or None


def find_agent_json(agent: str):
    """Locate <agent>.json. Anchor on this script's dir (reliable regardless of cwd), then fall
    back to cwd-relative locations (and the kit/ source tree for local tests)."""
    if not agent:
        return None
    script_dir = os.path.dirname(os.path.abspath(__file__))  # .../<target>/agents/scripts
    candidates = [
        os.path.join(script_dir, "..", f"{agent}.json"),                       # <target>/agents/<agent>.json
        os.path.join(os.getcwd(), ".kiro", "agents", f"{agent}.json"),
        os.path.join(os.getcwd(), "kit", "targets", "kiro", "agents", f"{agent}.json"),  # kit repo (dev/testing)
        os.path.join(os.getcwd(), "kit", "agents", f"{agent}.json"),           # legacy kit layout
        os.path.join(os.getcwd(), "agents", f"{agent}.json"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def load_allowed_paths(agent: str):
    """Kiro source of truth. Returns the JSON allowedPaths list, or None when no JSON is found
    (→ caller falls back to the Claude built-in policy)."""
    path = find_agent_json(agent)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return None
    return (cfg.get("toolsSettings", {}).get("write", {}) or {}).get("allowedPaths")


def normalize_path(path: str) -> str:
    """Convert absolute path to project-relative by stripping the workspace root."""
    if not path:
        return path
    if not os.path.isabs(path):
        return path

    cwd = os.getcwd()
    if path.startswith(cwd + "/"):
        return path[len(cwd) + 1 :]

    markers = [
        "specs/", "openspec/",
        ".kiro/memory/", ".kiro/openspec/", ".kiro/context/", ".kiro/context-map.json",
        ".claude/memory/", ".claude/context/",
        "memory/", "context/", "docs/",
        "src/", "app/", "apps/", "lib/", "pkg/", "internal/", "cmd/",
        "prisma/", "migrations/", "database/", "db/",
        "test/", "tests/", "e2e/", "spec/", "__tests__/", "docker/", "scripts/", "config/", ".github/",
    ]
    for marker in markers:
        idx = path.find("/" + marker)
        if idx != -1:
            return path[idx + 1 :]

    # Fallback: project-root file → match by basename against exact/suffix globs.
    return os.path.basename(path)


def path_allowed(path: str, patterns) -> bool:
    for pat in patterns:
        if pat.endswith("/**"):
            base = pat[:-3]  # "src/**" -> "src"
            if path == base or path.startswith(base + "/"):
                return True
        elif any(ch in pat for ch in "*?["):
            if fnmatch.fnmatch(path, pat):
                return True
        elif path == pat:
            return True
    return False


# --- Preservation net: context/ and memory/ hold human-curated / accumulated knowledge. Only
#     `developer` may carry Edit (security invariant), so every other role rewrites these via a FULL
#     Write — one bad generation could wipe curated facts or lessons. Two deterministic backstops run
#     in main() AFTER a write is judged allowed: (1) snapshot the prior file so any clobber is one
#     `cp` from recovery; (2) for memory/*.md, BLOCK a write that would delete an existing "## "
#     section (append-only discipline, like the cross-spec bridge). "ko phá những gì được lưu". ---
_PRESERVE_BASES = ("context/", "memory/",
                   ".claude/context/", ".kiro/context/",
                   ".claude/memory/", ".kiro/memory/")


def is_preserved_target(norm):
    return any(norm.startswith(b) for b in _PRESERVE_BASES)


def canonical_rel(norm):
    """Collapse any platform-prefixed path to its shared-root form (.claude/context/x → context/x)
    so snapshots share ONE history. Defensive only: platform-dir writes are now blocked upstream
    (root-only workspace), so `norm` is already root-relative in practice."""
    for pre in (".claude/", ".kiro/"):
        if norm.startswith(pre):
            return norm[len(pre):]
    return norm


def section_headers(text):
    import re
    return set(re.findall(r'^##\s+(.+?)\s*$', text or "", flags=re.MULTILINE))


def lost_sections(old, new):
    """'## ' headers present in `old` but missing from `new` — memory the write would destroy."""
    return sorted(section_headers(old) - section_headers(new))


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def snapshot_existing(norm, keep=5):
    """Best-effort: copy the soon-to-be-overwritten file into .snapshots/<canonical>/NNNN.bak
    (rotating, newest `keep` kept). Never raises — a snapshot failure must not block a valid write."""
    try:
        if not os.path.isfile(norm):
            return  # brand-new file: nothing to preserve
        import shutil
        snapdir = os.path.join(".snapshots", canonical_rel(norm))
        os.makedirs(snapdir, exist_ok=True)
        baks = sorted(f for f in os.listdir(snapdir) if f.endswith(".bak"))
        nxt = (int(baks[-1].split(".")[0]) + 1) if baks else 1
        shutil.copy2(norm, os.path.join(snapdir, f"{nxt:04d}.bak"))
        for old in baks[: max(0, len(baks) + 1 - keep)]:  # prune oldest beyond `keep`
            try: os.remove(os.path.join(snapdir, old))
            except OSError: pass
    except Exception:
        pass  # best-effort net — preservation must never break a legitimate write


def preserve(norm, tool_input):
    """Run the two backstops for an ALLOWED write to a preserved target. Returns a deny message
    (caller exits 2) if the memory append-guard trips, else None after taking a snapshot."""
    if not is_preserved_target(norm):
        return None
    crel = canonical_rel(norm)
    new_content = tool_input.get("content")
    if crel.startswith("memory/") and crel.endswith(".md") and isinstance(new_content, str):
        lost = lost_sections(read_text(norm), new_content)
        if lost:
            return (f"BLOCKED: write to {norm} would delete memory section(s): {', '.join(lost)}.\n"
                    f"  memory/ is append-only — keep every existing '## ' section and add new ones\n"
                    f"  (you may edit a section's body in place, just don't drop its header).\n")
    snapshot_existing(norm)
    return None


def decide(actor, raw_path, claude_host=None):
    """Return (allowed: bool, allowed_list, normalized_path). Shared by main() and the self-test.
    Policy SOURCE is host-based: Claude host → the built-in role policy (it knows `.claude/…`
    paths); Kiro host → the agent's .kiro JSON (falling back to the built-in policy if absent)."""
    if claude_host is None:
        claude_host = IS_CLAUDE_HOST
    if claude_host and actor is None:
        # Claude bare main session = the user's DEFAULT session → unrestricted (the orchestrator is
        # the named sdlc-* agent, which IS path-restricted via _CLAUDE_POLICY above).
        return (True, ["* (default session — unrestricted)"], normalize_path(raw_path))
    if claude_host:
        allowed = policy_for(actor, claude_host)            # Claude host: built-in policy wins
    else:
        allowed = load_allowed_paths(actor) if actor else None  # Kiro JSON = source of truth
        if allowed is None:
            allowed = policy_for(actor, claude_host)        # built-in fallback (host-scoped)
    if not allowed:
        return (False, allowed, "")
    norm = normalize_path(raw_path)
    return (path_allowed(norm, allowed), allowed, norm)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--self-test", "--test"):
        return _self_test()

    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.stderr.write("BLOCKED: check-write-path could not parse hook input (fail-closed).\n")
        sys.exit(2)

    actor = resolve_actor(data)
    ti = data.get("tool_input") or data.get("toolInput") or {}
    raw_path = ti.get("file_path") or ti.get("path") or data.get("path") or ""
    allowed_ok, allowed, norm = decide(actor, raw_path)

    if allowed is None or (not allowed):
        who = actor or "the main session"
        sys.stderr.write(f"BLOCKED: no write allow-list resolved for '{who}' (fail-closed).\n")
        sys.exit(2)

    if allowed_ok:
        deny = preserve(norm, ti)   # snapshot context/memory; block a memory-section deletion
        if deny:
            sys.stderr.write(deny)
            sys.exit(2)
        sys.exit(0)

    who = actor or "the main session (orchestrator)"
    sys.stderr.write(
        f"BLOCKED: {who} cannot write to {norm}.\n"
        f"  Allowed: {', '.join(allowed[:6])}{' …' if len(allowed) > 6 else ''}\n"
        f"  Code is written ONLY by the developer agent (S4); other roles write specs/artifacts.\n"
    )
    sys.exit(2)


def _self_test():
    """Vectors: (argv_agent, agent_type, raw_path, expect_allow)."""
    ALLOW, BLOCK = True, False
    vectors = [
        # --- Kiro: agent name via argv, allow-list from .kiro/agents/<agent>.json ---
        ("developer", None, "src/app.ts",                       ALLOW),
        ("developer", None, "tests/app.spec.ts",                ALLOW),
        ("developer", None, "random/elsewhere.txt",             BLOCK),
        ("analyst",   None, "openspec/changes/x/proposal.md",   ALLOW),
        ("analyst",   None, "src/app.ts",                       BLOCK),  # analyst-openspec-only
        ("analyst",   None, "docs/knowledge/x.md",              BLOCK),  # least-privilege: no docs/ write
        ("architect", None, "openspec/changes/x/design.md",     ALLOW),  # architect writes design via openspec
        ("architect", None, "docs/design.md",                   BLOCK),  # least-privilege: openspec-only now
        ("architect", None, "src/app.ts",                       BLOCK),
        ("qa",        None, "tests/e2e.spec.ts",                ALLOW),
        ("qa",        None, "src/app.ts",                       BLOCK),
        ("sdlc-full", None, "openspec/changes/x/_state.json",   ALLOW),  # baton (underscore-prefixed)
        ("sdlc-full", None, "openspec/_cross-spec-context.md",  ALLOW),  # cross-spec bridge
        ("sdlc-full", None, "openspec/changes/x/design.md",     BLOCK),  # DELIVERABLE → must delegate to architect
        ("sdlc-full", None, "openspec/changes/x/proposal.md",   BLOCK),  # DELIVERABLE → must delegate to analyst
        ("sdlc-full", None, "src/app.ts",                       BLOCK),  # never writes code
        ("onboarder", None, "context/project.md",               ALLOW),  # root context (no symlink)
        ("onboarder", None, ".kiro/context/project.md",          BLOCK),  # platform dir is NOT a write target
        ("intake",    None, "docs/extra-docs/user-profile/intake.md",       ALLOW),
        ("intake",    None, "docs/extra-docs/user-profile/ui/login.md",     ALLOW),  # ui/ screen spec
        ("intake",    None, "openspec/changes/x/_state.json",   ALLOW),  # baton ok
        ("intake",    None, "openspec/changes/x/proposal.md",   BLOCK),  # NOT a spec author
        ("intake",    None, "src/app.ts",                       BLOCK),  # never code
        ("context-refresh", None, "context/stack.md",           ALLOW),  # root context (no symlink)
        ("context-refresh", None, "context/conventions.md",     ALLOW),
        ("context-refresh", None, ".kiro/context/stack.md",     BLOCK),  # platform dir is NOT a write target
        ("context-refresh", None, "src/app.ts",                 BLOCK),  # never code
        # --- Claude: role via stdin agent_type (no argv), built-in policy ---
        (None, "developer", "src/app.ts",                       ALLOW),  # developer-allowed
        (None, "developer", "/abs/proj/src/models.py",          ALLOW),  # absolute, normalized
        (None, "developer", "secrets.txt",                      BLOCK),
        (None, "developer", "memory/developer.md",              ALLOW),  # root memory (no symlink)
        (None, "developer", ".claude/memory/developer.md",      BLOCK),  # platform dir is NOT a write target
        (None, "developer", ".kiro/memory/developer.md",        BLOCK),  # foreign platform dir — also not a target
        (None, None,        "openspec/changes/x/proposal.md",   ALLOW),  # default session — unrestricted
        (None, None,        "src/app.ts",                       ALLOW),  # default session = the user's own
        (None, "sdlc-full", "openspec/changes/x/_state.json",   ALLOW),  # orchestrator agent — baton only
        (None, "sdlc-full", "openspec/changes/x/design.md",     BLOCK),  # DELIVERABLE → must delegate to architect
        (None, "sdlc-full", "src/app.ts",                       BLOCK),  # never writes code
        (None, "analyst",   "openspec/specs/auth/spec.md",      ALLOW),  # analyst-openspec-only
        (None, "analyst",   "docs/knowledge/x.md",              BLOCK),  # least-privilege: no docs/ write
        (None, "analyst",   "src/app.ts",                       BLOCK),
        (None, "architect", "openspec/changes/x/design.md",     ALLOW),  # architect-openspec-only
        (None, "architect", "docs/design.md",                   BLOCK),  # least-privilege: openspec-only now
        (None, "qa",        "tests/unit.spec.ts",               ALLOW),
        (None, "qa",        "src/app.ts",                       BLOCK),
        (None, "onboarder", "context/project.md",                ALLOW),  # root context (no symlink)
        (None, "onboarder", ".claude/context/project.md",        BLOCK),  # platform dir is NOT a write target
        (None, "onboarder", ".kiro/context/project.md",          BLOCK),  # foreign platform dir — also not a target
        (None, "onboarder", "src/app.ts",                       BLOCK),
        (None, "intake",    "docs/extra-docs/user-profile/intake.md", ALLOW),  # root docs (no symlink)
        (None, "intake",    "docs/extra-docs/user-profile/ui/login.md", ALLOW),  # ui/ screen spec
        (None, "intake",    ".claude/docs/extra-docs/x/figma/screen.png", BLOCK),  # platform dir is NOT a write target
        (None, "intake",    ".kiro/docs/extra-docs/x/intake.md", BLOCK),  # foreign platform dir — also not a target
        (None, "intake",    "openspec/changes/x/proposal.md",   BLOCK),  # not a spec author
        (None, "intake",    "src/app.ts",                       BLOCK),  # never code
        (None, "context-refresh", "context/conventions.md",     ALLOW),  # root context (no symlink)
        (None, "context-refresh", ".claude/context/stack.md",   BLOCK),  # platform dir is NOT a write target
        (None, "context-refresh", ".kiro/context/stack.md",     BLOCK),  # foreign platform dir — also not a target
        (None, "context-refresh", "src/app.ts",                 BLOCK),  # never code
    ]
    fails = 0
    for argv_agent, agent_type, raw_path, expect in vectors:
        data = {} if agent_type is None else {"agent_type": agent_type}
        argv = ["check-write-path.py"] + ([argv_agent] if argv_agent else [])
        actor = resolve_actor(data, argv=argv)
        # Exercise the REAL decide() with the host that fired (kiro vector ⇒ Kiro host via argv;
        # claude vector ⇒ Claude host via agent_type), so host-based source selection is under test.
        allowed_ok, allowed, _ = decide(actor, raw_path, claude_host=(argv_agent is None))
        ok = allowed_ok == expect
        fails += not ok
        tag = "PASS" if ok else "FAIL"
        host = "kiro " if argv_agent else "claude"
        sys.stdout.write(f"  [{tag}] {host} actor={str(argv_agent or agent_type or 'MAIN'):10} "
                         f"{'allow' if allowed_ok else 'BLOCK'} :: {raw_path}\n")
    total = len(vectors)

    # --- preservation: memory append-guard (pure section-loss logic, no filesystem) ---
    mem_old = "## Lesson A\nbody\n## Lesson B\nbody\n"
    mem_checks = [
        ("keep all + append", mem_old + "## Lesson C\nz\n",      []),            # safe
        ("edit body only",    "## Lesson A\nEDITED\n## Lesson B\nb\n", []),       # safe (headers intact)
        ("drop a section",    "## Lesson A\nbody\n",             ["Lesson B"]),   # UNSAFE → would block
        ("wipe everything",   "",                                ["Lesson A", "Lesson B"]),
    ]
    for label, new, expect in mem_checks:
        got = lost_sections(mem_old, new)
        ok = got == expect
        fails += not ok
        total += 1
        sys.stdout.write(f"  [{'PASS' if ok else 'FAIL'}] mem-guard {label:18} lost={got}\n")

    sys.stdout.write(f"\n  {total - fails}/{total} passed"
                     f"{'' if not fails else f' — {fails} FAILED'}\n")
    return 1 if fails else 0


if __name__ == "__main__":
    rc = main()
    if rc is not None:
        sys.exit(rc)
