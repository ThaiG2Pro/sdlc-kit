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
        "prefixes": ["src/", "apps/", "prisma/", "test/", "tests/", "docker/", "specs/", ".kiro/memory/"],
        "exact": [
            "specs/.active-feature.json",
            "package.json",
            "package-lock.json",
            "tsconfig.json",
            "tsconfig.build.json",
            "vitest.config.ts",
            "nest-cli.json",
            ".env.example",
            ".env.node.example",
            "prisma.config.ts",
            "eslint.config.js",
            "eslint.config.mjs",
            ".prettierrc",
            ".prettierignore",
            "docker-compose.yml",
            "docker-compose.local.yml",
            "docker-compose.dev.yml",
            "docker-compose.node.yml",
            "Dockerfile",
            "Dockerfile.node",
            "README.md",
            "ROADMAP.md",
            ".gitlab-ci.yml",
            "mise.toml",
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
}


def normalize_path(path: str) -> str:
    """Convert absolute path to relative by stripping workspace root."""
    if not os.path.isabs(path):
        return path

    # Strategy 1: use cwd
    cwd = os.getcwd()
    if path.startswith(cwd + "/"):
        return path[len(cwd) + 1 :]

    # Strategy 2: find known segment markers in path
    markers = ["specs/", ".kiro/memory/", "docs/", "src/", "apps/", "prisma/", "test/", "tests/", "docker/"]
    for marker in markers:
        idx = path.find("/" + marker)
        if idx != -1:
            return path[idx + 1 :]

    # Strategy 3: check exact filenames at end of path
    basename_matches = [
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "tsconfig.build.json",
        "vitest.config.ts",
        "nest-cli.json",
        ".env.example",
        ".env.node.example",
        "eslint.config.js",
        "eslint.config.mjs",
        ".prettierrc",
        ".prettierignore",
        "docker-compose.yml",
        "docker-compose.local.yml",
        "docker-compose.dev.yml",
        "docker-compose.node.yml",
        "Dockerfile",
        "Dockerfile.node",
        "README.md",
        "ROADMAP.md",
        ".gitlab-ci.yml",
        "mise.toml",
    ]
    for bm in basename_matches:
        if path.endswith("/" + bm):
            return bm

    return path


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

    sys.stderr.write(f"BLOCKED: {agent} cannot write to {path}")
    sys.exit(2)


if __name__ == "__main__":
    main()
