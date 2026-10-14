"""
Contract Test Suite: Flexible, Surgical Patching & Blast-Radius Engine.
Verifies all 15 methods of Domain 10: In-flight amendments, line-level patching,
task split/reorder, blast-radius dependency analysis, and break-glass overrides.
"""

import os
import sys
import unittest
import json
import sqlite3

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from kit.shared.engine.db import init_db
from kit.shared.engine.state_machine import SDLCStateMachine
from kit.shared.engine.flexible import SDLCFlexibleEngine, FlexibleEngineException


class TestFlexiblePatching(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")
        self.sm = SDLCStateMachine(self.conn)
        self.flex = SDLCFlexibleEngine(self.conn)

        # Initialize test change
        self.change = self.sm.change_init(slug="flexible-test", work_type="feature")
        self.change_id = self.change["change_id"]

        # Populate sample requirements
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO spec_requirements (req_id, change_id, type, tag, title, given_when_then)
            VALUES ('AC-001', ?, 'AC', 'CONFIRMED', 'User login', 'Given valid creds when login then 200'),
                   ('AC-002', ?, 'AC', 'CONFIRMED', 'User logout', 'Given active session when logout then 204');
        """, (self.change_id, self.change_id))

        # Populate sample ADR
        cursor.execute("""
            INSERT INTO decision_ledger (decision_id, change_id, type, decision, reasoning, status, phase, author)
            VALUES ('ADR-001', ?, 'design', 'Use Redis for caching', 'Fast in-memory', 'ACTIVE', 'S3', 'architect');
        """, (self.change_id,))

        # Populate sample schema & endpoint
        cursor.execute("""
            INSERT INTO design_schemas (change_id, table_name, columns_json)
            VALUES (?, 'users', '[{"name": "id", "type": "int"}, {"name": "email", "type": "text"}]');
        """, (self.change_id,))

        cursor.execute("""
            INSERT INTO design_endpoints (id, change_id, method, path, error_codes_json)
            VALUES (1, ?, 'POST', '/auth/login', '["401", "400"]');
        """, (self.change_id,))

        # Populate sample tasks
        cursor.execute("""
            INSERT INTO task_graph (task_id, change_id, order_index, title, target_file, mapped_acs_json, status)
            VALUES ('T1', ?, 1, 'Login handler', 'src/login.ts', '["AC-001"]', 'COMPLETED'),
                   ('T2', ?, 2, 'Logout handler', 'src/logout.ts', '["AC-002"]', 'COMPLETED'),
                   ('T3', ?, 3, 'Audit logger', 'src/logger.ts', '[]', 'TODO');
        """, (self.change_id, self.change_id, self.change_id))

        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_surgical_spec_patching(self):
        # 1. Patch requirement
        res = self.flex.flex_patch_requirement(
            self.change_id, "AC-001", {"title": "Updated login spec"}, reason="Clarified requirement"
        )
        self.assertEqual(res["title"], "Updated login spec")

        # 2. Deprecate requirement
        dep = self.flex.flex_deprecate_requirement(self.change_id, "AC-002", reason="Feature dropped")
        self.assertEqual(dep["status"], "DEPRECATED")

        # 3. Quick add constraint
        quick = self.flex.flex_quick_add_constraint(
            self.change_id, req_type="BR", title="Max 5 login attempts", content="Lockout for 15 mins"
        )
        self.assertIn("BR-QUICK", quick["req_id"])

    def test_surgical_design_patching(self):
        # 4. Supersede decision
        sup = self.flex.flex_supersede_decision(
            self.change_id, "ADR-001", "Use in-memory cache", "Redis too heavy"
        )
        self.assertEqual(sup["superseded"], "ADR-001")
        self.assertEqual(sup["active_replacement"], "ADR-001.1")

        # 5. Patch schema column (add, modify, drop)
        add_col = self.flex.flex_patch_schema_column(
            self.change_id, "users", action="add_col", col_def={"name": "tenant_id", "type": "text"}, reason="Multi-tenancy"
        )
        self.assertEqual(add_col["action"], "add_col")

        mod_col = self.flex.flex_patch_schema_column(
            self.change_id, "users", action="modify_col", col_def={"name": "email", "type": "varchar(255)"}, reason="Explicit length"
        )
        self.assertEqual(mod_col["action"], "modify_col")

        # 6. Patch endpoint
        endp = self.flex.flex_patch_endpoint(
            self.change_id, endpoint_id=1, field="error_codes_json", new_val=["401", "400", "429"], reason="Added rate limit"
        )
        self.assertEqual(endp["field"], "error_codes_json")

    def test_flexible_task_mutations(self):
        # 7. Task split
        split_res = self.flex.flex_task_split(
            self.change_id, "T3", subtasks=[
                {"title": "File logger", "target_file": "src/file_logger.ts"},
                {"title": "Console logger", "target_file": "src/console_logger.ts"}
            ]
        )
        self.assertEqual(len(split_res["subtasks_created"]), 2)
        self.assertIn("T3.1", split_res["subtasks_created"])

        # 8. Task insert urgent
        urgent = self.flex.flex_task_insert_urgent(
            self.change_id, after_task_id="T1", new_task_def={"title": "Urgent DB patch", "target_file": "src/patch.ts"}
        )
        self.assertIn("URGENT", urgent["inserted_task_id"])

        # 9. Task update scope
        scope_res = self.flex.flex_task_update_scope(self.change_id, "T1", {"target_file": "src/auth/login.ts"})
        self.assertEqual(scope_res["status"], "UPDATED")

        # 10. Task reorder
        reorder_res = self.flex.flex_task_reorder(self.change_id, {"T1": 10, "T2": 20})
        self.assertEqual(reorder_res["reordered_tasks"], 2)

    def test_blast_radius_and_selective_invalidation(self):
        # 11. Preview impact of AC-001 (should only impact T1, NOT T2 or T3)
        preview = self.flex.flex_amendment_preview_impact(self.change_id, "requirement", "AC-001")
        self.assertEqual(preview["impacted_tasks_count"], 1)
        self.assertEqual(preview["impacted_tasks"][0]["task_id"], "T1")

        # 12. Apply amendment and invalidate
        # T1 was COMPLETED. It should be selectively invalidated to NEEDS_REVISION.
        # T2 was COMPLETED and should REMAIN COMPLETED!
        inv_res = self.flex.flex_amendment_apply_and_invalidate(
            self.change_id, "requirement", "AC-001", {"title": "Brand new login requirements"}
        )
        self.assertIn("T1", inv_res["invalidated_tasks"])

        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM task_graph WHERE change_id = ? AND task_id = 'T1';", (self.change_id,))
        self.assertEqual(cursor.fetchone()["status"], "NEEDS_REVISION")

        # Crucial check: T2 must NOT be invalidated!
        cursor.execute("SELECT status FROM task_graph WHERE change_id = ? AND task_id = 'T2';", (self.change_id,))
        self.assertEqual(cursor.fetchone()["status"], "COMPLETED")

    def test_fast_notes_and_break_glass(self):
        # 13. Fast note
        note = self.flex.flex_amend_phase_note(self.change_id, "S4", "Paused to align with security team")
        self.assertEqual(note["status"], "RECORDED")

        # 14. Mark known issue
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO qa_bugs (bug_id, change_id, severity, classification, rca_phase, title, repro_steps, status)
            VALUES ('BUG-99', ?, 'HIGH', 'LOGIC-BUG', 'S4', 'Minor UI flicker', 'Resize window', 'OPEN');
        """, (self.change_id,))
        self.conn.commit()

        known = self.flex.flex_qa_mark_known_issue(self.change_id, "BUG-99", justification="UI flicker non-critical for MVP")
        self.assertEqual(known["status"], "KNOWN_ISSUE")

        # 15. Break-glass override
        override = self.flex.flex_break_glass_override(
            self.change_id, gate_name="BUILD", rule_name="LINT_RULES", reason="Legacy lint exceptions", approved_by="tech-lead"
        )
        self.assertEqual(override["status"], "PASSED")
        self.assertTrue(override["audit_recorded"])


if __name__ == "__main__":
    unittest.main()
