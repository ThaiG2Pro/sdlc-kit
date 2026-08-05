#!/usr/bin/env node
// kiro-sdlc-kit — baton-compact: shrink a change's CPP baton back under its caps.
//
// WHY: the baton (_state.json, _decisions.jsonl, _glossary.md, _handoff.md, _progress.md) is read IN
// FULL by every role on every spawn, for the rest of the change — so anything that accumulates in it is
// a tax paid over and over. Measured across 8 live changes it had reached 34–155 KB per spawn (~9–39k
// tokens), 2-6× the entire agent prompt. Nothing ever compacted it: every writer's instruction was
// "append". This is the compaction step.
//
// It only does what is MECHANICALLY safe — never paraphrases, never guesses which prose is current:
//   _state.json       non-canonical keys (nothing reads them) → archived out; phase_history trimmed to
//                     the last N entries with the older ones folded into one digest line; over-long
//                     notes truncated at a sentence boundary.
//   _decisions.jsonl  an over-cap entry keeps its head + gains a `full` pointer; the complete text moves
//                     to _archive/ (never read by an agent, so it costs nothing per spawn).
//   _glossary.md      a row marked SUPERSEDED/HISTORICAL is dropped when a live row for the same term
//                     exists — its replacement is already there, so both were being paid for.
//   _handoff.md       REPORTED, not rewritten (which section is still current is a judgement call) —
//                     unless --handoff, which archives every `## ` section past the 5-section contract.
//
// Everything removed is written to <CHANGE_DIR>/_archive/ (underscore-prefixed → inside the baton
// write-fence, and no prompt tells any role to read it), so nothing is lost — and git has it anyway.
//
// Usage:
//   node .kiro/tools/baton-compact.mjs [projectDir] [--change <name>]            # dry run (default)
//   node .kiro/tools/baton-compact.mjs --change <name> --apply [--handoff]
//   node .kiro/tools/baton-compact.mjs --all                                     # every active change

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const KEEP_HISTORY = 8;      // recent phase_history entries kept verbatim
const NOTE_CAP = 200;        // one phase_history note
const DECISION_CAP = 240;    // one `decision` field
const REASONING_CAP = 120;
const HANDOFF_SECTIONS = 5;  // the CPP contract's section count

function readText(p) { try { return readFileSync(p, 'utf8'); } catch { return null; } }
function readJson(p) { try { return JSON.parse(readFileSync(p, 'utf8')); } catch { return null; } }
const bytes = (s) => (s ? Buffer.byteLength(s) : 0);

/**
 * Truncate at the last sentence/clause boundary before `cap`, so a note stays readable.
 * The ' …' marker is budgeted INSIDE cap — appending it afterwards would push every clipped field
 * a few chars past the cap, and the guard would then keep reporting an already-compacted entry.
 */
const ELLIPSIS = ' …';
function clip(s, cap) {
  if (s.length <= cap) return s;
  const room = cap - ELLIPSIS.length;
  const head = s.slice(0, room);
  const cut = Math.max(head.lastIndexOf('. '), head.lastIndexOf('; '), head.lastIndexOf(' — '));
  return (cut > room * 0.5 ? head.slice(0, cut + 1) : head.trimEnd()) + ELLIPSIS;
}

// ---- args ----
const argv = process.argv.slice(2);
let projectDir = '.', changeName = null, apply = false, doHandoff = false, all = false;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--change') changeName = argv[++i];
  else if (a === '--apply') apply = true;
  else if (a === '--handoff') doHandoff = true;
  else if (a === '--all') all = true;
  else if (a === '--dry-run') apply = false;
  else if (!a.startsWith('--')) projectDir = a;
  else { console.log(`  ✗ unknown flag ${a}`); process.exit(1); }
}
projectDir = resolve(projectDir);

const changesBase = join(projectDir, 'openspec', 'changes');
if (!existsSync(changesBase)) { console.log(`  ✗ no openspec/changes/ at ${projectDir}`); process.exit(1); }

