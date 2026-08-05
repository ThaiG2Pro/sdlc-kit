// state-schema — deterministic canonical-shape validator for a change's _state.json.
//
// WHY: the canonical shape of _state.json (the keys the guards READ) used to live only as a comment
// in state-template.json + implicit read-expectations in pipeline-guard / cpp-guard. Nothing validated
// it at WRITE time, so the orchestrator (raw Write) or a blind `state-set` dot-path could persist a
// non-canonical shape — most commonly rich per-gate objects merged INTO `gates` (gates.SPEC_LOCK={…},
// gates.S5={…}) instead of canonical `gates:{ "<PHASE>":"passed" }`, or `convergence` omitted at
// rigor=full. The guards only noticed at the NEXT gate (reactive) — and when the drift sat on a terminal
// gate it slipped through entirely. This turns the canonical contract into one function so BOTH writers
// (state-set: refuse to write) and the guard (STEP 0: refuse to operate) reject drift the moment it appears.
//
// Canonical contract (only these shapes are legal; everything else is drift):
//   gates        — keys are base phase IDs (S1..Sn); values are STRINGS ("passed"/"failed"/…).
//                  Rich per-gate audit data lives in a SEPARATE key (gate_audit / gate_details), never here.
//   convergence  — keys are base phase IDs; each value is { stable:<int>, rounds:<int> }.
//   phases       — (if present) an array of base phase-ID strings.
//   type / current_phase / change_name — strings (current_phase may carry a sub-phase suffix e.g. "S3-B").

const PHASE_ID = /^S[1-9]\d*$/; // base phase id: S1, S2, … (no sub-phase suffix — gates/convergence key on base)

// ── Key allowlist + size caps (the anti-bloat contract) ────────────────────────────────────────
//
// WHY: _state.json is read IN FULL by every role on every spawn, forever. Validating only the SHAPE
// of keys we happened to know about let it become a document store: measured across 8 live changes,
// 4.8–42 KB per file was keys NO guard and NO prompt ever reads — `staging_evidence` (10.7 KB),
// `regression` (6.6 KB), `gate_audit` (5.5 KB), `s3_outputs`, `resolved_at_s3`, `rigor_downgrade`,
// `s4_checkpoint_2`, … A role wrote its phase report INTO the baton and every later spawn paid for it.
// So the contract is now closed: these keys and no others. Detail goes to the file that is read
// SELECTIVELY (_handoff.md, the phase report, memory/<role>/), never to the one read unconditionally.

/** Every key legal in a canonical _state.json. Read by a guard, by the orchestrator, or by a prompt. */
export const CANONICAL_KEYS = new Set([
  'change_name', 'feature_slug', 'ticket_id', 'type', 'rigor', 'scope', 'test_scope',
  'current_phase', 'phases', 'gates', 'convergence', 'memory_writeback', 'deploy_status',
  'phase_history', 'next_action', 'last_updated', 'last_agent', 'testcase_export', 'isolation',
]);

/** Keys seen in the wild that DUPLICATE another baton file — named so the error says where to put it. */
export const RELOCATED_KEYS = {
  terminology: '_glossary.md (it is the glossary — state was carrying a second copy)',
  active_concerns: 'next_action.watch_items (same thing, one copy is enough)',
  gate_audit: '_progress.md (gate outcomes belong in the progress table)',
  gate_details: '_progress.md',
  staging_evidence: 'the phase report (dev-test-report.md / qa-report.md)',
  regression: 'the phase report + one _decisions.jsonl line',
  s3_outputs: 'nothing — design.md/tasks.md on disk already prove it',
  scope_rationale: '_handoff.md (one line)',
  rigor_downgrade: '_handoff.md (one line)',
  resolved_at_s3: '_decisions.jsonl',
  spec_lock: 'gates.S2',
  blocker: 'next_action.blocker',
  change_dir: 'nothing — it is the directory the file lives in',
  skipped_phases: 'nothing — derivable from `phases` + `type`',
};

/** Size ceilings. Every one of these was exceeded by a real change before they existed. */
export const CAPS = {
  noteChars: 200,            // one phase_history note — 1-2 sentences
  historyEntryChars: 400,    // one whole phase_history entry, serialized
  historyEntries: 12,        // S1..S6 + fix rounds; past this, compact
  nextActionChars: 900,      // incl. priority_reading + watch_items
  totalBytes: 8000,          // the whole file — every spawn pays this
};

