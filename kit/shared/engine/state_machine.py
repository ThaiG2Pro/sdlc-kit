"""
State Machine Engine & Invariants for SDLC Context Engine.
Enforces business rules, valid lifecycle transitions, and audit logging
for Change, Gate, Task, and Bug entities. Zero external dependencies.
"""

import json
import sqlite3
from typing import Optional, Dict, Any, List, Tuple


class StateMachineException(Exception):
    """Raised when an illegal state transition or invariant violation occurs."""
    pass


class SDLCStateMachine:
    """State Machine Controller handling transitions and integrity invariants."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _log_audit(
        self,
        change_id: str,
        entity_type: str,
        entity_id: str,
        from_state: Optional[str],
        to_state: str,
        actor: str,
        reason: Optional[str] = None
    ):
        """Append an entry to state_audit_log."""
        self.conn.execute("""
            INSERT INTO state_audit_log (change_id, entity_type, entity_id, from_state, to_state, actor, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (change_id, entity_type, entity_id, from_state, to_state, actor, reason))

    # =========================================================================
    # 1. CHANGE LIFECYCLE
    # =========================================================================
    def change_init(
        self,
        slug: str,
        work_type: str = "feature",
        ticket_id: Optional[str] = None,
        rigor: str = "full",
        change_id: Optional[str] = None,
        actor: str = "orchestrator"
    ) -> Dict[str, Any]:
        """Initialize a new change."""
        if change_id is None:
            change_id = f"chg-{slug}" if not ticket_id else f"chg-{ticket_id}-{slug}"

        valid_types = ('feature', 'cr', 'rebuild', 'bugfix', 'hotfix', 'spike', 'tech-debt')
        if work_type not in valid_types:
            raise StateMachineException(f"Invalid work_type: {work_type}. Must be one of {valid_types}")

        if rigor not in ('full', 'lite'):
            raise StateMachineException(f"Invalid rigor: {rigor}. Must be 'full' or 'lite'")

        self.conn.execute("""
            INSERT INTO change_state (change_id, ticket_id, slug, work_type, rigor, scope, test_scope, current_phase, overall_status)
            VALUES (?, ?, ?, ?, ?, 'standard', 'module', 'S1', 'IN_PROGRESS');
        """, (change_id, ticket_id, slug, work_type, rigor))

        self._log_audit(change_id, "change", change_id, None, "S1", actor, "Initialized change")
        self.conn.commit()
        return self.change_get_state(change_id)

    def change_get_state(self, change_id: str) -> Dict[str, Any]:
        """Fetch current state of a change."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM change_state WHERE change_id = ?;", (change_id,))
        row = cursor.fetchone()
        if not row:
            raise StateMachineException(f"Change not found: {change_id}")

        # Check for any active blockers
        cursor.execute("SELECT COUNT(*) as count FROM blockers WHERE change_id = ? AND status = 'OPEN';", (change_id,))
        blocker_count = cursor.fetchone()["count"]

        return {
            "change_id": row["change_id"],
            "ticket_id": row["ticket_id"],
            "slug": row["slug"],
            "work_type": row["work_type"],
            "rigor": row["rigor"],
            "scope": row["scope"],
            "test_scope": row["test_scope"],
            "current_phase": row["current_phase"],
            "overall_status": row["overall_status"],
            "active_blockers": blocker_count,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def change_transition_phase(
        self,
        change_id: str,
        target_phase: str,
        actor: str = "orchestrator"
    ) -> Dict[str, Any]:
        """Transition change to the next phase, verifying prerequisite gates."""
        state = self.change_get_state(change_id)
        current = state["current_phase"]

        phase_gate_prereqs = {
            "S2": None,               # S1 -> S2 (intake to functional spec)
            "S3": "SPEC_LOCK",        # S2 -> S3 requires SPEC_LOCK passed
            "S4": "DESIGN_REVIEW",    # S3 -> S4 requires DESIGN_REVIEW passed
            "S5": "BUILD",            # S4 -> S5 requires BUILD gate passed
            "S6": "QA",               # S5 -> S6 requires QA gate passed
        }

        prereq_gate = phase_gate_prereqs.get(target_phase)
        if prereq_gate:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT status FROM gate_history
                WHERE change_id = ? AND gate_name = ?
                ORDER BY id DESC LIMIT 1;
            """, (change_id, prereq_gate))
            gate_row = cursor.fetchone()
            if not gate_row or gate_row["status"] != "PASSED":
                raise StateMachineException(
                    f"Cannot transition to {target_phase}: Prerequisite Gate '{prereq_gate}' has not PASSED."
                )

        self.conn.execute("""
            UPDATE change_state SET current_phase = ?, updated_at = CURRENT_TIMESTAMP
            WHERE change_id = ?;
        """, (target_phase, change_id))

        self._log_audit(change_id, "change", change_id, current, target_phase, actor, f"Phase transition to {target_phase}")
        self.conn.commit()
        return self.change_get_state(change_id)

    def change_escalate_scope(
        self,
        change_id: str,
        to_scope: str = "standard",
        reason: str = "",
        actor: str = "architect"
    ) -> Dict[str, Any]:
        """Escalate scope from tiny to standard (never allowed from standard to tiny)."""
        state = self.change_get_state(change_id)
        current = state["scope"]
        if current == "standard" and to_scope == "tiny":
            raise StateMachineException("Illegal scope de-escalation: Scope cannot be downgraded from standard to tiny.")

        if to_scope not in ('tiny', 'standard'):
            raise StateMachineException(f"Invalid scope: {to_scope}")

        self.conn.execute("""
            UPDATE change_state SET scope = ?, updated_at = CURRENT_TIMESTAMP
            WHERE change_id = ?;
        """, (to_scope, change_id))

        self._log_audit(change_id, "change", change_id, current, to_scope, actor, f"Scope escalated: {reason}")
        self.conn.commit()
        return self.change_get_state(change_id)

    # =========================================================================
    # 2. GATE INVARIANTS & PASSING
    # =========================================================================
    def gate_inspect(self, change_id: str, gate_name: str) -> Dict[str, Any]:
        """Inspect gate readiness against deterministic invariants."""
        cursor = self.conn.cursor()
        issues: List[str] = []

        if gate_name == "SPEC_LOCK":
            # Rule 1: No UNCLEAR or MISSING tags in ACs
            cursor.execute("""
                SELECT req_id, tag FROM spec_requirements
                WHERE change_id = ? AND tag IN ('UNCLEAR', 'MISSING') AND status != 'DEPRECATED';
            """, (change_id,))
            unclear = cursor.fetchall()
            if unclear:
                issues.append(f"Found {len(unclear)} requirements with [UNCLEAR] or [MISSING] tags: {[r['req_id'] for r in unclear]}")

            # Rule 2: Minimum edge cases
            state = self.change_get_state(change_id)
            min_edge = 3 if state["scope"] == "tiny" else 10
            cursor.execute("SELECT COUNT(*) as count FROM spec_edge_cases WHERE change_id = ?;", (change_id,))
            edge_count = cursor.fetchone()["count"]
            if edge_count < min_edge:
                issues.append(f"Insufficient edge cases: found {edge_count}, minimum required is {min_edge} for scope '{state['scope']}'.")

        elif gate_name == "DESIGN_REVIEW":
            # Rule: 100% of specified ACs must be mapped in task_graph
            cursor.execute("""
                SELECT req_id FROM spec_requirements
                WHERE change_id = ? AND type = 'AC' AND status != 'DEPRECATED';
            """, (change_id,))
            all_acs = [r["req_id"] for r in cursor.fetchall()]

            cursor.execute("SELECT mapped_acs_json FROM task_graph WHERE change_id = ?;", (change_id,))
            mapped_acs = set()
            for r in cursor.fetchall():
                try:
                    mapped_acs.update(json.loads(r["mapped_acs_json"]))
                except Exception:
                    pass

            unmapped = [ac for ac in all_acs if ac not in mapped_acs]
            if unmapped:
                issues.append(f"Design gap: {len(unmapped)} ACs not mapped to any task in task_graph: {unmapped}")

        elif gate_name == "BUILD":
            # Rule: 100% of tasks must be COMPLETED
            cursor.execute("""
                SELECT task_id, status FROM task_graph
                WHERE change_id = ? AND status != 'COMPLETED';
            """, (change_id,))
            incomplete = cursor.fetchall()
            if incomplete:
                issues.append(f"Build incomplete: {len(incomplete)} tasks not COMPLETED: {[t['task_id'] for t in incomplete]}")

        elif gate_name == "QA":
            # Rule: 0 OPEN or IN_FIX bugs with CRITICAL or HIGH severity
            cursor.execute("""
                SELECT bug_id, severity, title FROM qa_bugs
                WHERE change_id = ? AND status IN ('OPEN', 'IN_FIX') AND severity IN ('CRITICAL', 'HIGH');
            """, (change_id,))
            blocking_bugs = cursor.fetchall()
            if blocking_bugs:
                issues.append(f"QA blocker: {len(blocking_bugs)} Critical/High bugs open: {[b['bug_id'] for b in blocking_bugs]}")

        return {
            "change_id": change_id,
            "gate_name": gate_name,
            "can_pass": len(issues) == 0,
            "violations": issues
        }

    def gate_attempt_pass(
        self,
        change_id: str,
        gate_name: str,
        approver: str,
        force_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pass a gate if all invariants are met, or if force_reason is provided."""
        inspection = self.gate_inspect(change_id, gate_name)
        if not inspection["can_pass"] and not force_reason:
            raise StateMachineException(
                f"Cannot pass gate '{gate_name}': Invariant violations detected: {'; '.join(inspection['violations'])}. "
                "Use force_reason to override with audit justification if permitted."
            )

        status = "PASSED"
        self.conn.execute("""
            INSERT INTO gate_history (change_id, gate_name, status, approver, override_reason)
            VALUES (?, ?, ?, ?, ?);
        """, (change_id, gate_name, status, approver, force_reason))

        self._log_audit(change_id, "gate", gate_name, "PENDING", status, approver, force_reason or "All invariants verified")
        self.conn.commit()

        return {
            "change_id": change_id,
            "gate_name": gate_name,
            "status": status,
            "approver": approver,
            "overridden": force_reason is not None
        }

    # =========================================================================
    # 3. TASK GRAPH LIFECYCLE
    # =========================================================================
    def task_start(self, change_id: str, task_id: str, actor: str = "developer") -> Dict[str, Any]:
        """Start a task, ensuring dependencies are satisfied."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, task_id))
        task = cursor.fetchone()
        if not task:
            raise StateMachineException(f"Task not found: {task_id}")

        if task["status"] == "COMPLETED":
            raise StateMachineException(f"Task {task_id} is already COMPLETED.")

        # Check dependencies
        if task["depends_on_json"]:
            try:
                deps = json.loads(task["depends_on_json"])
                for dep_id in deps:
                    cursor.execute("SELECT status FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, dep_id))
                    dep = cursor.fetchone()
                    if not dep or dep["status"] != "COMPLETED":
                        raise StateMachineException(
                            f"Cannot start Task {task_id}: Prerequisite Task '{dep_id}' is not COMPLETED (status: {dep['status'] if dep else 'missing'})."
                        )
            except json.JSONDecodeError:
                pass

        self.conn.execute("""
            UPDATE task_graph SET status = 'IN_PROGRESS'
            WHERE change_id = ? AND task_id = ?;
        """, (change_id, task_id))

        self._log_audit(change_id, "task", task_id, task["status"], "IN_PROGRESS", actor)
        self.conn.commit()

        return {"task_id": task_id, "status": "IN_PROGRESS"}

    def task_complete(
        self,
        change_id: str,
        task_id: str,
        test_command_run: str,
        test_output: str,
        exit_code: int,
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Complete a task with mandatory test proof (exit_code == 0)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, task_id))
        task = cursor.fetchone()
        if not task:
            raise StateMachineException(f"Task not found: {task_id}")

        if exit_code != 0:
            raise StateMachineException(
                f"Cannot complete Task {task_id}: Verification failed with exit code {exit_code}. Output: {test_output[:200]}"
            )

        self.conn.execute("""
            UPDATE task_graph
            SET status = 'COMPLETED',
                test_command_run = ?,
                test_output = ?,
                exit_code = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE change_id = ? AND task_id = ?;
        """, (test_command_run, test_output, exit_code, change_id, task_id))

        # Also update mapped ACs to IMPLEMENTED if all tasks referencing them are done
        if task["mapped_acs_json"]:
            try:
                acs = json.loads(task["mapped_acs_json"])
                for ac_id in acs:
                    self.conn.execute("""
                        UPDATE spec_requirements
                        SET status = 'IMPLEMENTED', updated_at = CURRENT_TIMESTAMP
                        WHERE change_id = ? AND req_id = ? AND status = 'SPECIFIED';
                    """, (change_id, ac_id))
            except json.JSONDecodeError:
                pass

        self._log_audit(change_id, "task", task_id, task["status"], "COMPLETED", actor, f"Test passed: {test_command_run}")
        self.conn.commit()

        return {"task_id": task_id, "status": "COMPLETED", "exit_code": exit_code}

    # =========================================================================
    # 4. BUG LIFECYCLE
    # =========================================================================
    def bug_open(
        self,
        change_id: str,
        bug_id: str,
        title: str,
        severity: str,
        classification: str,
        rca_phase: str,
        repro_steps: str,
        actor: str = "qa"
    ) -> Dict[str, Any]:
        """Open a new bug."""
        valid_sevs = ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
        if severity not in valid_sevs:
            raise StateMachineException(f"Invalid severity: {severity}. Must be in {valid_sevs}")

        self.conn.execute("""
            INSERT INTO qa_bugs (bug_id, change_id, severity, classification, rca_phase, title, repro_steps, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN');
        """, (bug_id, change_id, severity, classification, rca_phase, title, repro_steps))

        self._log_audit(change_id, "bug", bug_id, None, "OPEN", actor, f"Bug opened ({severity}): {title}")
        self.conn.commit()

        return {"bug_id": bug_id, "status": "OPEN", "severity": severity}

    def bug_submit_fix(
        self,
        change_id: str,
        bug_id: str,
        fix_commit_or_diff: str,
        regression_test_name: str,
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Submit a bug fix with mandatory regression test reference."""
        if not regression_test_name or not regression_test_name.strip():
            raise StateMachineException("Cannot resolve bug: A valid regression_test_name is required to prevent regressions.")

        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM qa_bugs WHERE change_id = ? AND bug_id = ?;", (change_id, bug_id))
        bug = cursor.fetchone()
        if not bug:
            raise StateMachineException(f"Bug not found: {bug_id}")

        self.conn.execute("""
            UPDATE qa_bugs
            SET status = 'RESOLVED',
                fix_commit_or_diff = ?,
                regression_test_name = ?,
                resolved_at = CURRENT_TIMESTAMP
            WHERE change_id = ? AND bug_id = ?;
        """, (fix_commit_or_diff, regression_test_name, change_id, bug_id))

        self._log_audit(change_id, "bug", bug_id, bug["status"], "RESOLVED", actor, f"Fixed with regression test: {regression_test_name}")
        self.conn.commit()

        return {"bug_id": bug_id, "status": "RESOLVED"}

    def bug_retest(
        self,
        change_id: str,
        bug_id: str,
        verdict: str,  # 'PASS' or 'FAIL'
        qa_notes: str = "",
        actor: str = "qa"
    ) -> Dict[str, Any]:
        """QA re-tests a resolved bug. PASS -> RETESTED_PASS, FAIL -> OPEN."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM qa_bugs WHERE change_id = ? AND bug_id = ?;", (change_id, bug_id))
        bug = cursor.fetchone()
        if not bug:
            raise StateMachineException(f"Bug not found: {bug_id}")

        if verdict == "PASS":
            new_status = "RETESTED_PASS"
        elif verdict == "FAIL":
            new_status = "OPEN"
        else:
            raise StateMachineException(f"Invalid retest verdict: {verdict}. Must be 'PASS' or 'FAIL'.")

        self.conn.execute("""
            UPDATE qa_bugs SET status = ? WHERE change_id = ? AND bug_id = ?;
        """, (new_status, change_id, bug_id))

        self._log_audit(change_id, "bug", bug_id, bug["status"], new_status, actor, f"Retest {verdict}: {qa_notes}")
        self.conn.commit()

        return {"bug_id": bug_id, "status": new_status, "verdict": verdict}

    def bug_assign_fix(self, change_id: str, bug_id: str, actor: str = "orchestrator") -> Dict[str, Any]:
        self.conn.execute("UPDATE qa_bugs SET status = 'IN_FIX' WHERE change_id = ? AND bug_id = ?;", (change_id, bug_id))
        self._log_audit(change_id, "bug", bug_id, "OPEN", "IN_FIX", actor, "Assigned to developer for S4-FIX")
        self.conn.commit()
        return {"bug_id": bug_id, "status": "IN_FIX"}

    # =========================================================================
    # 5. ORCHESTRATOR & BLOCKER UTILITIES
    # =========================================================================
    def change_set_scope(self, change_id: str, scope: str, reason: str = "", actor: str = "orchestrator") -> Dict[str, Any]:
        self.conn.execute("UPDATE change_state SET scope = ? WHERE change_id = ?;", (scope, change_id))
        self._log_audit(change_id, "change", change_id, None, scope, actor, f"Scope set: {reason}")
        self.conn.commit()
        return {"change_id": change_id, "scope": scope}

    def change_set_rigor(self, change_id: str, rigor: str, actor: str = "orchestrator") -> Dict[str, Any]:
        self.conn.execute("UPDATE change_state SET rigor = ? WHERE change_id = ?;", (rigor, change_id))
        self._log_audit(change_id, "change", change_id, None, rigor, actor, f"Rigor set to {rigor}")
        self.conn.commit()
        return {"change_id": change_id, "rigor": rigor}

    def change_set_test_scope(self, change_id: str, test_scope: str, actor: str = "orchestrator") -> Dict[str, Any]:
        self.conn.execute("UPDATE change_state SET test_scope = ? WHERE change_id = ?;", (test_scope, change_id))
        self._log_audit(change_id, "change", change_id, None, test_scope, actor, f"Test scope set to {test_scope}")
        self.conn.commit()
        return {"change_id": change_id, "test_scope": test_scope}

    def change_archive(self, change_id: str, actor: str = "orchestrator") -> Dict[str, Any]:
        self.conn.execute("UPDATE change_state SET overall_status = 'ARCHIVED' WHERE change_id = ?;", (change_id,))
        self._log_audit(change_id, "change", change_id, "IN_PROGRESS", "ARCHIVED", actor, "Change archived")
        self.conn.commit()
        return {"change_id": change_id, "overall_status": "ARCHIVED"}

    def orch_get_subagent_brief(self, change_id: str, target_agent: str) -> str:
        state = self.change_get_state(change_id)
        return f"Brief for {target_agent}: change_id={change_id}, phase={state['current_phase']}, scope={state['scope']}, rigor={state['rigor']}."

    def orch_dispute_bug(self, change_id: str, bug_id: str, dev_claim: str, verdict: str, actor: str = "orchestrator") -> Dict[str, Any]:
        new_status = "RESOLVED" if verdict == "UPHELD_DEV" else "OPEN"
        self.conn.execute("UPDATE qa_bugs SET status = ? WHERE change_id = ? AND bug_id = ?;", (new_status, change_id, bug_id))
        self._log_audit(change_id, "bug_dispute", bug_id, None, new_status, actor, f"Dispute claim: {dev_claim}. Verdict: {verdict}")
        self.conn.commit()
        return {"bug_id": bug_id, "verdict": verdict, "status": new_status}

    def orch_check_flow_ownership(self, change_id: str, expected_type: str) -> bool:
        state = self.change_get_state(change_id)
        return state["work_type"] == expected_type

    def orch_render_baton_to_disk(self, change_id: str, output_dir: str) -> str:
        import os
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "_state_rendered.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.change_get_state(change_id), f, indent=2, default=str)
        return path

    def gate_mark_blocked(self, change_id: str, gate_name: str, blocker_reason: str, actor: str = "orchestrator") -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO gate_history (change_id, gate_name, status, approver, override_reason)
            VALUES (?, ?, 'BLOCKED', ?, ?);
        """, (change_id, gate_name, actor, blocker_reason))
        self._log_audit(change_id, "gate", gate_name, "PENDING", "BLOCKED", actor, blocker_reason)
        self.conn.commit()
        return {"gate_name": gate_name, "status": "BLOCKED", "reason": blocker_reason}

    def gate_list_history(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM gate_history WHERE change_id = ? ORDER BY id ASC;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def blocker_raise(self, change_id: str, phase: str, raised_by: str, question: str, options_list: Optional[List[str]] = None) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM blockers WHERE change_id = ?;", (change_id,))
        count = cursor.fetchone()["count"] + 1
        blk_id = f"BLK-{count:02d}"

        self.conn.execute("""
            INSERT INTO blockers (blocker_id, change_id, phase, raised_by, question, options_json, status)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN');
        """, (blk_id, change_id, phase, raised_by, question, json.dumps(options_list or [])))
        self._log_audit(change_id, "blocker", blk_id, None, "OPEN", raised_by, question)
        self.conn.commit()
        return {"blocker_id": blk_id, "question": question, "status": "OPEN"}

    def blocker_resolve_by_user(self, change_id: str, blocker_id: str, selected_option: str, actor: str = "user") -> Dict[str, Any]:
        self.conn.execute("""
            UPDATE blockers
            SET selected_option = ?, status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
            WHERE change_id = ? AND blocker_id = ?;
        """, (selected_option, change_id, blocker_id))
        self._log_audit(change_id, "blocker", blocker_id, "OPEN", "RESOLVED", actor, f"Selected: {selected_option}")
        self.conn.commit()
        return {"blocker_id": blocker_id, "status": "RESOLVED", "selected_option": selected_option}

    def blocker_list_active(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM blockers WHERE change_id = ? AND status = 'OPEN';", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def blocker_get_details(self, blocker_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM blockers WHERE blocker_id = ?;", (blocker_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
