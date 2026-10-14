-- ============================================================================
-- SDLC Context Engine - Complete Database Schema (18 Tables & FTS5)
-- Conforming to: sdlc-context-engine-spec.md
-- ============================================================================

-- PERFORMANCE & INTEGRITY PRAGMAS
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;

-- DOMAIN 1: CHANGE & PIPELINE STATE MACHINE
CREATE TABLE IF NOT EXISTS change_state (
    change_id TEXT PRIMARY KEY,
    ticket_id TEXT,
    slug TEXT NOT NULL,
    work_type TEXT NOT NULL CHECK(work_type IN ('feature', 'cr', 'rebuild', 'bugfix', 'hotfix', 'spike', 'tech-debt')),
    rigor TEXT NOT NULL CHECK(rigor IN ('full', 'lite')),
    scope TEXT NOT NULL DEFAULT 'standard' CHECK(scope IN ('tiny', 'standard')),
    test_scope TEXT NOT NULL DEFAULT 'module' CHECK(test_scope IN ('module', 'full')),
    current_phase TEXT NOT NULL DEFAULT 'S1',
    overall_status TEXT NOT NULL DEFAULT 'IN_PROGRESS' CHECK(overall_status IN ('IN_PROGRESS', 'BLOCKED', 'READY_FOR_RELEASE', 'ARCHIVED')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- View alias: enables queries against `changes` to resolve to `change_state` (supports both `id` and `change_id`)
CREATE VIEW IF NOT EXISTS changes AS SELECT change_id AS id, * FROM change_state;

CREATE TABLE IF NOT EXISTS gate_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    gate_name TEXT NOT NULL CHECK(gate_name IN ('SPEC_LOCK', 'DESIGN_REVIEW', 'BUILD', 'QA', 'RELEASE')),
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'BLOCKED', 'PASSED', 'SKIPPED')),
    approver TEXT NOT NULL,
    override_reason TEXT,
    passed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blockers (
    blocker_id TEXT PRIMARY KEY,        -- BLK-01, BLK-02...
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    phase TEXT NOT NULL,
    raised_by TEXT NOT NULL,
    question TEXT NOT NULL,
    options_json TEXT,                  -- Array of suggested options
    selected_option TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'ANSWERED', 'RESOLVED')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);

-- DOMAIN 2: BATON CONTEXT PROTOCOL
CREATE TABLE IF NOT EXISTS phase_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    phase TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('IN_PROGRESS', 'DONE', 'BLOCKED')),
    agent TEXT NOT NULL,
    summary_note TEXT NOT NULL,
    next_action TEXT,
    logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS phase_handoff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    from_phase TEXT NOT NULL,
    to_phase TEXT NOT NULL,
    author_role TEXT NOT NULL,
    key_decisions TEXT NOT NULL,        -- JSON array of strings
    contentious_points TEXT,           -- JSON array of strings
    implicit_assumptions TEXT,         -- JSON array of strings
    risky_areas TEXT,                  -- JSON array of strings
    reading_order TEXT NOT NULL,       -- JSON array of paths
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_ledger (
    decision_id TEXT PRIMARY KEY,       -- DEC-001, ADR-001...
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    type TEXT NOT NULL CHECK(type IN ('design', 'implementation', 'deviation', 'architectural')),
    decision TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    rejected_alternatives TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'SUPERSEDED', 'DEPRECATED')),
    superseded_by TEXT,
    phase TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS change_glossary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    term TEXT NOT NULL,
    definition TEXT NOT NULL,
    introduced_phase TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'DEPRECATED')),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(change_id, term)
);

CREATE TABLE IF NOT EXISTS cross_spec_bridge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    exported_service TEXT NOT NULL,
    endpoint_or_symbol TEXT NOT NULL,
    contract_summary TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK(role IN ('analyst', 'architect', 'developer', 'qa', 'intake', 'onboarder')),
    change_id TEXT NOT NULL,
    domain_tag TEXT NOT NULL,
    lesson_learned TEXT NOT NULL,
    reusable_pattern TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- DOMAIN 3: INTAKE & UI SPECIFICATION
