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

  // light type checks on core scalar fields (only when present)
  for (const f of ['type', 'current_phase', 'change_name']) {
    if (state[f] != null && typeof state[f] !== 'string') problems.push(`\`${f}\` must be a string`);
  }

  return { ok: problems.length === 0, problems };
}
