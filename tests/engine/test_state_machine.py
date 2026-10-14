"""
Contract Test Suite: State Machine & Business Invariants.
Verifies lifecycle transitions, prerequisite gates, dependency checks,
test proof enforcement, and audit logs.
"""

import os
import sys
import unittest
import sqlite3

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from kit.shared.engine.db import init_db
from kit.shared.engine.state_machine import SDLCStateMachine, StateMachineException


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")
        self.sm = SDLCStateMachine(self.conn)
        self.change = self.sm.change_init(slug="user-auth", work_type="feature", ticket_id="AUTH-101")
        self.change_id = self.change["change_id"]

    def tearDown(self):
        self.conn.close()

    def test_change_lifecycle_and_scope(self):
        # Initial state should be S1
        self.assertEqual(self.change["current_phase"], "S1")
        self.assertEqual(self.change["scope"], "standard")

        # Scope de-escalation from standard to tiny must be REJECTED
        with self.assertRaises(StateMachineException):
            self.sm.change_escalate_scope(self.change_id, to_scope="tiny")

        # Phase transition S2 -> S3 must fail without SPEC_LOCK gate
        self.sm.change_transition_phase(self.change_id, "S2")
        with self.assertRaises(StateMachineException):
            self.sm.change_transition_phase(self.change_id, "S3")

    def test_gate_spec_lock_invariants(self):
        cursor = self.conn.cursor()
        # Add an unclear AC
        cursor.execute("""
            INSERT INTO spec_requirements (req_id, change_id, type, tag, title)
            VALUES ('AC-AUTH-001', ?, 'AC', 'UNCLEAR', 'User login password');
        """, (self.change_id,))
        self.conn.commit()

        # Gate inspect must flag violations
        inspection = self.sm.gate_inspect(self.change_id, "SPEC_LOCK")
        self.assertFalse(inspection["can_pass"])
        self.assertIn("Found 1 requirements with [UNCLEAR] or [MISSING] tags", inspection["violations"][0])

        # Attempting to pass without override must raise exception
        with self.assertRaises(StateMachineException):
            self.sm.gate_attempt_pass(self.change_id, "SPEC_LOCK", approver="lead")

        # Passing with break-glass override must succeed
        res = self.sm.gate_attempt_pass(self.change_id, "SPEC_LOCK", approver="lead", force_reason="Reviewed in call")
        self.assertEqual(res["status"], "PASSED")
        self.assertTrue(res["overridden"])

        # Now S3 transition succeeds
        s3 = self.sm.change_transition_phase(self.change_id, "S3")
        self.assertEqual(s3["current_phase"], "S3")

    def test_task_dependency_and_proof(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO task_graph (task_id, change_id, order_index, title, target_file, mapped_acs_json, depends_on_json)
            VALUES ('T1', ?, 1, 'Migration', 'migrations/001.sql', '["AC-001"]', '[]'),
                   ('T2', ?, 2, 'Service', 'services/auth.ts', '["AC-001"]', '["T1"]');
        """, (self.change_id, self.change_id))
        self.conn.commit()

        # Cannot start T2 because T1 is not completed
        with self.assertRaises(StateMachineException):
            self.sm.task_start(self.change_id, "T2")

        # Start T1
        self.sm.task_start(self.change_id, "T1")

        # Cannot complete T1 with exit_code != 0
        with self.assertRaises(StateMachineException):
            self.sm.task_complete(self.change_id, "T1", "npm run migrate", "Migration failed: syntax error", exit_code=1)

        # Complete T1 with exit_code == 0
        res = self.sm.task_complete(self.change_id, "T1", "npm run migrate", "Migration succeeded", exit_code=0)
        self.assertEqual(res["status"], "COMPLETED")

        # Now T2 can start
        t2_res = self.sm.task_start(self.change_id, "T2")
        self.assertEqual(t2_res["status"], "IN_PROGRESS")

    def test_bug_lifecycle_and_qa_retest(self):
        # Open a critical bug
        bug = self.sm.bug_open(
            self.change_id,
            bug_id="BUG-01",
            title="Token leak in logs",
            severity="CRITICAL",
            classification="AI-DETECTABLE",
            rca_phase="S4",
            repro_steps="Check console logs during login"
        )
        self.assertEqual(bug["status"], "OPEN")

        # QA gate inspection must fail because critical bug is open
        inspection = self.sm.gate_inspect(self.change_id, "QA")
        self.assertFalse(inspection["can_pass"])
        self.assertIn("QA blocker: 1 Critical/High bugs open", inspection["violations"][0])

        # Developer submits fix without regression test must fail
        with self.assertRaises(StateMachineException):
            self.sm.bug_submit_fix(self.change_id, "BUG-01", "diff...", "")

        # Submit valid fix
        fix = self.sm.bug_submit_fix(self.change_id, "BUG-01", "diff...", "test_token_not_in_logs")
        self.assertEqual(fix["status"], "RESOLVED")

        # QA re-tests: if FAIL, reverts to OPEN
        fail_retest = self.sm.bug_retest(self.change_id, "BUG-01", verdict="FAIL", qa_notes="Still leaked on error")
        self.assertEqual(fail_retest["status"], "OPEN")

        # Dev re-fixes
        self.sm.bug_submit_fix(self.change_id, "BUG-01", "better diff...", "test_token_not_in_logs_v2")

        # QA re-tests: if PASS, marks RETESTED_PASS
        pass_retest = self.sm.bug_retest(self.change_id, "BUG-01", verdict="PASS", qa_notes="Verified clean")
        self.assertEqual(pass_retest["status"], "RETESTED_PASS")

    def test_audit_log_tracking(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM state_audit_log WHERE change_id = ?;", (self.change_id,))
        logs = cursor.fetchall()
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0]["entity_type"], "change")

    def test_change_list_and_status(self):
        # List changes
        changes = self.sm.change_list()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["slug"], "user-auth")

        # Status report
        status = self.sm.change_status_report(self.change_id)
        self.assertEqual(status["change"]["slug"], "user-auth")
        self.assertEqual(status["change"]["current_phase"], "S1")
        self.assertEqual(status["requirements"]["total"], 0)
        self.assertEqual(status["tasks"]["total"], 0)
        self.assertEqual(status["bugs"]["open"], 0)

    def test_changes_view_alias(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM changes WHERE id = ?;", (self.change_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["slug"], "user-auth")

    def test_all_view_aliases_exist(self):
        cursor = self.conn.cursor()
        views = [
            "changes", "tasks", "requirements", "bugs", "gates",
            "adrs", "decisions", "decision_log", "progress_log",
            "glossary", "project_glossary", "bridge", "bridge_contracts",
            "knowledge", "edge_cases", "schemas", "endpoints", "components",
            "test_scenarios", "scenarios", "verifications", "audit_log"
        ]
        for v in views:
            cursor.execute(f"SELECT * FROM {v} LIMIT 0;")
        # Also test knowledge has title
        cursor.execute("SELECT title FROM knowledge LIMIT 0;")

    def test_gate_record_blocker(self):
        res = self.sm.gate_record_blocker(self.change_id, "SPEC_LOCK", "AUDIT_FAIL", "AC missing details")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn("AUDIT_FAIL", res["reason"])

    def test_flex_split_task_alias(self):
        from kit.shared.engine.flexible import SDLCFlexibleEngine
        self.assertTrue(hasattr(SDLCFlexibleEngine, "flex_split_task"))
        self.assertTrue(hasattr(SDLCFlexibleEngine, "flex_task_split"))


if __name__ == "__main__":
    unittest.main()