CREATE TABLE IF NOT EXISTS intake_packages (
    ticket_id TEXT PRIMARY KEY,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    raw_status TEXT,
    assignee TEXT,
    figma_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intake_ui_screens (
    screen_id TEXT PRIMARY KEY,         -- SCR-LOGIN, SCR-PROFILE...
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    screen_name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    route TEXT,
    figma_image_path TEXT,
    figma_url TEXT,
    layout_spec TEXT NOT NULL,          -- Markdown/text regions
    components_json TEXT NOT NULL,      -- Array of {type, label, states: []}
    data_fields_json TEXT NOT NULL,     -- Array of {field, type, validation}
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- DOMAIN 4: PROJECT KNOWLEDGE & DRIFT
CREATE TABLE IF NOT EXISTS project_knowledge (
    topic TEXT PRIMARY KEY,             -- 'stack', 'conventions', 'architecture', 'glossary', 'legacy-ref'
    content_json TEXT NOT NULL,         -- Structured key-value / sections
    version INTEGER NOT NULL DEFAULT 1,
    last_updated_by TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- FTS5 table for fast local search
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    topic,
    title,
    body_text
);

-- DOMAIN 5: REQUIREMENTS & STRIDE (Analyst S1 / S2)
CREATE TABLE IF NOT EXISTS spec_requirements (
    req_id TEXT PRIMARY KEY,            -- AC-123-001, BR-123-001, INT-123-001
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    type TEXT NOT NULL CHECK(type IN ('AC', 'BR', 'INT')),
    tag TEXT NOT NULL CHECK(tag IN ('CONFIRMED', 'ASSUMED', 'MISSING', 'UNCLEAR')),
    title TEXT NOT NULL,
    given_when_then TEXT,
    status TEXT NOT NULL DEFAULT 'SPECIFIED' CHECK(status IN ('DRAFT', 'SPECIFIED', 'IMPLEMENTED', 'VERIFIED_PASS', 'VERIFIED_FAIL', 'DEPRECATED')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- View alias: enables queries against `requirements` to resolve to `spec_requirements`
CREATE VIEW IF NOT EXISTS requirements AS SELECT req_id AS id, * FROM spec_requirements;

CREATE TABLE IF NOT EXISTS spec_edge_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    category TEXT NOT NULL CHECK(category IN ('boundary', 'state_transition', 'concurrency', 'data_integrity', 'permission', 'integration', 'ui_ux')),
    scenario TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    mapped_ac_id TEXT REFERENCES spec_requirements(req_id)
);

CREATE TABLE IF NOT EXISTS spec_clarifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    question TEXT NOT NULL,
    impact TEXT NOT NULL,
    proposed_guess TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'ANSWERED', 'APPLIED')),
    answer TEXT
);

CREATE TABLE IF NOT EXISTS spec_stride_threats (
    threat_id TEXT PRIMARY KEY,         -- THR-001, THR-002...
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    category TEXT NOT NULL CHECK(category IN ('Spoofing', 'Tampering', 'Repudiation', 'Information_Disclosure', 'Denial_of_Service', 'Elevation_of_Privilege')),
    description TEXT NOT NULL,
    mitigation_strategy TEXT NOT NULL,
    mapped_ac_id TEXT REFERENCES spec_requirements(req_id)
);

-- DOMAIN 6: DESIGN & ARCHITECTURE (Architect S3)
CREATE TABLE IF NOT EXISTS design_schemas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    table_name TEXT NOT NULL,
    columns_json TEXT NOT NULL,         -- Array of {name, type, nullable, default}
    indexes_json TEXT,                  -- Array of {name, columns, unique}
    migration_notes TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'REVISED', 'DROPPED')),
    UNIQUE(change_id, table_name)
);

CREATE TABLE IF NOT EXISTS design_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    method TEXT NOT NULL CHECK(method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')),
    path TEXT NOT NULL,
    request_schema_json TEXT,
    response_schema_json TEXT,
    error_codes_json TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'SUPERSEDED')),
    UNIQUE(change_id, method, path)
);

CREATE TABLE IF NOT EXISTS design_components (
    component_id TEXT PRIMARY KEY,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    name TEXT NOT NULL,
    layer TEXT NOT NULL CHECK(layer IN ('shared', 'domain', 'application', 'interface', 'middleware')),
    responsibility TEXT NOT NULL,
    dependencies_json TEXT              -- Array of component names
);

