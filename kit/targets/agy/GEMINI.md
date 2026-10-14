# {{PROJECT_TITLE}} — SDLC Kit (Antigravity / agy)

This project runs the **SDLC Kit** on Google Antigravity (`agy`) backed by the **SDLC Context Engine** (persistent MCP Server `bin/sdlc-mcp` or fast CLI `bin/sdlc-ctx`).

The orchestrator drives the S1→S6 lifecycle directly or spawns role subagents per phase, holding execution at deterministic gates for human review.

---

## 1. Quick Start & Execution Modes

You can run the SDLC Kit in Antigravity in two primary ways:

### A. Full Flow (Feature · Change Request · Rebuild: S1 → S6)
When the user asks to implement a feature, rebuild a module, or fulfill a change request:
1. Initialize the change in the Context Engine:
   - Via MCP: `sdlc_manage_lifecycle(action="init", change_id="<slug>", slug="<slug>")`
   - Or CLI: `bin/sdlc-ctx change init --change "<slug>" --slug "<slug>"`
2. Drive through the 6 phases:
   - **S1 (Requirements Intake)** & **S2 (Functional Spec)**: Invoke `Analyst` subagent.
   - **Gate S2 (SPEC LOCK)**: Run audit, prompt user via `ask_question` for approval.
   - **S3 (Technical Design)**: Invoke `Architect` subagent.
   - **Gate S3 (ARCH LOCK)**: Run audit, prompt user via `ask_question` for approval.
   - **S4 (Build / Implementation)**: Invoke `Developer` subagent.
   - **Gate S4 (DEV COMPLETE)**: Verify tests and task completion.
   - **S5 (Quality Assurance)**: Invoke `QA` subagent.
   - **Gate S5 (QA PASS / GO)**: Review verification matrix and open bugs.
   - **S6 (Release & Archive)**: Invoke `Developer` to archive specs and finalize release notes.

### B. Fast-Track Flow (Bugfix · Hotfix)
Skips S1–S3; goes straight to S4 (Developer builds fix + regression test) → S5 (QA verifies fix) → S6 (Archive).
- Via MCP: `sdlc_manage_lifecycle(action="init", change_id="<slug>", slug="<slug>", work_type="bugfix")`

---

## 2. Core Security Invariant

> [!IMPORTANT]
> **Only the `developer` subagent writes product code.**
> - The **orchestrator** and the **analyst**, **architect**, and **qa** subagents treat production source code (`src/**`, `app/**`, `lib/**`) as read-only.
> - Their outputs are strictly specifications, ADRs, designs, and test scenarios.
> - Code changes are performed exclusively by the Developer during Phase S4.

---

## 3. High-Performance Context Engine Integration

Instead of repeatedly reading dozens of kilobytes of markdown baton files (`_handoff.md`, `_state.json`), interact with the database via persistent **MCP Tools** (preferred, ~1.5ms) or **Fast CLI** (`bin/sdlc-ctx`):

### Native MCP Tools (Registered in `mcp_config.json`)
1. **`sdlc_manage_lifecycle`**: Init change, transition phases (`S1`...`S6`), inspect and pass gates.
2. **`sdlc_record_spec_bundle`**: Batch insert requirements (`ACs`), edge cases, STRIDE threats, commit spec lock.
3. **`sdlc_get_work_context`**: Fetch the complete, consolidated work context for the active task (ACs + ADRs + schemas + risky areas) in **1 call**.
4. **`sdlc_submit_task_result`**: Complete a task, record build logs, deviations, and git commits.
5. **`sdlc_audit_and_verify`**: Inspect QA audit context, bulk create test scenarios, record test execution outcomes.
6. **`sdlc_flex_patch`**: In-flight amendment engine (patch schema, insert urgent task, supersede ADR, preview impact).
7. **`sdlc_inspect_query`**: Swiss Army Knife for ad-hoc inspection (FTS5 search across knowledge/ADRs, inspect any of the 18 tables, or run read-only `safe_sql`).

### Fast CLI Equivalents (`bin/sdlc-ctx`)
```bash
bin/sdlc-ctx change get --change <id>
bin/sdlc-ctx task inspect-work-context --change <id>
bin/sdlc-ctx spec add-req-batch --change <id> --file <reqs.json>
bin/sdlc-ctx gate inspect --change <id> --gate <gate_name>
bin/sdlc-ctx gate pass --change <id> --gate <gate_name> --approver human
bin/sdlc-ctx sync export --change <id> --dir ./openspec/changes/<id>
```

---

## 4. Subagent Dispatch in Antigravity

When driving phases S1–S5, the orchestrator spawns role subagents using `invoke_subagent`.

### Dispatch Pattern:
```json
{
  "Subagents": [
    {
      "TypeName": "self",
      "Role": "Analyst",
      "Prompt": "You are the Analyst role for change <change_id>. Read the role instructions at .agents/agents/analyst.md. Query the Context Engine for change details, perform assumption/edge-case/STRIDE analysis, record requirements via sdlc_record_spec_bundle, and commit spec lock."
    }
  ]
}
```

### Role Mapping:
- **`Analyst`** (`.agents/agents/analyst.md`): S1 Intake + S2 Functional Spec. Outputs ACs/BRs/INTs into `spec_requirements`.
- **`Architect`** (`.agents/agents/architect.md`): S3 Technical Design. Outputs `design.md`, `openapi.yaml`, and `tasks.md`.
- **`Developer`** (`.agents/agents/developer.md`): S4 Build & S6 Release. Implements code, unit tests, and records task completions.
- **`QA`** (`.agents/agents/qa.md`): S5 Verification. Builds test matrix, runs tests, logs bugs, gives GO/NO-GO verdict.
- **`Onboarder`** (`.agents/agents/onboarder.md`): Repo onboarding & scanning (drafts `./context/*.md`).
- **`Intake`** (`.agents/agents/intake.md`): Ticket & Figma intake into `docs/extra-docs/`.

---

## 5. Interactive Gate Reviews

At each gate, the orchestrator executes the deterministic gate inspection (`sdlc_manage_lifecycle(action="gate_inspect", ...)`).
If `can_pass == true`, use `ask_question` to present the summary to the user for formal approval before transitioning to the next phase:

```json
{
  "questions": [
    {
      "question": "Gate SPEC LOCK passed verification. Ready to advance to Phase S3 (Technical Design)?",
      "options": [
        "(Recommended) Approve and transition to Phase S3",
        "Request amendments to requirements",
        "Inspect requirements in detail"
      ]
    }
  ]
}
```

---

## 6. Project Context — Surgical Reads

Each role reads only the context files relevant to its domain:

| File | Analyst | Architect | Developer | QA | Note |
|---|:-:|:-:|:-:|:-:|---|
| `context/project.md` | ✓ | – | – | – | Project domain and overview |
| `context/glossary.md` | ✓ | – | – | – | Domain glossary (or query via `sdlc_inspect_query`) |
| `context/stack.md` | – | ✓ | ✓ | ✓ | Actual build/test/lint commands |
| `context/conventions.md` | – | ✓ | ✓ | ✓ | Code conventions and styles |
| `context/architecture.md` | – | ✓ | ✓ | – | System layout & integration points |
| `context/legacy-ref.md` | ◐ | ◐ | ◐ | ◐ | ◐ = only if touching legacy code |
| `.agents/steering/security.md` | ✓ | ✓ | – | – | Security policies & STRIDE rules |
