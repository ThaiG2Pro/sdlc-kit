"""
Flexible, Surgical Patching & Blast-Radius Engine for SDLC Context Engine.
Implements Domain 10: In-flight amendments, line-level patching, task splitting/reordering,
blast-radius dependency analysis, selective invalidation, and break-glass overrides.
Zero external dependencies.
"""

import json
import sqlite3
from typing import Optional, Dict, Any, List, Union


class FlexibleEngineException(Exception):
    """Raised when a flexible patching operation encounters invalid parameters or data."""
    pass


class SDLCFlexibleEngine:
    """Handles granular patching, flexible task mutations, and blast-radius impact analysis."""

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
        """Append to audit log."""
        self.conn.execute("""
            INSERT INTO state_audit_log (change_id, entity_type, entity_id, from_state, to_state, actor, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (change_id, entity_type, entity_id, from_state, to_state, actor, reason))

    # =========================================================================
    # 1. SURGICAL SPEC & DECISION PATCHING
    # =========================================================================
    def flex_patch_requirement(
        self,
        change_id: str,
        req_id: str,
        patch_data: Dict[str, Any],
        reason: str,
        actor: str = "analyst"
    ) -> Dict[str, Any]:
        """Surgically update fields of a single requirement (title, given_when_then, tag)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM spec_requirements WHERE change_id = ? AND req_id = ?;", (change_id, req_id))
        row = cursor.fetchone()
        if not row:
            raise FlexibleEngineException(f"Requirement not found: {req_id}")

        allowed_fields = {"title", "given_when_then", "tag"}
        updates = []
        params = []
        for k, v in patch_data.items():
            if k in allowed_fields:
                updates.append(f"{k} = ?")
                params.append(v)

        if not updates:
            raise FlexibleEngineException(f"No valid patch fields provided. Allowed: {allowed_fields}")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([change_id, req_id])

        sql = f"UPDATE spec_requirements SET {', '.join(updates)} WHERE change_id = ? AND req_id = ?;"
        self.conn.execute(sql, params)

        self._log_audit(change_id, "requirement", req_id, row["status"], row["status"], actor, f"Patched: {reason}")
        self.conn.commit()

        cursor.execute("SELECT * FROM spec_requirements WHERE change_id = ? AND req_id = ?;", (change_id, req_id))
        return dict(cursor.fetchone())

    def flex_deprecate_requirement(
        self,
        change_id: str,
        req_id: str,
        reason: str,
        actor: str = "analyst"
    ) -> Dict[str, Any]:
        """Soft-deprecate an existing requirement without deleting history."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM spec_requirements WHERE change_id = ? AND req_id = ?;", (change_id, req_id))
        row = cursor.fetchone()
        if not row:
            raise FlexibleEngineException(f"Requirement not found: {req_id}")

        self.conn.execute("""
            UPDATE spec_requirements SET status = 'DEPRECATED', updated_at = CURRENT_TIMESTAMP
            WHERE change_id = ? AND req_id = ?;
        """, (change_id, req_id))

        self._log_audit(change_id, "requirement", req_id, row["status"], "DEPRECATED", actor, f"Deprecated: {reason}")
        self.conn.commit()
        return {"req_id": req_id, "status": "DEPRECATED", "reason": reason}

    def flex_quick_add_constraint(
        self,
        change_id: str,
        req_type: str,  # 'BR', 'INT', 'AC'
        title: str,
        content: str,
        mapped_ac: Optional[str] = None,
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Quickly add an in-flight business rule or edge case while coding."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM spec_requirements WHERE change_id = ? AND type = ?;", (change_id, req_type))
        count = cursor.fetchone()["count"] + 1
        req_id = f"{req_type}-QUICK-{count:03d}"

        self.conn.execute("""
            INSERT INTO spec_requirements (req_id, change_id, type, tag, title, given_when_then, status)
            VALUES (?, ?, ?, 'CONFIRMED', ?, ?, 'SPECIFIED');
        """, (req_id, change_id, req_type, title, content))

        self._log_audit(change_id, "requirement", req_id, None, "SPECIFIED", actor, f"Quick added in-flight constraint (mapped: {mapped_ac})")
        self.conn.commit()
        return {"req_id": req_id, "type": req_type, "title": title}

    def flex_supersede_decision(
        self,
        change_id: str,
        old_adr_id: str,
        new_decision: str,
        rationale: str,
        author: str = "architect"
    ) -> Dict[str, Any]:
        """Mark an ADR/Decision as SUPERSEDED and record the replacement in-place."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM decision_ledger WHERE change_id = ? AND decision_id = ?;", (change_id, old_adr_id))
        old_row = cursor.fetchone()
        if not old_row:
            raise FlexibleEngineException(f"Decision/ADR not found: {old_adr_id}")

        new_decision_id = f"{old_adr_id}.1"
        self.conn.execute("""
            UPDATE decision_ledger
            SET status = 'SUPERSEDED', superseded_by = ?
            WHERE change_id = ? AND decision_id = ?;
        """, (new_decision_id, change_id, old_adr_id))

        self.conn.execute("""
            INSERT INTO decision_ledger (decision_id, change_id, type, decision, reasoning, status, phase, author)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
        """, (new_decision_id, change_id, old_row["type"], new_decision, rationale, old_row["phase"], author))

        self._log_audit(change_id, "decision", old_adr_id, "ACTIVE", "SUPERSEDED", author, f"Superseded by {new_decision_id}")
        self._log_audit(change_id, "decision", new_decision_id, None, "ACTIVE", author, f"Replaced {old_adr_id}")
        self.conn.commit()

        return {"superseded": old_adr_id, "active_replacement": new_decision_id}

    def flex_patch_schema_column(
        self,
        change_id: str,
        table_name: str,
        action: str,  # 'add_col', 'modify_col', 'drop_col'
        col_def: Dict[str, Any],  # {"name": "...", "type": "...", "nullable": True}
        reason: str,
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Surgically modify column definition inside design_schemas.columns_json."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT columns_json FROM design_schemas WHERE change_id = ? AND table_name = ?;", (change_id, table_name))
        row = cursor.fetchone()
        if not row:
            raise FlexibleEngineException(f"Schema for table '{table_name}' not found.")

        try:
            columns = json.loads(row["columns_json"])
        except Exception:
            columns = []

        col_name = col_def.get("name")
        if not col_name:
            raise FlexibleEngineException("col_def must include a 'name' field.")

        if action == "add_col":
            # Check if column already exists
            if any(c.get("name") == col_name for c in columns):
                raise FlexibleEngineException(f"Column '{col_name}' already exists in table '{table_name}'.")
            columns.append(col_def)

        elif action == "modify_col":
            found = False
            for i, c in enumerate(columns):
                if c.get("name") == col_name:
                    columns[i] = col_def
                    found = True
                    break
            if not found:
                raise FlexibleEngineException(f"Column '{col_name}' not found to modify.")

        elif action == "drop_col":
            columns = [c for c in columns if c.get("name") != col_name]

        else:
            raise FlexibleEngineException(f"Invalid column action: {action}. Must be add_col, modify_col, or drop_col.")

        self.conn.execute("""
            UPDATE design_schemas SET columns_json = ?, status = 'REVISED'
            WHERE change_id = ? AND table_name = ?;
        """, (json.dumps(columns), change_id, table_name))

        self._log_audit(change_id, "schema_column", f"{table_name}.{col_name}", None, action, actor, reason)
        self.conn.commit()

        return {"table_name": table_name, "action": action, "column": col_name, "status": "REVISED"}

    def flex_patch_endpoint(
        self,
        change_id: str,
        endpoint_id: Union[int, str],
        field: str,
        new_val: Any,
        reason: str,
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Surgically patch an endpoint field (error_codes_json, response_schema_json, etc.)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM design_endpoints WHERE change_id = ? AND id = ?;", (change_id, endpoint_id))
        row = cursor.fetchone()
        if not row:
            raise FlexibleEngineException(f"Endpoint with id {endpoint_id} not found.")

        val_str = json.dumps(new_val) if isinstance(new_val, (dict, list)) else str(new_val)
        sql = f"UPDATE design_endpoints SET {field} = ? WHERE change_id = ? AND id = ?;"
        self.conn.execute(sql, (val_str, change_id, endpoint_id))

        self._log_audit(change_id, "endpoint", str(endpoint_id), None, field, actor, reason)
        self.conn.commit()
        return {"endpoint_id": endpoint_id, "field": field, "status": "UPDATED"}

    # =========================================================================
    # 2. FLEXIBLE TASK GRAPH MUTATIONS
    # =========================================================================
    def flex_task_split(
        self,
        change_id: str,
        task_id: str,
        subtasks: List[Dict[str, Any]],
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Split a large task into 2+ smaller subtasks."""
        if len(subtasks) < 2:
            raise FlexibleEngineException("Splitting a task requires at least 2 subtask definitions.")

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, task_id))
        orig = cursor.fetchone()
        if not orig:
            raise FlexibleEngineException(f"Task not found: {task_id}")

        base_order = orig["order_index"]
        created_ids = []

        for i, sub in enumerate(subtasks, start=1):
            sub_id = f"{task_id}.{i}"
            order = base_order + (i * 0.1)
            mapped_acs = json.dumps(sub.get("mapped_acs", json.loads(orig["mapped_acs_json"])))
            deps = json.dumps(sub.get("depends_on", json.loads(orig["depends_on_json"] or "[]")))

            self.conn.execute("""
                INSERT INTO task_graph (task_id, change_id, order_index, title, target_file, mapped_acs_json, depends_on_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'TODO');
            """, (sub_id, change_id, int(order * 10), sub.get("title", f"Subtask {i}"), sub.get("target_file", orig["target_file"]), mapped_acs, deps))
            created_ids.append(sub_id)

        # Mark original task as COMPLETED or removed
        self.conn.execute("""
            UPDATE task_graph SET status = 'COMPLETED', test_output = 'SPLIT_INTO_SUBTASKS', completed_at = CURRENT_TIMESTAMP
            WHERE change_id = ? AND task_id = ?;
        """, (change_id, task_id))

        self._log_audit(change_id, "task", task_id, orig["status"], "SPLIT", actor, f"Split into: {created_ids}")
        self.conn.commit()

        return {"original_task": task_id, "subtasks_created": created_ids}

    def flex_task_insert_urgent(
        self,
        change_id: str,
        after_task_id: str,
        new_task_def: Dict[str, Any],
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Insert an urgent task immediately following an existing task."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT order_index FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, after_task_id))
        prior = cursor.fetchone()
        if not prior:
            raise FlexibleEngineException(f"Preceding task '{after_task_id}' not found.")

        # Shift all succeeding task order indices up by 1
        new_order = prior["order_index"] + 1
        self.conn.execute("""
            UPDATE task_graph SET order_index = order_index + 1
            WHERE change_id = ? AND order_index >= ?;
        """, (change_id, new_order))

        task_id = new_task_def.get("task_id", f"{after_task_id}-URGENT")
        mapped_acs = json.dumps(new_task_def.get("mapped_acs", []))
        deps = json.dumps(new_task_def.get("depends_on", [after_task_id]))

        self.conn.execute("""
            INSERT INTO task_graph (task_id, change_id, order_index, title, target_file, mapped_acs_json, depends_on_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'TODO');
        """, (task_id, change_id, new_order, new_task_def["title"], new_task_def["target_file"], mapped_acs, deps))

        self._log_audit(change_id, "task", task_id, None, "TODO", actor, f"Urgent task inserted after {after_task_id}")
        self.conn.commit()

        return {"inserted_task_id": task_id, "order_index": new_order}

    def flex_task_update_scope(
        self,
        change_id: str,
        task_id: str,
        patch_data: Dict[str, Any],
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Update target_file or description for a task."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, task_id))
        task = cursor.fetchone()
        if not task:
            raise FlexibleEngineException(f"Task not found: {task_id}")

        allowed = {"title", "target_file"}
        updates = []
        params = []
        for k, v in patch_data.items():
            if k in allowed:
                updates.append(f"{k} = ?")
                params.append(v)

        if updates:
            params.extend([change_id, task_id])
            self.conn.execute(f"UPDATE task_graph SET {', '.join(updates)} WHERE change_id = ? AND task_id = ?;", params)
            self._log_audit(change_id, "task", task_id, task["status"], task["status"], actor, f"Scope updated: {patch_data}")
            self.conn.commit()

        return {"task_id": task_id, "status": "UPDATED"}

    def flex_task_reorder(
        self,
        change_id: str,
        task_order_map: Dict[str, int],  # {"T1": 1, "T3": 2, "T2": 3}
        actor: str = "developer"
    ) -> Dict[str, Any]:
        """Reorder task execution sequence."""
        for task_id, new_order in task_order_map.items():
            self.conn.execute("""
                UPDATE task_graph SET order_index = ? WHERE change_id = ? AND task_id = ?;
            """, (new_order, change_id, task_id))

        self._log_audit(change_id, "task_graph", "all", None, "REORDERED", actor, f"New order: {task_order_map}")
        self.conn.commit()
        return {"reordered_tasks": len(task_order_map)}

    # =========================================================================
    # 3. BLAST-RADIUS ANALYSIS & SELECTIVE INVALIDATION
    # =========================================================================
    def flex_amendment_preview_impact(
        self,
        change_id: str,
        item_type: str,  # 'requirement' or 'decision' or 'schema'
        item_id: str
    ) -> Dict[str, Any]:
        """Scan downstream dependency graph to preview affected tasks and test scenarios."""
        cursor = self.conn.cursor()
        impacted_tasks = []
        impacted_test_scenarios = []

        if item_type == "requirement":
            # Search tasks that map this requirement
            cursor.execute("SELECT task_id, title, status, mapped_acs_json FROM task_graph WHERE change_id = ?;", (change_id,))
            for t in cursor.fetchall():
                try:
                    acs = json.loads(t["mapped_acs_json"] or "[]")
                    if item_id in acs:
                        impacted_tasks.append({"task_id": t["task_id"], "title": t["title"], "current_status": t["status"]})
                except Exception:
                    pass

            # Search QA test scenarios mapping this AC
            cursor.execute("SELECT scenario_id, title, execution_status FROM qa_test_scenarios WHERE change_id = ? AND mapped_ac_id = ?;", (change_id, item_id))
            impacted_test_scenarios = [dict(r) for r in cursor.fetchall()]

        elif item_type in ("decision", "schema"):
            # When an architectural decision or schema changes, find tasks referencing that file/keyword
            cursor.execute("SELECT task_id, title, status FROM task_graph WHERE change_id = ?;", (change_id,))
            impacted_tasks = [dict(r) for r in cursor.fetchall()]

        return {
            "change_id": change_id,
            "item_type": item_type,
            "item_id": item_id,
            "impacted_tasks_count": len(impacted_tasks),
            "impacted_tasks": impacted_tasks,
            "impacted_test_scenarios_count": len(impacted_test_scenarios),
            "impacted_test_scenarios": impacted_test_scenarios
        }

    def flex_amendment_apply_and_invalidate(
        self,
        change_id: str,
        item_type: str,
        item_id: str,
        patch_data: Dict[str, Any],
        actor: str = "architect"
    ) -> Dict[str, Any]:
        """Apply amendment and SELECTIVELY invalidate only impacted tasks to NEEDS_REVISION."""
        # Preview impact first
        preview = self.flex_amendment_preview_impact(change_id, item_type, item_id)

        # Apply the amendment
        if item_type == "requirement":
            self.flex_patch_requirement(change_id, item_id, patch_data, reason="Selective invalidation patch", actor=actor)

        # Invalidate impacted tasks that were already COMPLETED or IN_PROGRESS
        invalidated_task_ids = []
        for t in preview["impacted_tasks"]:
            t_id = t["task_id"]
            if t["current_status"] in ("COMPLETED", "IN_PROGRESS"):
                self.conn.execute("""
                    UPDATE task_graph SET status = 'NEEDS_REVISION' WHERE change_id = ? AND task_id = ?;
                """, (change_id, t_id))
                self._log_audit(change_id, "task", t_id, t["current_status"], "NEEDS_REVISION", actor, f"Invalidated by amendment on {item_type} {item_id}")
                invalidated_task_ids.append(t_id)

        self.conn.commit()

        return {
            "amendment_applied": True,
            "target_item": f"{item_type}:{item_id}",
            "invalidated_tasks": invalidated_task_ids,
            "preserved_tasks_count": len(preview["impacted_tasks"]) - len(invalidated_task_ids)
        }

    # =========================================================================
    # 4. FAST NOTES & BREAK-GLASS OVERRIDES
    # =========================================================================
    def flex_amend_phase_note(
        self,
        change_id: str,
        phase: str,
        amendment_note: str,
        actor: str = "orchestrator"
    ) -> Dict[str, Any]:
        """Quickly log an in-flight amendment note to phase progress."""
        self.conn.execute("""
            INSERT INTO phase_progress (change_id, phase, status, agent, summary_note, next_action)
            VALUES (?, ?, 'IN_PROGRESS', ?, ?, 'CONTINUE_WITH_AMENDMENT');
        """, (change_id, phase, actor, f"[AMENDMENT] {amendment_note}"))

        self._log_audit(change_id, "phase_progress", phase, None, "AMENDED", actor, amendment_note)
        self.conn.commit()
        return {"phase": phase, "note": amendment_note, "status": "RECORDED"}

    def flex_qa_mark_known_issue(
        self,
        change_id: str,
        bug_id: str,
        justification: str,
        actor: str = "qa"
    ) -> Dict[str, Any]:
        """Downgrade a bug to KNOWN_ISSUE to unblock release while maintaining auditability."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status, severity FROM qa_bugs WHERE change_id = ? AND bug_id = ?;", (change_id, bug_id))
        bug = cursor.fetchone()
        if not bug:
            raise FlexibleEngineException(f"Bug not found: {bug_id}")

        self.conn.execute("""
            UPDATE qa_bugs
            SET status = 'KNOWN_ISSUE', justification_for_known_issue = ?
            WHERE change_id = ? AND bug_id = ?;
        """, (justification, change_id, bug_id))

        self._log_audit(change_id, "bug", bug_id, bug["status"], "KNOWN_ISSUE", actor, justification)
        self.conn.commit()

        return {"bug_id": bug_id, "status": "KNOWN_ISSUE", "justification": justification}

    def flex_break_glass_override(
        self,
        change_id: str,
        gate_name: str,
        rule_name: str,
        reason: str,
        approved_by: str
    ) -> Dict[str, Any]:
        """Controlled break-glass bypass of a specific gate rule with mandatory audit log."""
        self.conn.execute("""
            INSERT INTO gate_history (change_id, gate_name, status, approver, override_reason)
            VALUES (?, ?, 'PASSED', ?, ?);
        """, (change_id, gate_name, approved_by, f"BREAK_GLASS [{rule_name}]: {reason}"))

        self._log_audit(change_id, "gate_override", gate_name, "BLOCKED", "PASSED", approved_by, f"Bypassed {rule_name}: {reason}")
        self.conn.commit()

        return {
            "gate_name": gate_name,
            "bypassed_rule": rule_name,
            "status": "PASSED",
            "approved_by": approved_by,
            "audit_recorded": True
        }
