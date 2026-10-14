#!/usr/bin/env python3
"""
Zero-Dependency Model Context Protocol (MCP) Server for SDLC Context Engine.
Communicates via JSON-RPC 2.0 over Stdio with IDE clients (Claude Code, Cursor).

Hardened against the 6 Production Pitfalls:
1. Concurrency: 10s busy timeout, WAL autocheckpoint, atomic short-lived transactions.
2. Stateless: Zero in-memory business state; queries directly from SQLite on every call.
3. Zero-Dependency: 100% Python standard library (no pip packages).
4. Chunky Tools: Exactly 6 high-level consolidated tools (~380 tokens vs 4,000 tokens).
5. Stdio Protection: sys.stdout redirected to sys.stderr; only valid JSON-RPC goes to raw stdout.
   Zombie prevention: Clean exit on EOF, SIGINT, SIGTERM.
6. Clean Architecture: Reuses Domain Services (SDLCServices, SDLCStateMachine, SDLCFlexibleEngine).
"""

import os
import sys
import json
import signal
from typing import Dict, Any, Optional

# Reserve clean raw stdout for JSON-RPC ONLY
RAW_STDOUT = sys.__stdout__
# Redirect sys.stdout to sys.stderr to prevent rogue print() from polluting MCP channel
sys.stdout = sys.stderr

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from db import get_connection, init_db, DEFAULT_DB_PATH
from state_machine import SDLCStateMachine, StateMachineException
from flexible import SDLCFlexibleEngine, FlexibleEngineException
from services import SDLCServices, SDLCServiceException


def log_debug(msg: str):
    sys.stderr.write(f"[sdlc-mcp] {msg}\n")
    sys.stderr.flush()


def get_db(db_path: Optional[str] = None):
    target = db_path or DEFAULT_DB_PATH
    if not (os.path.exists(target) and os.path.getsize(target) > 0):
        return init_db(target)
    return get_connection(target)


# =============================================================================
# 6 CHUNKY TOOL DEFINITIONS (Model Context Protocol Schema)
# =============================================================================
TOOLS = [
    {
        "name": "sdlc_manage_lifecycle",
        "description": "Orchestrate SDLC lifecycle: initialize changes, transition phases (S1-S6), inspect quality gates, and record/resolve blockers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["init", "get", "transition", "scope", "gate_inspect", "gate_pass", "gate_block"],
                    "description": "Lifecycle action to perform."
                },
                "change_id": {"type": "string", "description": "Target Change ID (e.g. CHG-01)."},
                "slug": {"type": "string", "description": "Short slug name for change (for init)."},
                "work_type": {"type": "string", "default": "feature", "description": "Work type (feature/bugfix/refactor/hotfix)."},
                "rigor": {"type": "string", "default": "full", "description": "Rigor mode (full/lite)."},
                "phase": {"type": "string", "description": "Target phase (S1, S2, S3, S4, S5, S6)."},
                "gate_name": {"type": "string", "description": "Gate name to inspect or pass."},
                "approver": {"type": "string", "default": "orchestrator", "description": "Approver role or human identifier."},
                "reason": {"type": "string", "description": "Reason for transition, scope escalation, or force-pass."}
            },
            "required": ["action", "change_id"]
        }
    },
    {
        "name": "sdlc_record_spec_bundle",
        "description": "Analyst requirement bundle: atomically add requirements, edge cases, clarifications, and threats, or commit spec lock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add_requirements", "add_edge_cases", "commit_spec_lock", "record_clarification", "add_threat"],
                    "description": "Spec action to perform."
                },
                "change_id": {"type": "string", "description": "Target Change ID."},
                "requirements": {
                    "type": "array",
                    "description": "Array of AC objects: [{'req_id': 'AC-01', 'title': '...', 'gwt': '...', 'tag': 'CONFIRMED'}]",
                    "items": {"type": "object"}
                },
                "edge_cases": {
                    "type": "array",
                    "description": "Array of edge case objects: [{'category': 'boundary', 'scenario': '...', 'expected': '...'}]",
                    "items": {"type": "object"}
                },
                "scope": {"type": "string", "default": "standard", "description": "S2 scope (standard or tiny)."},
                "question": {"type": "string", "description": "Question text for clarification."},
                "answer": {"type": "string", "description": "Proposed guess or answer."},
                "threat_id": {"type": "string", "description": "STRIDE threat ID."}
            },
            "required": ["action", "change_id"]
        }
    },
    {
        "name": "sdlc_get_work_context",
        "description": "Chunky developer/architect query: retrieves the active ready task, full mapped AC specifications, latest handoff reading order, fragile areas, and architecture ADRs/endpoints in a single sub-millisecond query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "change_id": {"type": "string", "description": "Target Change ID."},
                "task_id": {"type": "string", "description": "Optional specific Task ID (defaults to next ready TODO task)."}
            },
            "required": ["change_id"]
        }
    },
    {
        "name": "sdlc_submit_task_result",
        "description": "Developer task completion: marks task started or completed with test execution proof, commands, and exit code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "complete", "list"],
                    "description": "Task action."
                },
                "change_id": {"type": "string", "description": "Target Change ID."},
                "task_id": {"type": "string", "description": "Target Task ID."},
                "test_cmd": {"type": "string", "default": "manual", "description": "Test command executed for verification."},
                "test_output": {"type": "string", "default": "", "description": "Execution output or verification proof."},
                "exit_code": {"type": "integer", "default": 0, "description": "Process exit code (0 = success)."}
            },
            "required": ["action", "change_id"]
        }
    },
    {
        "name": "sdlc_audit_and_verify",
        "description": "QA verification & defect management: inspect consolidated audit context, record test runs in batch, report bugs, and record sign-off verdicts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["inspect_audit_context", "verification_matrix", "create_scenarios_batch", "record_tests_batch", "report_bug", "record_verification"],
                    "description": "QA action to perform."
                },
                "change_id": {"type": "string", "description": "Target Change ID."},
                "scenarios": {"type": "array", "description": "Array of scenario objects.", "items": {"type": "object"}},
                "test_runs": {"type": "array", "description": "Array of test run results [{'scenario_id': 'TC-01', 'status': 'PASS'}].", "items": {"type": "object"}},
                "bug_id": {"type": "string", "description": "Bug identifier (e.g. BUG-01)."},
                "severity": {"type": "string", "default": "MEDIUM", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
                "title": {"type": "string", "description": "Title or bug summary."},
                "repro": {"type": "string", "description": "Reproduction steps or error details."},
                "verdict": {"type": "string", "default": "GO", "enum": ["GO", "NO_GO"]},
                "coverage": {"type": "number", "default": 0.0, "description": "Total test coverage percentage."}
            },
            "required": ["action", "change_id"]
        }
    },
    {
        "name": "sdlc_flex_patch",
        "description": "Surgical in-flight patching (Break-glass): patch requirements, supersede ADRs, split tasks, or override rules without resetting lifecycle.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["patch_req", "deprecate_req", "supersede_adr", "split_task", "preview_impact", "override", "qa_mark_known_issue"],
                    "description": "Flex action."
                },
                "change_id": {"type": "string", "description": "Target Change ID."},
                "item_id": {"type": "string", "description": "Target ID (req_id, adr_id, task_id, or bug_id)."},
                "title": {"type": "string", "description": "New title, decision text, or replacement."},
                "reason": {"type": "string", "default": "Manual patch", "description": "Justification for hot patch."},
                "subtasks": {"type": "array", "description": "Subtask definitions for task split.", "items": {"type": "object"}},
                "approver": {"type": "string", "default": "tech-lead", "description": "Approving entity."}
            },
            "required": ["action", "change_id", "item_id"]
        }
    }
]