/**
 * Non-blocking bloat/drift audit, separate from validateState's shape contract.
 * Returns one warning per problem, each naming the key and where its content belongs instead.
 * Callers decide severity: state-set REJECTS warnings caused by the write in hand (so drift can
 * never be introduced) and only PRINTS pre-existing ones (so a change mid-flight never deadlocks);
 * pipeline-guard only ever prints.
 * @returns {{warnings:string[], offendingKeys:string[]}}
 */
export function auditState(state) {
  const warnings = [], offendingKeys = [];
  if (!state || typeof state !== 'object' || Array.isArray(state)) return { warnings, offendingKeys };

  for (const k of Object.keys(state)) {
    if (k === '_comment' || CANONICAL_KEYS.has(k)) continue;
    offendingKeys.push(k);
    const bytes = JSON.stringify(state[k]).length;
    const where = RELOCATED_KEYS[k];
    warnings.push(`\`${k}\` (${bytes} B) is not a canonical _state.json key — nothing reads it, but ` +
      `every future spawn reads it. Put it in ${where || '_handoff.md or the phase report'}; then ` +
      `\`--unset ${k}\`.`);
  }

  const h = state.phase_history;
  if (Array.isArray(h)) {
    if (h.length > CAPS.historyEntries) {
      offendingKeys.push('phase_history');
      warnings.push(`phase_history has ${h.length} entries (cap ${CAPS.historyEntries}) — run ` +
        `baton-compact.mjs to fold the oldest into one digest line.`);
    }
    h.forEach((e, i) => {
      const n = e && typeof e.note === 'string' ? e.note.length : 0;
      if (n > CAPS.noteChars) {
        offendingKeys.push('phase_history');
        warnings.push(`phase_history[${i}].note is ${n} chars (cap ${CAPS.noteChars}) — 1-2 sentences; ` +
          `detail goes in _handoff.md / the phase report, which are read selectively.`);
      }
      const b = JSON.stringify(e ?? null).length;
      if (b > CAPS.historyEntryChars) {
        offendingKeys.push('phase_history');
        warnings.push(`phase_history[${i}] is ${b} B (cap ${CAPS.historyEntryChars}) — keep it to ` +
          `{phase, agent, date, note}; artifacts are on disk, no need to list them.`);
      }
    });
  }

  if (state.next_action != null) {
    const b = JSON.stringify(state.next_action).length;
    if (b > CAPS.nextActionChars) {
      offendingKeys.push('next_action');
      warnings.push(`next_action is ${b} B (cap ${CAPS.nextActionChars}) — priority_reading is a list of ` +
        `file names with a short why, not the reasoning itself.`);
    }
  }

  const total = JSON.stringify(state).length;
  if (total > CAPS.totalBytes) {
    warnings.push(`_state.json is ${total} B (cap ${CAPS.totalBytes}) — this is re-read on EVERY spawn ` +
      `for the rest of the change. Run baton-compact.mjs.`);
  }

  return { warnings, offendingKeys: [...new Set(offendingKeys)] };
}

/**
 * Validate the canonical shape of a parsed _state.json object.
 * Only validates keys that are PRESENT — a fresh/NEW state with no gates/convergence is legal.
 * @returns {{ok:boolean, problems:string[]}}
 */
