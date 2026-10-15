# Domain Glossary (Ubiquitous Language)

> All agents read this to prevent **Semantic Drift** and the illusion of shared vocabulary.
> One row per domain term. 
> 
> **Pragmatic Rules (Anti-Bikeshedding):**
> 1. Only register terms that are **domain-specific**, **overloaded**, or **have caused ambiguity** (e.g., "Active", "Session", "Role", "Sync").
> 2. Do NOT add common generic programming terms (e.g., "function", "variable", "database").
> 3. Each definition must be actionable, concise (≤ 160 characters), and specify what is IN and OUT of that definition.

| Term | Canonical Definition | Boundary / Out-of-Scope / Aliases |
|------|----------------------|-----------------------------------|
| Change | An atomic unit of SDLC work (feature/bugfix/rebuild) tracked by `sdlc-ctx` | Aliased as `change_id`, `slug`. Not a git branch name. |
| Spec Lock | Gate S2 milestone where all ACs are finalized, tagged, and immutable | Unresolved questions must be tagged `[ASSUMED]` or resolved. |
| Zero-Guess | Invariant forbidding assumptions on High-Risk domains (Auth/Money/Schema) | Does not apply to low-risk UI cosmetics (use Sensible Defaults). |
| Intent Mirroring | Structured reflection of understanding before gate sign-off | Includes In-Scope, Out-of-Scope, Term Definitions, Top 2 Risks. |
| Triangulation | QA verification by comparing Spec vs Design vs Code independently | Prevents confirming bugs already baked into specs. |