# =============================================================================
# TOOL EXECUTION DISPATCHER (Clean Delegation to Domain Services)
# =============================================================================
def dispatch_tool(name: str, args: Dict[str, Any]) -> Any:
    conn = get_db()
    try:
        sm = SDLCStateMachine(conn)
        flex = SDLCFlexibleEngine(conn)
        srv = SDLCServices(conn)

        change_id = args.get("change_id")

        if name == "sdlc_manage_lifecycle":
            action = args["action"]
            if action == "init":
                return sm.change_init(
                    slug=args.get("slug", "feature"),
                    work_type=args.get("work_type", "feature"),
                    rigor=args.get("rigor", "full"),
                    change_id=change_id
                )
            elif action == "get":
                return sm.change_get_state(change_id)
            elif action == "transition":
                return sm.change_transition_phase(change_id, args.get("phase"))
            elif action == "scope":
                return sm.change_escalate_scope(change_id, args.get("scope", "standard"), args.get("reason", ""))
            elif action == "gate_inspect":
                return sm.gate_inspect(change_id, args.get("gate_name", "S1"))
            elif action == "gate_pass":
                return sm.gate_attempt_pass(change_id, args.get("gate_name"), args.get("approver", "orchestrator"), args.get("reason"))
            elif action == "gate_block":
                return sm.gate_record_blocker(change_id, args.get("gate_name"), "BLOCKER", args.get("reason", ""))
            raise ValueError(f"Unknown lifecycle action: {action}")

        elif name == "sdlc_record_spec_bundle":
            action = args["action"]
            if action == "add_requirements":
                return srv.spec_add_requirements_batch(change_id, args.get("requirements", []))
            elif action == "add_edge_cases":
                return srv.spec_add_edge_cases_batch(change_id, args.get("edge_cases", []))
            elif action == "commit_spec_lock":
                return srv.spec_commit_spec_lock(change_id, args.get("scope", "standard"))
            elif action == "record_clarification":
                return srv.spec_record_clarification(change_id, args.get("question", ""), "Impact", args.get("answer", ""))
            elif action == "add_threat":
                return srv.spec_add_stride_threat(args.get("threat_id", "T-01"), change_id, "S", "Security threat", "Mitigation")
            raise ValueError(f"Unknown spec action: {action}")

        elif name == "sdlc_get_work_context":
            return srv.task_inspect_work_context(change_id, args.get("task_id"))

        elif name == "sdlc_submit_task_result":
            action = args["action"]
            task_id = args.get("task_id")
            if action == "start":
                return sm.task_start(change_id, task_id)
            elif action == "complete":
                return sm.task_complete(
                    change_id, task_id,
                    args.get("test_cmd", "manual"),
                    args.get("test_output", ""),
                    int(args.get("exit_code", 0))
                )
            elif action == "list":
                return srv.task_list_all(change_id)
            raise ValueError(f"Unknown task action: {action}")

        elif name == "sdlc_audit_and_verify":
            action = args["action"]
            if action == "inspect_audit_context":
                return srv.qa_inspect_audit_context(change_id)
            elif action == "verification_matrix":
                return srv.qa_get_verification_matrix(change_id)
            elif action == "create_scenarios_batch":
                return srv.qa_create_scenarios_batch(change_id, args.get("scenarios", []))
            elif action == "record_tests_batch":
                return srv.qa_record_tests_batch(change_id, args.get("test_runs", []))
            elif action == "report_bug":
                return srv.qa_report_bug(
                    change_id, args.get("bug_id", "BUG-01"),
                    args.get("severity", "MEDIUM"),
                    "LOGIC", "S4",
                    args.get("title", "Bug"),
                    args.get("repro", "")
                )
            elif action == "record_verification":
                return srv.qa_record_verification(
                    change_id, "module", 0, 0, 0,
                    float(args.get("coverage", 0.0)),
                    args.get("verdict", "GO"),
                    args.get("title", "")
                )
            raise ValueError(f"Unknown qa action: {action}")

        elif name == "sdlc_flex_patch":
            action = args["action"]
            item_id = args.get("item_id")
            if action == "patch_req":
                return flex.flex_patch_requirement(change_id, item_id, {"title": args.get("title")}, args.get("reason", "Hot patch"))
            elif action == "deprecate_req":
                return flex.flex_deprecate_requirement(change_id, item_id, args.get("reason", "Deprecated"))
            elif action == "supersede_adr":
                return flex.flex_supersede_decision(change_id, item_id, args.get("title", "Superseded"), args.get("reason", "Superseded"))
            elif action == "split_task":
                return flex.flex_split_task(change_id, item_id, args.get("subtasks", []), args.get("reason", "Task split"))
            elif action == "preview_impact":
                return flex.flex_amendment_preview_impact(change_id, "requirement", item_id)
            elif action == "override":
                return flex.flex_break_glass_override(change_id, item_id, "OVERRIDE_RULE", args.get("reason", "Emergency override"), args.get("approver", "tech-lead"))
            elif action == "qa_mark_known_issue":
                return flex.flex_qa_mark_known_issue(change_id, item_id, args.get("reason", "Approved known issue"), args.get("approver", "tech-lead"))
            raise ValueError(f"Unknown flex action: {action}")

        raise ValueError(f"Unknown tool name: {name}")

    finally:
        conn.close()