export function validateState(state) {
  if (!state || typeof state !== 'object' || Array.isArray(state)) {
    return { ok: false, problems: ['_state.json is not a JSON object'] };
  }
  const problems = [];

  // gates: { "<PHASE>": "<string>" }
  if (state.gates != null) {
    const g = state.gates;
    if (typeof g !== 'object' || Array.isArray(g)) {
      problems.push('`gates` must be an object keyed by phase ID, e.g. {"S2":"passed"}');
    } else {
      for (const [k, v] of Object.entries(g)) {
        if (!PHASE_ID.test(k))
          problems.push(`gates.${k}: key is not a phase ID — gate-name keys (SPEC_LOCK/DESIGN_REVIEW/…) and rich audit data belong in a separate key like \`gate_audit\`, not \`gates\``);
        if (typeof v !== 'string')
          problems.push(`gates.${k}: value must be a string like "passed" (got ${Array.isArray(v) ? 'array' : typeof v}) — the guard reads \`gates.<phase> === "passed"\`; move rich data to \`gate_audit\``);
        else if (!v.trim())
          problems.push(`gates.${k}: value is an empty string`);
      }
    }
  }

  // convergence: { "<PHASE>": { stable:<int>, rounds:<int> } }
  if (state.convergence != null) {
    const c = state.convergence;
    if (typeof c !== 'object' || Array.isArray(c)) {
      problems.push('`convergence` must be an object keyed by phase ID, e.g. {"S2":{"stable":3,"rounds":3}}');
    } else {
      for (const [k, v] of Object.entries(c)) {
        if (!PHASE_ID.test(k)) problems.push(`convergence.${k}: key is not a phase ID`);
        if (!v || typeof v !== 'object' || Array.isArray(v)) {
          problems.push(`convergence.${k}: value must be { "stable":<int>, "rounds":<int> }`);
        } else {
          if (!Number.isInteger(v.stable)) problems.push(`convergence.${k}.stable must be an integer`);
          if (!Number.isInteger(v.rounds)) problems.push(`convergence.${k}.rounds must be an integer`);
        }
      }
    }
  }

  // phases: array of phase-ID strings
  if (state.phases != null) {
    if (!Array.isArray(state.phases)) {
      problems.push('`phases` must be an array of phase-ID strings, e.g. ["S1","S2",…]');
    } else {
      state.phases.forEach((p, i) => {
        if (typeof p !== 'string' || !PHASE_ID.test(p))
          problems.push(`phases[${i}] = ${JSON.stringify(p)} is not a phase-ID string (e.g. "S2")`);
      });
    }
  }

  // memory_writeback: { "<role>": "appended" | "nothing-reusable" } — the per-phase role-memory
  // DECISION flag cpp-guard reads at each gate (analyst/architect/developer/qa). Value is an enum.
  if (state.memory_writeback != null) {
    const m = state.memory_writeback;
    if (typeof m !== 'object' || Array.isArray(m)) {
      problems.push('`memory_writeback` must be an object keyed by role, e.g. {"developer":"appended"}');
    } else {
      for (const [k, v] of Object.entries(m)) {
        if (v !== 'appended' && v !== 'nothing-reusable')
          problems.push(`memory_writeback.${k}: value must be "appended" or "nothing-reusable" (got ${JSON.stringify(v)})`);
      }
    }
  }

  // deploy_status: { "<env>": "pending" | "pass" | "fail" } — OPTIONAL, NEVER gated. A breadcrumb
  // for the real-world promotion that happens AFTER `openspec archive` (S6) — e.g. dev/stg/master or
  // whatever env names the project's CI/CD uses. Archive already ran by the time this fills in, so
  // nothing in pipeline-guard/cpp-guard reads this key or blocks on it; it only lets a bug found
  // downstream be traced back to the change that archived it, instead of relying on memory. Set later
  // via state-set, e.g. `--set deploy_status.stg=fail`.
  if (state.deploy_status != null) {
    const d = state.deploy_status;
    if (typeof d !== 'object' || Array.isArray(d)) {
      problems.push('`deploy_status` must be an object keyed by environment name, e.g. {"dev":"pass","stg":"pending"}');
    } else {
      for (const [k, v] of Object.entries(d)) {
        if (v !== 'pending' && v !== 'pass' && v !== 'fail')
          problems.push(`deploy_status.${k}: value must be "pending", "pass", or "fail" (got ${JSON.stringify(v)})`);
      }
    }
  }

  // scope: "tiny" | "standard" — OPTIONAL, independent of type/rigor. Shrinks how much a phase WRITES
  // (condensed design.md, index-first memory reads, affected-tests-only at intermediate checkpoints),
  // never which phases/gates run. Default is "standard" when unset — absence is legal, never inferred as tiny.
  if (state.scope != null && state.scope !== 'tiny' && state.scope !== 'standard') {
    problems.push(`\`scope\` must be "tiny" or "standard" (got ${JSON.stringify(state.scope)})`);
  }

  // test_scope: "module" | "full" — OPTIONAL. Controls how wide the developer S4 FINAL checkpoint
  // and the QA S5 independent re-run reach (both must match). Default resolves from rigor when unset
  // (full rigor → full, lite rigor → module) — absence is legal, never inferred as either value.
  if (state.test_scope != null && state.test_scope !== 'module' && state.test_scope !== 'full') {
    problems.push(`\`test_scope\` must be "module" or "full" (got ${JSON.stringify(state.test_scope)})`);
  }

  // light type checks on core scalar fields (only when present)
  for (const f of ['type', 'current_phase', 'change_name']) {
    if (state[f] != null && typeof state[f] !== 'string') problems.push(`\`${f}\` must be a string`);
  }

  return { ok: problems.length === 0, problems };
}
