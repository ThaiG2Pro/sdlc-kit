"""
Contract Test Suite: DDL Schema Verification.
Verifies that all 18 tables and FTS5 virtual table from sdlc-context-engine-spec.md
exist, possess proper columns, and enforce foreign keys and check constraints.
"""

import os
import sys
import unittest
import sqlite3

# Ensure kit/shared/engine is on path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from kit.shared.engine.db import init_db, get_connection


EXPECTED_TABLES = {
    # Domain 1
    "change_state",
    "gate_history",
    "blockers",
    # Domain 2
    "phase_progress",
    "phase_handoff",
    "decision_ledger",
    "change_glossary",
    "cross_spec_bridge",
    "role_memory",
    # Domain 3
    "intake_packages",
    "intake_ui_screens",
    # Domain 4
    "project_knowledge",
    "knowledge_fts",
    # Domain 5
    "spec_requirements",
    "spec_edge_cases",
    "spec_clarifications",
    "spec_stride_threats",
    # Domain 6
    "design_schemas",
    "design_endpoints",
    "design_components",
    # Domain 7
    "task_graph",
    "dev_deviations",
    "release_plans",
    # Domain 8
    "qa_test_scenarios",
    "qa_bugs",
    "qa_verifications",
    "qa_hollow_tests",
    # Audit
    "state_audit_log",
}


class TestSchemaDDL(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_all_expected_tables_exist(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow');")
        tables = {row["name"] for row in cursor.fetchall()}

        for expected in EXPECTED_TABLES:
            self.assertIn(
                expected,
                tables,
                f"Missing expected table or virtual table: {expected}"
            )

    def test_foreign_key_enforcement(self):
        cursor = self.conn.cursor()
        # Inserting gate_history for a nonexistent change_id must raise an IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO gate_history (change_id, gate_name, status, approver)
                VALUES ('nonexistent-change', 'SPEC_LOCK', 'PASSED', 'tester');
            """)

    def test_check_constraint_enforcement(self):
        cursor = self.conn.cursor()
        # Invalid work_type must fail check constraint
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO change_state (change_id, slug, work_type, rigor)
                VALUES ('chg-1', 'test-slug', 'invalid_type', 'lite');
            """)

        # Valid insert must succeed
        cursor.execute("""
            INSERT INTO change_state (change_id, slug, work_type, rigor)
            VALUES ('chg-1', 'test-slug', 'feature', 'full');
        """)
        self.conn.commit()

        cursor.execute("SELECT * FROM change_state WHERE change_id = 'chg-1';")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["slug"], "test-slug")
        self.assertEqual(row["scope"], "standard")  # Default value check
        self.assertEqual(row["test_scope"], "module")  # Default value check

    def test_task_graph_structure(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO change_state (change_id, slug, work_type, rigor)
            VALUES ('chg-2', 'test-task', 'feature', 'full');
        """)
        cursor.execute("""
            INSERT INTO task_graph (task_id, change_id, order_index, title, target_file, mapped_acs_json)
            VALUES ('T1', 'chg-2', 1, 'Setup DB', 'src/db.ts', '["AC-001"]');
        """)
        self.conn.commit()

        cursor.execute("SELECT * FROM task_graph WHERE task_id = 'T1';")
        task = cursor.fetchone()
        self.assertEqual(task["status"], "TODO")
        self.assertEqual(task["is_checkpoint"], 0)

    def test_fts5_virtual_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO knowledge_fts (topic, title, body_text)
            VALUES ('conventions', 'Database Naming', 'All table names must be snake_case.');
        """)
        self.conn.commit()

        cursor.execute("""
            SELECT topic, title FROM knowledge_fts WHERE knowledge_fts MATCH 'snake_case';
        """)
        match = cursor.fetchone()
        self.assertIsNotNone(match)
        self.assertEqual(match["title"], "Database Naming")


if __name__ == "__main__":
    unittest.main()
