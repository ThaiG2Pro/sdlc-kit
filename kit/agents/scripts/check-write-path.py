#!/usr/bin/env python3
"""
Shared preToolUse hook: validate fs_write paths against allowed prefixes.

Usage: echo '{"tool_input":{"path":"..."}}' | python3 check-write-path.py <agent_name>

Agent allowed paths:
  analyst:     specs/, docs/knowledge/
  architect:   specs/, docs/
  developer:   src/, apps/, prisma/, test/, tests/, specs/
  qa:          specs/, apps/cms/e2e/
  sdlc:        specs/

Exit 0 = allowed, Exit 2 = blocked
"""
import json, sys, os

AGENT_RULES = {
    "analyst": {
        "prefixes": ["specs/", "docs/knowledge/"],
        "exact": ["specs/.active-feature.json"],
    },
    "architect": {
        "prefixes": ["specs/", "docs/"],
        "exact": ["specs/.active-feature.json"],
    },
    "developer": {
        # Stack-agnostic source / test / migration / tooling dirs.
        "prefixes": [
            "src/", "app/", "apps/", "lib/", "pkg/", "internal/", "cmd/",
            "prisma/", "migrations/", "database/", "db/",
            "test/", "tests/", "spec/", "__tests__/",
            "docker/", "scripts/", "config/", "specs/", ".kiro/memory/", ".github/",
        ],
        # Common project-root manifests across stacks (Node, PHP, Go, Python, Rust, generic).
        "exact": [
            "specs/.active-feature.json",
            # Node / TS
            "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "nest-cli.json",
            # PHP
            "composer.json", "composer.lock", "artisan", "phpunit.xml", "phpunit.xml.dist",
            # Go
            "go.mod", "go.sum",
            # Python
            "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "requirements-dev.txt",
            "pytest.ini", "tox.ini", "Pipfile", "Pipfile.lock",
            # Rust
            "Cargo.toml", "Cargo.lock",
            # generic
            "Makefile", "Dockerfile", "README.md", "ROADMAP.md", "mise.toml", ".gitlab-ci.yml",
            ".env.example", ".env.sample", ".env.local.example",
            "docker-compose.yml", "docker-compose.yaml", "docker-compose.dev.yml",
            "docker-compose.local.yml", "docker-compose.override.yml", "compose.yml", "compose.yaml",
        ],
        # Config-file patterns (endswith) — covers *.config.ts, tsconfig.json, lint/format configs, etc.
        "suffixes": [
            ".config.ts", ".config.js", ".config.mjs", ".config.cjs",
            "tsconfig.json", "tsconfig.build.json", "jsconfig.json",
            ".prettierrc", ".prettierignore", ".eslintrc", ".eslintrc.js", ".eslintrc.json",
            "biome.json", "Dockerfile",
        ],
    },
    "qa": {
        "prefixes": ["specs/", ".kiro/memory/", "apps/cms/e2e/"],
        "exact": [],
    },
    "sdlc": {
        "prefixes": ["specs/", ".kiro/memory/"],
        "exact": ["specs/.active-feature.json"],
    },
    "onboarder": {
        "prefixes": [".kiro/context/"],
        "exact": [".kiro/context-map.json"],
    },
}


def normalize_path(path: str) -> str:
    """Convert absolute path to relative by stripping workspace root."""
    if not os.path.isabs(path):
        return path

    # Strategy 1: use cwd
    cwd = os.getcwd()
    if path.startswith(cwd + "/"):
        return path[len(cwd) + 1 :]

    # Strategy 2: find known segment markers in path (resolve to project-relative)
    markers = [
        "specs/", ".kiro/memory/", ".kiro/context/", ".kiro/context-map.json", "docs/",
        "src/", "app/", "apps/", "lib/", "pkg/", "internal/", "cmd/",
        "prisma/", "migrations/", "database/", "db/",
        "test/", "tests/", "spec/", "__tests__/", "docker/", "scripts/", "config/", ".github/",
    ]
    for marker in markers:
        idx = path.find("/" + marker)
        if idx != -1:
            return path[idx + 1 :]

    # Strategy 3 (fallback): treat as a project-root file → match by basename.
    # exact/suffix rules then decide. This is stack-agnostic (no hardcoded filenames).
    return os.path.basename(path)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: check-write-path.py <agent_name>\n")
        sys.exit(2)

    agent = sys.argv[1]
    if agent not in AGENT_RULES:
        sys.stderr.write(f"Unknown agent: {agent}\n")
        sys.exit(2)

    rules = AGENT_RULES[agent]
    data = json.load(sys.stdin)
    raw_path = data.get("tool_input", {}).get("path", "")
    path = normalize_path(raw_path)

    # Check exact matches
    if path in rules["exact"]:
        sys.exit(0)

    # Check prefix matches
    if any(path.startswith(p) for p in rules["prefixes"]):
        sys.exit(0)

    # Check suffix (config-file pattern) matches
    if any(path.endswith(s) for s in rules.get("suffixes", [])):
        sys.exit(0)

    sys.stderr.write(f"BLOCKED: {agent} cannot write to {path}")
    sys.exit(2)


if __name__ == "__main__":
    main()
