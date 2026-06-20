# Architecture

> Architect/developer read this to respect layer boundaries and patterns. Replaces the
> old `structure.md`. Replace `<!-- TODO -->`.

## Style
<!-- TODO: e.g. Layered / Clean Architecture / DDD 4-layer / Modular monolith / Hexagonal. -->

## Layers & Boundaries
<!-- TODO: list layers and the dependency rule between them. Example:
- Domain: pure logic, no I/O imports
- Application: orchestrates domain, manages transactions
- Infrastructure: implements ports (DB/HTTP)
- Interface: controllers, validation, serializers
Rule: inner layers must not import outer layers.
-->

## Key Patterns
<!-- TODO: repository pattern, CQRS, ports/adapters, aggregates, etc. — or "None". -->

## Transaction & Consistency
<!-- TODO: where transactions live, locking strategy, atomic vs eventual. -->

## Directory Map
<!-- TODO: top-level source folders and what lives in each. -->

## Anti-patterns (do NOT do)
<!-- TODO: project-specific things to avoid. -->