# =============================================================================
# JSON-RPC 2.0 PROTOCOL ENGINE OVER STDIO
# =============================================================================
def send_rpc_response(msg: Dict[str, Any]):
    """Write strict JSON-RPC message directly to raw stdout with newline delimiter."""
    payload = json.dumps(msg)
    RAW_STDOUT.write(f"{payload}\n")
    RAW_STDOUT.flush()


def handle_request(req: Dict[str, Any]):
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    # Protocol initialization
    if method == "initialize":
        send_rpc_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "sdlc-context-engine",
                    "version": "1.0.0"
                }
            }
        })
        return

    # Client notification after init
    if method == "notifications/initialized":
        return

    # Tools catalog
    if method == "tools/list":
        send_rpc_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        })
        return

    # Tool invocation
    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            res_data = dispatch_tool(tool_name, tool_args)
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res_data, indent=2, default=str)
                        }
                    ],
                    "isError": False
                }
            })
        except Exception as e:
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"ERROR: {str(e)}"
                        }
                    ],
                    "isError": True
                }
            })
        return

    # Ping / keep-alive
    if method == "ping":
        send_rpc_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        return

    # Unknown method
    if req_id is not None:
        send_rpc_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        })


def main():
    def shutdown(signum=None, frame=None):
        log_debug("MCP Server shutting down cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    log_debug("SDLC Context Engine MCP Server started (listening on stdin).")

    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                # EOF: Client (Cursor/Claude) disconnected or closed stdin
                break
            line_str = line.strip()
            if not line_str:
                continue

            try:
                req = json.loads(line_str)
                handle_request(req)
            except json.JSONDecodeError as e:
                log_debug(f"JSON decode error: {e}")
                send_rpc_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error: Invalid JSON"}
                })
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        shutdown()


if __name__ == "__main__":
    main()
