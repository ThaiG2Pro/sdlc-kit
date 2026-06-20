#!/usr/bin/env python3
"""
CPP-aware agentSpawn hook script.
Reads _state.json + CPP artifacts and outputs rich context for agent startup.
Usage: python3 .kiro/agents/scripts/agent-spawn-context.py [agent_name]
"""
import json
import sys
import os

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

# 1. Find active spec
active = read_json('specs/.active-feature.json')
if not active or not active.get('active_spec'):
    print(f"No active feature. Say: sdlc feature {{name}} ticket {{id}}")
    sys.exit(0)

spec_dir = active['active_spec']
state = read_json(f'{spec_dir}/_state.json')
if not state:
    print(f"No _state.json in {spec_dir}")
    sys.exit(0)

# 2. Basic state info
tid = state.get('ticket_id', '?')
slug = state.get('feature_slug', '?')
phase = state.get('current_phase', '?')
last_agent = state.get('last_agent', '?')

print(f"Feature: {tid}-{slug}")
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

# 6. Role memory (last 2 entries)
memory_path = f'.kiro/memory/{agent_name}.md'
if os.path.isfile(memory_path):
    with open(memory_path) as mf:
        mem_content = mf.read()
    import re as _re
    sections = _re.split(r'(?=^## )', mem_content, flags=_re.MULTILINE)
    sections = [s for s in sections if s.strip() and s.startswith('## ')]
    last_two = sections[-2:] if len(sections) >= 2 else sections
    if last_two:
        print()
        print("=== Role Memory (recent) ===")
        for sec in last_two:
            lines = sec.strip().splitlines()[:8]
            for line in lines:
                print(f"  {line}")
            print()

# 7. Terminology snapshot (top 5 terms)
terms = state.get('terminology', {})
if terms:
    print()
    print("=== Key Terms ===")
    for term, defn in list(terms.items())[:5]:
        print(f"  {term}: {defn}")
