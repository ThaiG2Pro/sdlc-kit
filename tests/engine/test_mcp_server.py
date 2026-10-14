"""
Master Contract Test Suite: Zero-Dependency MCP Server over Stdio.
Verifies JSON-RPC 2.0 handshake, 6 Chunky Tools catalog, and Tool Call dispatches.
"""

import os
import sys
import json
import uuid
import tempfile
import unittest
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

from kit.shared.engine.db import init_db
from kit.shared.engine.mcp_server import TOOLS, dispatch_tool, handle_request


class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "session.db")
        os.environ["SDLC_DB_PATH"] = self.db_path
        self.conn = init_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()
        os.environ.pop("SDLC_DB_PATH", None)

    def test_tools_catalog_schema(self):
        """Verify exactly 6 high-level Chunky Tools exist and conform to MCP Schema."""
        self.assertEqual(len(TOOLS), 6)
        tool_names = [t["name"] for t in TOOLS]
        expected_tools = [
            "sdlc_manage_lifecycle",
            "sdlc_record_spec_bundle",
            "sdlc_get_work_context",
            "sdlc_submit_task_result",
            "sdlc_audit_and_verify",
            "sdlc_flex_patch"
        ]
        self.assertEqual(tool_names, expected_tools)
        for t in TOOLS:
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertIn("inputSchema", t)
            self.assertEqual(t["inputSchema"]["type"], "object")

    def test_lifecycle_and_work_context_dispatch(self):
        cid = f"CHG-MCP-{uuid.uuid4().hex[:6]}"

        # 1. Lifecycle init
        res_init = dispatch_tool("sdlc_manage_lifecycle", {
            "action": "init",
            "change_id": cid,
            "slug": "mcp-test",
            "work_type": "feature",
            "rigor": "full"
        })
        self.assertEqual(res_init["change_id"], cid)

        # 2. Record spec bundle (batch)
        res_spec = dispatch_tool("sdlc_record_spec_bundle", {
            "action": "add_requirements",
            "change_id": cid,
            "requirements": [
                {"req_id": "AC-MCP-01", "title": "First MCP req", "gwt": "Given MCP..."}
            ]
        })
        self.assertEqual(res_spec["inserted_count"], 1)

        # 3. Work context query (chunky)
        res_work = dispatch_tool("sdlc_get_work_context", {
            "change_id": cid
        })
        self.assertEqual(res_work["change_id"], cid)
        self.assertIn("handoff", res_work)
        self.assertIn("architecture", res_work)

        # 4. QA audit context query (chunky)
        res_qa = dispatch_tool("sdlc_audit_and_verify", {
            "action": "inspect_audit_context",
            "change_id": cid
        })
        self.assertEqual(res_qa["change"]["change_id"], cid)
        self.assertIn("verification_matrix", res_qa)
        self.assertIn("open_bugs", res_qa)

    def test_stdio_json_rpc_subshell_interaction(self):
        """Test persistent MCP server process communicating via stdio JSON-RPC 2.0 lines."""
        cid = f"CHG-STDIO-{uuid.uuid4().hex[:6]}"
        env = os.environ.copy()
        env["SDLC_DB_PATH"] = self.db_path

        proc = subprocess.Popen(
            ["bin/sdlc-mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        try:
            # 1. Handshake: initialize
            init_req = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"}
            }) + "\n"
            proc.stdin.write(init_req)
            proc.stdin.flush()

            init_resp_line = proc.stdout.readline()
            init_resp = json.loads(init_resp_line)
            self.assertEqual(init_resp["id"], 1)
            self.assertEqual(init_resp["result"]["serverInfo"]["name"], "sdlc-context-engine")

            # 2. tools/list
            tools_req = json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }) + "\n"
            proc.stdin.write(tools_req)
            proc.stdin.flush()

            tools_resp_line = proc.stdout.readline()
            tools_resp = json.loads(tools_resp_line)
            self.assertEqual(tools_resp["id"], 2)
            self.assertEqual(len(tools_resp["result"]["tools"]), 6)

            # 3. tools/call: init change
            call_req = json.dumps({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "sdlc_manage_lifecycle",
                    "arguments": {"action": "init", "change_id": cid, "slug": "stdio-test"}
                }
            }) + "\n"
            proc.stdin.write(call_req)
            proc.stdin.flush()

            call_resp_line = proc.stdout.readline()
            call_resp = json.loads(call_resp_line)
            self.assertEqual(call_resp["id"], 3)
            self.assertFalse(call_resp["result"]["isError"])
            data = json.loads(call_resp["result"]["content"][0]["text"])
            self.assertEqual(data["change_id"], cid)

        finally:
            proc.stdin.close()
            proc.stdout.close()
            proc.stderr.close()
            proc.terminate()
            proc.wait(timeout=2.0)



if __name__ == "__main__":
    unittest.main()