-- DOMAIN 7: TASK GRAPH & IMPLEMENTATION (Developer S4 / S6)
CREATE TABLE IF NOT EXISTS task_graph (
    task_id TEXT PRIMARY KEY,           -- T1, T2, T2.1, T3...
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    target_file TEXT NOT NULL,
    mapped_acs_json TEXT NOT NULL,      -- Array of req_id: ["AC-123-001"]
    depends_on_json TEXT,               -- Array of task_id: ["T1"]
    is_checkpoint BOOLEAN NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'TODO' CHECK(status IN ('TODO', 'IN_PROGRESS', 'COMPLETED', 'NEEDS_REVISION', 'BLOCKED')),
    test_command_run TEXT,
    test_output TEXT,
    exit_code INTEGER,
    completed_at DATETIME
);

-- View alias: enables queries against `tasks` to resolve to `task_graph`
CREATE VIEW IF NOT EXISTS tasks AS SELECT task_id AS id, * FROM task_graph;

CREATE TABLE IF NOT EXISTS dev_deviations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    task_id TEXT NOT NULL REFERENCES task_graph(task_id),
    deviation_type TEXT NOT NULL CHECK(deviation_type IN ('minor', 'major')),
    description TEXT NOT NULL,
    impact TEXT NOT NULL,
    is_approved BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS release_plans (
    change_id TEXT PRIMARY KEY REFERENCES change_state(change_id),
    migration_steps TEXT NOT NULL,
    rollback_plan TEXT NOT NULL,
    post_deploy_checks TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'APPROVED', 'DEPLOYED'))
);

-- DOMAIN 8: QA, VERIFICATIONS & BUGS (S4-FIX / S5)
CREATE TABLE IF NOT EXISTS qa_test_scenarios (
    scenario_id TEXT PRIMARY KEY,       -- TC-001, TC-002...
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    mapped_ac_id TEXT NOT NULL REFERENCES spec_requirements(req_id),
    title TEXT NOT NULL,
    steps TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    priority TEXT NOT NULL CHECK(priority IN ('P0', 'P1', 'P2')),
    execution_status TEXT NOT NULL DEFAULT 'UNTESTED' CHECK(execution_status IN ('UNTESTED', 'PASSED', 'FAILED', 'BLOCKED'))
);

CREATE TABLE IF NOT EXISTS qa_bugs (
    bug_id TEXT PRIMARY KEY,            -- BUG-01, BUG-02...
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    classification TEXT NOT NULL CHECK(classification IN ('AI-DETECTABLE', 'LOGIC-BUG', 'EDGE-CASE', 'SPEC-UNCLEAR')),
    rca_phase TEXT NOT NULL CHECK(rca_phase IN ('S2', 'S3', 'S4')),
    title TEXT NOT NULL,
    repro_steps TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'IN_FIX', 'RESOLVED', 'RETESTED_PASS', 'KNOWN_ISSUE')),
    fix_commit_or_diff TEXT,
    regression_test_name TEXT,
    justification_for_known_issue TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);

-- View alias: enables queries against `bugs` to resolve to `qa_bugs`
CREATE VIEW IF NOT EXISTS bugs AS SELECT bug_id AS id, * FROM qa_bugs;

CREATE TABLE IF NOT EXISTS qa_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    test_scope TEXT NOT NULL CHECK(test_scope IN ('module', 'full')),
    total_tests INTEGER NOT NULL,
    passed_tests INTEGER NOT NULL,
    failed_tests INTEGER NOT NULL,
    coverage_pct REAL,
    verdict TEXT NOT NULL CHECK(verdict IN ('GO', 'NO-GO')),
    verdict_notes TEXT,
    verified_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS qa_hollow_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL REFERENCES change_state(change_id),
    test_file TEXT NOT NULL,
    hollow_type TEXT NOT NULL CHECK(hollow_type IN ('H1_NO_ASSERT', 'H2_ALWAYS_TRUE', 'H3_MOCK_EVERYTHING', 'H4_UNCHECKED_MUTATION', 'H5_IGNORED_PROMISE')),
    description TEXT NOT NULL
);

-- AUDIT TRAIL LOG
CREATE TABLE IF NOT EXISTS state_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,          -- 'task', 'gate', 'ac', 'bug', 'adr', 'schema'
    entity_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