function activeChanges() {
  return readdirSync(changesBase)
    .filter((n) => n !== 'archive' && existsSync(join(changesBase, n, '_state.json')))
    .map((n) => join(changesBase, n));
}
let targets;
if (all) targets = activeChanges();
else if (changeName) targets = [join(changesBase, changeName)];
else {
  const c = activeChanges().map((d) => [statSync(join(d, '_state.json')).mtimeMs, d]).sort((a, b) => b[0] - a[0]);
  if (!c.length) { console.log('  ✗ no active change with _state.json'); process.exit(1); }
  targets = [c[0][1]];
}

const BATON = ['_state.json', '_decisions.jsonl', '_glossary.md', '_handoff.md', '_progress.md'];
let grandBefore = 0, grandAfter = 0;

for (const changeDir of targets) {
  if (!existsSync(join(changeDir, '_state.json'))) { console.log(`  ✗ ${changeDir}: no _state.json`); continue; }
  const name = changeDir.split(/[\\/]/).pop();
  const before = BATON.reduce((n, f) => n + bytes(readText(join(changeDir, f))), 0);
  const notes = [];
  const writes = [];   // [absPath, text]
  const archiveDir = join(changeDir, '_archive');
  // Date only, and filename-safe — `last_updated` is a full ISO timestamp whose colons are illegal
  // in a Windows filename (Kiro runs there too).
  const stamp = String((readJson(join(changeDir, '_state.json')) || {}).last_updated || 'compact')
    .slice(0, 10).replace(/[^0-9A-Za-z-]/g, '-');
  const archive = (file, text) => writes.push([join(archiveDir, file), text]);

  // ── _state.json ────────────────────────────────────────────────────────────────────────────────
  const st = readJson(join(changeDir, '_state.json'));
  if (st) {
    const { CANONICAL_KEYS } = await import('./state-schema.mjs');
    const dropped = {};
    for (const k of Object.keys(st)) {
      if (k === '_comment' || CANONICAL_KEYS.has(k)) continue;
      dropped[k] = st[k];
      delete st[k];
    }
    const nDropped = Object.keys(dropped).length;
    if (nDropped) {
      notes.push(`_state.json: dropped ${nDropped} non-canonical key(s) (${bytes(JSON.stringify(dropped))} B) → ` +
        `_archive/: ${Object.keys(dropped).join(', ')}`);
      archive(`state-keys-${stamp}.json`, JSON.stringify(dropped, null, 2) + '\n');
    }

    if (Array.isArray(st.phase_history)) {
      const original = JSON.stringify(st.phase_history, null, 2) + '\n';
      let clipped = 0, folded = 0;
      // An entry is {phase, agent, date, note}. Roles invent other names for the prose field
      // (`result`, `summary`, `key_outcome`) and list artifacts that are already on disk — so
      // normalize by VALUE, not by a list of key names we happen to know.
      const ENTRY_KEYS = new Set(['phase', 'agent', 'date', 'note']);
      for (const e of st.phase_history) {
        if (!e || typeof e !== 'object') continue;
        for (const [k, v] of Object.entries(e)) {
          if (ENTRY_KEYS.has(k)) continue;
          // fold the longest stray prose field into `note` rather than dropping what it said
          if (typeof v === 'string' && v.length > (typeof e.note === 'string' ? e.note.length : 0)) e.note = v;
          delete e[k];
          folded++;
        }
        if (typeof e.note === 'string' && e.note.length > NOTE_CAP) { e.note = clip(e.note, NOTE_CAP); clipped++; }
      }
      if (clipped || folded) {
        archive(`phase-history-full-${stamp}.json`, original);
        notes.push(`_state.json: normalized phase_history — ${clipped} note(s) clipped to ${NOTE_CAP} chars` +
          (folded ? `, ${folded} stray field(s) folded into note/dropped` : '') + ` (full copy in _archive/)`);
      }
      if (st.phase_history.length > KEEP_HISTORY) {
        const old = st.phase_history.slice(0, st.phase_history.length - KEEP_HISTORY);
        const kept = st.phase_history.slice(-KEEP_HISTORY);
        const phases = [...new Set(old.map((e) => e?.phase).filter(Boolean))].join(',');
        st.phase_history = [
          { phase: old[0]?.phase || 'S1', agent: 'baton-compact', date: stamp,
            note: `${old.length} earlier entries (${phases}) folded — see _archive/ and git history.` },
          ...kept,
        ];
        archive(`phase-history-${stamp}.json`, JSON.stringify(old, null, 2) + '\n');
        notes.push(`_state.json: folded ${old.length} old phase_history entr${old.length === 1 ? 'y' : 'ies'} into 1 digest`);
      }
    }
    writes.push([join(changeDir, '_state.json'), JSON.stringify(st, null, 2) + '\n']);
  }

  // ── _decisions.jsonl ───────────────────────────────────────────────────────────────────────────
  const decTxt = readText(join(changeDir, '_decisions.jsonl'));
  if (decTxt) {
    const ptr = `_archive/decisions-${stamp}.jsonl`;
    const out = [], moved = [];
    for (const raw of decTxt.split('\n')) {
      const t = raw.trim();
      if (!t) continue;
      let o; try { o = JSON.parse(t); } catch { out.push(t); continue; }  // keep unparseable lines untouched
      // Clip by VALUE LENGTH, not by a list of field names: roles invent their own fat fields
      // (`source` at 741 B, `impact`, `root_cause`, `fixed`, …), so an allowlist misses most of the
      // weight. `decision` gets the larger budget; every other free-text field is a summary line.
      // Arrays of strings (`rejected`, `alternatives`, `refs`) are clipped element-wise.
      const capFor = (k) => (k === 'decision' ? DECISION_CAP : REASONING_CAP);
      let didClip = false;
      for (const [k, v] of Object.entries(o)) {
        if (k === 'full') continue;
        if (typeof v === 'string' && v.length > capFor(k)) { o[k] = clip(v, capFor(k)); didClip = true; }
        else if (Array.isArray(v)) {
          const next = v.map((x) => (typeof x === 'string' && x.length > REASONING_CAP ? clip(x, REASONING_CAP) : x));
          if (JSON.stringify(next) !== JSON.stringify(v)) { o[k] = next; didClip = true; }
        }
      }
      if (didClip) {
        moved.push(t);
        o.full = `${ptr}#${o.id || o.ts || ''}`;
      }
      out.push(JSON.stringify(o));
    }
    const count = out.length;
    if (count > 40)
      notes.push(`_decisions.jsonl: ${count} entries — a decision log records WHY something is not ` +
        `obvious from the artifacts; one entry per AC/per action turns it into a second copy of the spec. ` +
        `Not safe to prune mechanically: the next role has to stop adding them (see the role prompt).`);
    if (moved.length) {
      archive(`decisions-${stamp}.jsonl`, moved.join('\n') + '\n');
      const after = out.join('\n') + '\n';
      notes.push(`_decisions.jsonl: shortened ${moved.length} over-cap entr${moved.length === 1 ? 'y' : 'ies'} ` +
        `(${bytes(decTxt)} → ${bytes(after)} B); full text in ${ptr}`);
      writes.push([join(changeDir, '_decisions.jsonl'), after]);
    }
  }

  // ── _glossary.md — drop a SUPERSEDED row when a live row for the same term exists ───────────────
  const gloss = readText(join(changeDir, '_glossary.md'));
  if (gloss) {
    const lines = gloss.split('\n');
    // The term is whatever precedes the first annotation bracket — a real row reads
    // `| voucher_count **[SUPERSEDED … see `voucher_count [REWRITTEN]` below]** | …`, where the
    // brackets nest, so stripping `[...]` pairs leaves residue and the term never matches its
    // replacement. Cutting at the first `[` is what actually works.
    const termOf = (l) => (l.split('|')[1] || '').split('[')[0].replace(/\*\*|`/g, '').trim().toLowerCase();
    const isRow = (l) => l.trim().startsWith('|') && !/^\|[\s:|-]+\|?$/.test(l.trim());
    const dead = (l) => /SUPERSEDED|HISTORICAL|DO NOT IMPLEMENT/i.test(l);
    const live = new Set(lines.filter((l) => isRow(l) && !dead(l)).map(termOf));
    const kept = [], removed = [];
    lines.forEach((l, i) => {
      if (i > 0 && isRow(l) && dead(l) && live.has(termOf(l))) removed.push(l);
      else kept.push(l);
    });
    if (removed.length) {
      const after = kept.join('\n');
      archive(`glossary-superseded-${stamp}.md`, removed.join('\n') + '\n');
      notes.push(`_glossary.md: dropped ${removed.length} superseded row(s) whose replacement is already present ` +
        `(${bytes(gloss)} → ${bytes(after)} B)`);
      writes.push([join(changeDir, '_glossary.md'), after]);
    } else if (lines.some(dead)) {
      notes.push(`_glossary.md: has superseded marker(s) but no live row for the same term — the CURRENT ` +
        `definition has to replace the old one by hand (not safe to do mechanically).`);
    }
  }

  // ── _handoff.md — report by default; --handoff archives sections past the contract ─────────────
  const ho = readText(join(changeDir, '_handoff.md'));
  if (ho) {
    const idx = [];
    ho.split('\n').forEach((l, i) => { if (/^##\s/.test(l)) idx.push(i); });
    if (idx.length > HANDOFF_SECTIONS) {
      if (doHandoff) {
        const lines = ho.split('\n');
        const cut = idx[HANDOFF_SECTIONS];
        const tail = lines.slice(cut);
        const head = lines.slice(0, cut);
        head.push(`## Earlier rounds`, '', `${idx.length - HANDOFF_SECTIONS} section(s) from earlier rounds moved to ` +
          `\`_archive/handoff-${stamp}.md\` (and in git). A handoff carries what the NEXT phase needs — ` +
          `not the history of how we got here.`, '');
        const after = head.join('\n');
        archive(`handoff-${stamp}.md`, tail.join('\n'));
        notes.push(`_handoff.md: archived ${idx.length - HANDOFF_SECTIONS} extra section(s) (${bytes(ho)} → ${bytes(after)} B)`);
        writes.push([join(changeDir, '_handoff.md'), after]);
      } else {
        notes.push(`_handoff.md: ${idx.length} \`## \` sections vs the ${HANDOFF_SECTIONS}-section contract, ` +
          `${bytes(ho)} B — appended per round instead of replaced. Re-run with --handoff to archive the extras, ` +
          `or have the next role REWRITE it.`);
      }
    }
  }

  // ── report / write ─────────────────────────────────────────────────────────────────────────────
  console.log(`\n  ${name} — baton ${(before / 1024).toFixed(1)} KB`);
  if (!notes.length) { console.log('      ✓ nothing to compact'); grandBefore += before; grandAfter += before; continue; }
  for (const n of notes) console.log(`      · ${n}`);

  if (apply) {
    if (writes.some(([p]) => p.startsWith(archiveDir))) mkdirSync(archiveDir, { recursive: true });
    for (const [p, text] of writes) writeFileSync(p, text);
  }
  const after = apply ? BATON.reduce((n, f) => n + bytes(readText(join(changeDir, f))), 0)
    : BATON.reduce((n, f) => {
        const w = writes.find(([p]) => p === join(changeDir, f));
        return n + (w ? bytes(w[1]) : bytes(readText(join(changeDir, f))));
      }, 0);
  grandBefore += before; grandAfter += after;
  const pct = before ? Math.round((1 - after / before) * 100) : 0;
  console.log(`      ${apply ? '✓ applied' : '→ would be'} ${(before / 1024).toFixed(1)} → ${(after / 1024).toFixed(1)} KB ` +
    `(−${pct}%, ≈${Math.round((before - after) / 4000)}k tokens saved per spawn)`);
}

if (targets.length > 1) {
  const pct = grandBefore ? Math.round((1 - grandAfter / grandBefore) * 100) : 0;
  console.log(`\n  TOTAL ${(grandBefore / 1024).toFixed(1)} → ${(grandAfter / 1024).toFixed(1)} KB (−${pct}%)`);
}
if (!apply) console.log('\n  (dry run — add --apply to write; removed content goes to <CHANGE_DIR>/_archive/)');
