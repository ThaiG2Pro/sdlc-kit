#!/usr/bin/env python3
"""
CPP-aware agentSpawn hook script.
Reads _state.json + CPP artifacts and outputs rich context for agent startup.
Usage: python3 .kiro/agents/scripts/agent-spawn-context.py [agent_name]
"""
import json
import sys
import os

# Hook robustness: a Bash `cd` in the session can leave this hook's cwd inside a project subdir
# (the host may run hooks from the session cwd), breaking the relative reads below. This script lives
# at <root>/<platform>/agents/scripts/, so the project root is three parents up — chdir there so every
# relative path (openspec/, memory/, _state.json) resolves from the root. Affects only THIS
# subprocess, never the caller's shell. No-op in the normal case (cwd already the root).
try:
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
except OSError:
    pass

agent_name = sys.argv[1] if len(sys.argv) > 1 else "unknown"

def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return None

def count_lines(path):
    try:
        with open(path) as f:
            return sum(1 for line in f if line.strip())
    except:
        return 0

def file_exists(path):
    return os.path.isfile(path)

def read_first_line_match(path, prefix):
    try:
        with open(path) as f:
            for line in f:
                if prefix in line:
                    return line.strip()
    except:
        pass
    return None

# 1. Find the active OpenSpec change.
# Workspace is OpenSpec-backed: active changes live in openspec/changes/<name>/ (each with a
# _state.json); archived ones in openspec/changes/archive/. There is no .active-feature.json.
# Pick the change whose _state.json was modified most recently = the one being worked on.
def find_active_change():
    base = 'openspec/changes'
    if not os.path.isdir(base):
        return None
    candidates = []
    for name in os.listdir(base):
        if name == 'archive':
            continue
        d = os.path.join(base, name)
        st = os.path.join(d, '_state.json')
        if os.path.isdir(d) and os.path.isfile(st):
            candidates.append((os.path.getmtime(st), d))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]

spec_dir = find_active_change()
if not spec_dir:
    print("No active change. Say: sdlc <feature|cr|bugfix|hotfix|rebuild> {slug} ticket {id}")
    sys.exit(0)

state = read_json(f'{spec_dir}/_state.json')
if not state:
    print(f"No _state.json in {spec_dir}")
    sys.exit(0)

# 2. Basic state info
tid = state.get('ticket_id', '?')
slug = state.get('feature_slug', '?')
phase = state.get('current_phase', '?')
last_agent = state.get('last_agent', '?')
wtype = state.get('type', 'feature')          # which pipeline (feature/cr/bugfix/hotfix/rebuild)
phases = state.get('phases', [])

print(f"Change: {tid}-{slug}  ({spec_dir})")
print(f"Type: {wtype}{('  pipeline: ' + '→'.join(phases)) if phases else ''}")
print(f"Phase: {phase} | Last agent: {last_agent}")

# 3. CPP artifacts status
handoff_exists = file_exists(f'{spec_dir}/_handoff.md')
decisions_count = count_lines(f'{spec_dir}/_decisions.jsonl')
glossary_count = max(0, count_lines(f'{spec_dir}/_glossary.md') - 3)  # subtract header rows
state_enriched = bool(state.get('phase_history')) and bool(state.get('active_concerns'))

print()
print("=== CPP Artifacts ===")
print(f"  _handoff.md:      {'YES' if handoff_exists else 'MISSING'}")
print(f"  _decisions.jsonl:  {decisions_count} entries" if decisions_count > 0 else "  _decisions.jsonl:  MISSING")
print(f"  _glossary.md:      {glossary_count} terms" if glossary_count > 0 else "  _glossary.md:      MISSING")
print(f"  _state.json:       {'ENRICHED' if state_enriched else 'BASIC'}")

# 4. Active concerns (top 3)
concerns = state.get('active_concerns', [])
if concerns:
    print()
    print("=== Active Concerns ===")
    for c in concerns[:3]:
        print(f"  ⚠ {c}")

# 5. Next action
na = state.get('next_action', {})
if na.get('agent'):
    print()
    if na.get('blocker'):
        print(f"GATE: {na['blocker']}")
        print(f'Say "approve" to continue, or provide feedback.')
    else:
        print(f"Ready for: {na.get('command', '?')}")
        print(f'Say "continue" to proceed.')

    # Priority reading (for the target agent)
    pr = na.get('priority_reading', [])
    if pr and na.get('agent') == agent_name:
        print()
        print("=== Priority Reading Order ===")
        for i, item in enumerate(pr[:5], 1):
            print(f"  {i}. {item}")

    # Watch items (for the target agent)
    wi = na.get('watch_items', [])
    if wi and na.get('agent') == agent_name:
        print()
        print("=== Watch Items ===")
        for item in wi[:5]:
            print(f"  ⚠ {item}")

# 5b. Context budget — tell the role, in one line, how much it may read this spawn. The role prompt
#     carries the full per-role table; at scope=tiny that collapses to baton + priority_reading.
scope = state.get('scope') or 'standard'
print()
if scope == 'tiny':
    print("=== Context Budget: scope=tiny ===")
    print("  Read ONLY: CPP baton + next_action.priority_reading (+ context/stack.md for developer/qa).")
    print("  Skip every other context/*.md, steering/*.md and golden example.")
else:
    print(f"=== Context Budget: scope={scope} ===")
    print("  Read only your role's column of the context table (CLAUDE.md / your Inputs) — not all of context/.")

# 6. Role memory digest — memory/<role>/_index.md, one line per past change (the legacy flat
#    memory/<role>.md is hard-blocked by the write guard and no longer written). Show the last 3
#    lines so the role sees the digest is there without opening the fragment files. memory/ lives
#    ONCE at the project root (no symlink); both platforms read it via the root path.
index_path = f'memory/{agent_name}/_index.md'
if os.path.isfile(index_path):
    with open(index_path) as mf:
        entries = [l.rstrip() for l in mf if l.lstrip().startswith('- ')]
    if entries:
        print()
        print(f"=== Role Memory digest ({len(entries)} entr{'y' if len(entries) == 1 else 'ies'}; last 3) ===")
        for line in entries[-3:]:
            print(f"  {line[:160]}")

# 7. Terminology snapshot (top 5 terms)
terms = state.get('terminology', {})
if terms:
    print()
    print("=== Key Terms ===")
    for term, defn in list(terms.items())[:5]:
        print(f"  {term}: {defn}")
