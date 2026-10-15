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
6. **Risk-Tiered Zero-Guess vs Sensible Defaults**:
   - **High-Risk (Zero-Guess)**: Security, Auth/RBAC, Financial/Billing, DB Schema, and Public API contracts strictly forbid guessing. Agents MUST halt and clarify via `bin/sdlc-ctx flex` or explicit question.
   - **Low-Risk (Sensible Defaults)**: Non-breaking internal utilities, UI styling details, or minor error wording use sensible conventions without halting the pipeline or paralyzing the human approver. Document choices in handoff.
7. **Semantic Disambiguation & Pragmatic Glossary**:
   - Overloaded or domain-specific terms (e.g. "active", "session", "cancel") must be explicitly registered in `context/glossary.md` or `_glossary.md`. Do NOT bikeshed over trivial common words.
8. **Anti-Boilerplate Intent Mirroring**:
   - Before any gate approval (S2, S3, S5), the agent must mirror back understanding: (a) In-Scope ACs, (b) Explicit Out-of-Scope, (c) Disambiguated terms, and (d) Top 2 Concrete Business Failure Scenarios. Generic infrastructure boilerplate ("network drops", "server dies") is strictly banned.
9. **Smart Inversion (Adversarial Self-Challenge)**:
   - Upstream agents are NOT blindly trusted. The Architect must challenge Analyst requirements for technical failure modes; QA must design destructive test scenarios beyond the happy-path spec.
