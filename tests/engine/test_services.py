"""
Contract Test Suite: Domain Services & Markdown Sync.
Verifies Baton Protocol, Intake Packages, Knowledge FTS, Spec/Design contracts,
QA verification matrix, Role Memory, and Dual-Layer Markdown Export.
"""

import os
import sys
import unittest
import tempfile
import sqlite3

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from kit.shared.engine.db import init_db
from kit.shared.engine.state_machine import SDLCStateMachine
from kit.shared.engine.services import SDLCServices


class TestServices(unittest.TestCase):
    def setUp(self):
        self.conn = init_db(":memory:")
        self.sm = SDLCStateMachine(self.conn)
        self.srv = SDLCServices(self.conn)

        self.change = self.sm.change_init(slug="services-test", work_type="feature", ticket_id="SRV-100")
        self.change_id = self.change["change_id"]

    def tearDown(self):
        self.conn.close()

    def test_baton_protocol_services(self):
        # 1. Handoff
        self.srv.handoff_create(
            self.change_id, "S1", "S2", "analyst",
            key_decisions=["K1"], risky_areas=["Auth edge cases"], reading_order=["context/stack.md"]
        )
        ro = self.srv.handoff_get_reading_order(self.change_id)
        self.assertEqual(ro, ["context/stack.md"])
        risks = self.srv.handoff_get_risky_areas(self.change_id)
        self.assertEqual(risks, ["Auth edge cases"])

        # 2. Decisions
        self.srv.decision_record(self.change_id, "DEC-001", "design", "Use JWT", "Stateless auth")
        decs = self.srv.decision_list(self.change_id, type="design")
        self.assertEqual(len(decs), 1)
        found = self.srv.decision_search(self.change_id, "JWT")
        self.assertEqual(len(found), 1)

        # 3. Progress
        self.srv.progress_mark(self.change_id, "S1", "DONE", "Requirements gathered", next_action="Start S2 spec")
        next_act = self.srv.progress_get_next_action(self.change_id)
        self.assertEqual(next_act, "Start S2 spec")

        # 4. Glossary
        self.srv.glossary_define(self.change_id, "JWT", "JSON Web Token")
        def_val = self.srv.glossary_lookup(self.change_id, "JWT")
        self.assertEqual(def_val, "JSON Web Token")

        # 5. Bridge
        self.srv.bridge_export_service(self.change_id, "AuthService", "/api/v1/auth", "Token auth service")
        deps = self.srv.bridge_query_dependencies("AuthService")
        self.assertEqual(len(deps), 1)

    def test_intake_and_ui_screens(self):
        # Intake package
        self.srv.intake_save_raw_ticket(self.change_id, "TKT-1", "Login feature", "Full description")
        summary = self.srv.intake_get_summary(self.change_id)
        self.assertEqual(summary["ticket"]["title"], "Login feature")

        # UI Screen
        self.srv.intake_save_ui_screen(
            self.change_id, "SCR-01", "Login Screen", "Authenticate user", "/login", None,
            "Header / Form / Footer", [{"type": "button", "label": "Submit"}], [{"field": "email", "type": "text"}]
        )
        screen = self.srv.intake_get_ui_screen(self.change_id, "SCR-01")
        self.assertIsNotNone(screen)
        self.assertEqual(screen["screen_name"], "Login Screen")
        self.assertEqual(len(screen["components_json"]), 1)

    def test_knowledge_and_fts_search(self):
        self.srv.knowledge_set_topic("conventions", {"db_naming": "snake_case", "api_prefix": "/api/v1"})
        sec = self.srv.knowledge_get_section("conventions", "db_naming")
        self.assertEqual(sec, "snake_case")

        # FTS5 search
        matches = self.srv.knowledge_search("snake_case")
        self.assertGreater(len(matches), 0)

        # Drift detection
        drift = self.srv.knowledge_detect_drift({"db_naming": "camelCase", "new_tool": "vitest"})
        self.assertTrue(drift["drift_detected"])
        self.assertEqual(drift["drift_count"], 2)

    def test_requirements_and_design(self):
        # Spec requirement
        self.srv.spec_add_requirement(self.change_id, "AC-SRV-001", "AC", "CONFIRMED", "Return 200 on login")
        req = self.srv.spec_get_requirement("AC-SRV-001")
        self.assertEqual(req["title"], "Return 200 on login")

        # Design schema & endpoint
        self.srv.design_set_schema(self.change_id, "accounts", [{"name": "id", "type": "int"}])
        schema = self.srv.design_get_schema(self.change_id, "accounts")
        self.assertIsNotNone(schema)
        self.assertEqual(schema["table_name"], "accounts")

        self.srv.design_set_endpoint(self.change_id, "POST", "/accounts", {"name": "string"}, {"id": "int"}, ["400"])
        endp = self.srv.design_get_endpoint(self.change_id, "POST", "/accounts")
        self.assertIsNotNone(endp)
        self.assertEqual(endp["method"], "POST")

    def test_task_graph_and_qa_matrix(self):
        self.srv.spec_add_requirement(self.change_id, "AC-QA-01", "AC", "CONFIRMED", "Valid password")
        self.srv.task_create(self.change_id, "T1", 1, "Implement pass check", "src/pass.ts", ["AC-QA-01"])

        # Next active task
        next_task = self.srv.task_get_next_active(self.change_id)
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task["task_id"], "T1")

        # QA test scenario
        self.srv.qa_create_test_scenario(self.change_id, "TC-01", "AC-QA-01", "Test strong password", "Enter P@ss", "Pass", "P0")
        matrix = self.srv.qa_get_verification_matrix(self.change_id)
        self.assertEqual(len(matrix), 1)
        self.assertEqual(matrix[0]["test_scenarios_count"], 1)

    def test_dual_layer_markdown_export(self):
        self.srv.spec_add_requirement(self.change_id, "AC-01", "AC", "CONFIRMED", "Feature X")
        self.srv.task_create(self.change_id, "T1", 1, "Task X", "src/x.ts", ["AC-01"])

        with tempfile.TemporaryDirectory() as tmpdir:
            exported_files = self.srv.sync_export_all_markdown(self.change_id, tmpdir)
            self.assertEqual(len(exported_files), 3)
            for fpath in exported_files:
                self.assertTrue(os.path.exists(fpath))
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.assertIn(self.change_id, content)


if __name__ == "__main__":
    unittest.main()
