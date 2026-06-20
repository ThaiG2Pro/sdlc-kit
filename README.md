# kiro-sdlc-kit

Reusable **Kiro IDE** SDLC kit, extracted from the GotIt Merchant APIs setup.
Drop a complete S1→S6 pipeline (orchestrator + 4 role agents + 24 skills + steering
rules + hooks) into any project with one command.

## What's inside

```
kit/
  agents/      6 Kiro agents (JSON config + MD prompt) + scripts/ + examples/
                 sdlc (ctrl+0) · analyst (1) · architect (2) · developer (3) · qa (4) · rtk
  skills/      24 skills — spec-auditor, cross-artifact-audit, qa-*, coding-standards, …
  steering/    8 always-on rules — sdlc-workflow, commit-policy, security, api-standards, …
  ai/          5 backend coding/sonar rule files
  hooks/       Kiro hook(s)
  settings/    lsp.json
bin/init.mjs   zero-dependency installer
```

`specs/` and `memory/` are **not** shipped — they are per-project workspace and are
scaffolded fresh (as repo-root dirs, symlinked from `.kiro/`) on init.

## Usage

From the target project root:

```bash
# via npx against the git repo
npx github:gotit/kiro-sdlc-kit          # or your GitLab remote

# or clone once, then run anywhere
node /path/to/kiro-sdlc-kit/bin/init.mjs            # into current dir
node /path/to/kiro-sdlc-kit/bin/init.mjs ../other   # into another project
```

Flags: `--force` (overwrite existing kit files; never touches your `specs/`/`memory/`),
`--yes` (accept defaults, no prompts).

The installer prompts for:

| Placeholder        | Used for                                                |
|--------------------|---------------------------------------------------------|
| `PROJECT_TITLE`    | Human-readable project name in agent prompts / steering |
| `LEGACY_REF_PATH`  | Path to a legacy/reference codebase (or `N/A`)          |

## After init

1. Open in Kiro — agents bind to `ctrl+0..4`.
2. **Customize for your stack** — the shipped steering/examples are NestJS + Prisma +
   voucher-domain samples. Edit `steering/api-standards.md`, `steering/stack-*.md`, and
   `ai/*` to match the new project. Examples under `agents/examples/` are reference
   samples; replace them as your project accumulates real specs.
3. Drive the pipeline: tell the `sdlc` agent `sdlc feature {slug} ticket {id}`.

## Model

A single source of truth: edit `kit/` here, re-run init (`--force`) in consumer projects
to pull updates. Because each project owns its copy after init, there is no submodule
coupling and no framework/project file mixing.
