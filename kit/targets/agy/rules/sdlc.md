---
description: SDLC Kit core rules and security invariants
trigger: always_on
---

# SDLC Kit Rules

1. **Role Invariant**: Only the `developer` role/subagent may write or modify application code (`src/**`, `app/**`, `lib/**`, configuration). The orchestrator, analyst, architect, and qa roles are strictly read-only regarding production source code.
2. **Context Engine First**: State updates and context inspections MUST be performed via the SDLC Context Engine (MCP tools `sdlc_*` or CLI `bin/sdlc-ctx`), NOT by manually modifying baton files.
3. **Spec Lock Requirement**: No implementation (Phase S4) can begin without an approved SPEC LOCK (Phase S2) and DESIGN REVIEW (Phase S3).
4. **Traceability**: All code changes and test cases must link back to specific Acceptance Criteria IDs (`AC-*`).
5. **Clean Git State**: Changes should be isolated on dedicated feature branches or worktrees (`feat/<slug>`, `bugfix/<slug>`).
