"""
Domain Services for SDLC Context Engine.
Implements Baton, Intake, Knowledge FTS, Requirements, Design,
Implementation, QA, Role Memory, and Dual-Layer Markdown Sync.
Zero external dependencies.
"""

import os
import json
import sqlite3
from typing import Optional, Dict, Any, List, Union


class SDLCServiceException(Exception):
    pass


class SDLCServices:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # =========================================================================
    # DOMAIN 3: BATON & INTER-PHASE CONTEXT PROTOCOL
    # =========================================================================
    def handoff_create(
        self,
        change_id: str,
        from_phase: str,
        to_phase: str,
        author_role: str,
        key_decisions: List[str],
        risky_areas: List[str],
        reading_order: List[str],
        contentious_points: Optional[List[str]] = None,
        implicit_assumptions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Record an inter-phase baton handoff."""
        self.conn.execute("""
            INSERT INTO phase_handoff (
                change_id, from_phase, to_phase, author_role,
                key_decisions, contentious_points, implicit_assumptions, risky_areas, reading_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            change_id, from_phase, to_phase, author_role,
            json.dumps(key_decisions),
            json.dumps(contentious_points or []),
            json.dumps(implicit_assumptions or []),
            json.dumps(risky_areas),
            json.dumps(reading_order)
        ))
        self.conn.commit()
        return {"change_id": change_id, "from_phase": from_phase, "to_phase": to_phase, "status": "CREATED"}

    def handoff_get_latest(self, change_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM phase_handoff WHERE change_id = ? ORDER BY id DESC LIMIT 1;", (change_id,))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        for field in ("key_decisions", "contentious_points", "implicit_assumptions", "risky_areas", "reading_order"):
            try:
                res[field] = json.loads(res[field])
            except Exception:
                pass
        return res

    def handoff_get_reading_order(self, change_id: str) -> List[str]:
        latest = self.handoff_get_latest(change_id)
        return latest.get("reading_order", []) if latest else []

    def handoff_get_risky_areas(self, change_id: str) -> List[str]:
        latest = self.handoff_get_latest(change_id)
        return latest.get("risky_areas", []) if latest else []

    def handoff_get_contentious_points(self, change_id: str) -> List[str]:
        latest = self.handoff_get_latest(change_id)
        return latest.get("contentious_points", []) if latest else []

    def decision_record(
        self,
        change_id: str,
        decision_id: str,
        type: str,
        decision: str,
        reasoning: str,
        rejected_alternatives: Optional[str] = None,
        phase: str = "S3",
        author: str = "architect"
    ) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO decision_ledger (decision_id, change_id, type, decision, reasoning, rejected_alternatives, phase, author)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (decision_id, change_id, type, decision, reasoning, rejected_alternatives, phase, author))
        self.conn.commit()
        return {"decision_id": decision_id, "status": "RECORDED"}

    def decision_list(self, change_id: str, type: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if type:
            cursor.execute("SELECT * FROM decision_ledger WHERE change_id = ? AND type = ? ORDER BY created_at ASC;", (change_id, type))
        else:
            cursor.execute("SELECT * FROM decision_ledger WHERE change_id = ? ORDER BY created_at ASC;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def decision_get(self, decision_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM decision_ledger WHERE decision_id = ?;", (decision_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def decision_search(self, change_id: str, query: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM decision_ledger
            WHERE change_id = ? AND (decision LIKE ? OR reasoning LIKE ?);
        """, (change_id, f"%{query}%", f"%{query}%"))
        return [dict(r) for r in cursor.fetchall()]

    def progress_mark(
        self,
        change_id: str,
        phase: str,
        status: str,
        summary_note: str,
        next_action: Optional[str] = None,
        agent: str = "orchestrator"
    ) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO phase_progress (change_id, phase, status, agent, summary_note, next_action)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (change_id, phase, status, agent, summary_note, next_action))
        self.conn.commit()
        return {"phase": phase, "status": status, "summary": summary_note}

    def progress_get_timeline(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM phase_progress WHERE change_id = ? ORDER BY id ASC;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def progress_get_next_action(self, change_id: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT next_action FROM phase_progress WHERE change_id = ? ORDER BY id DESC LIMIT 1;", (change_id,))
        row = cursor.fetchone()
        return row["next_action"] if row else None

    def glossary_define(self, change_id: str, term: str, definition: str, introduced_phase: str = "S1") -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO change_glossary (change_id, term, definition, introduced_phase, status)
            VALUES (?, ?, ?, ?, 'ACTIVE')
            ON CONFLICT(change_id, term) DO UPDATE SET definition = excluded.definition, updated_at = CURRENT_TIMESTAMP;
        """, (change_id, term, definition, introduced_phase))
        self.conn.commit()
        return {"term": term, "definition": definition}

    def glossary_lookup(self, change_id: str, term: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT definition FROM change_glossary WHERE change_id = ? AND term = ?;", (change_id, term))
        row = cursor.fetchone()
        return row["definition"] if row else None

    def bridge_export_service(self, change_id: str, service_name: str, endpoint_or_symbol: str, contract_summary: str) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO cross_spec_bridge (change_id, exported_service, endpoint_or_symbol, contract_summary)
            VALUES (?, ?, ?, ?);
        """, (change_id, service_name, endpoint_or_symbol, contract_summary))
        self.conn.commit()
        return {"exported_service": service_name, "status": "EXPORTED"}

    def bridge_query_dependencies(self, target_service: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cross_spec_bridge WHERE exported_service LIKE ?;", (f"%{target_service}%",))
        return [dict(r) for r in cursor.fetchall()]

    # =========================================================================
    # DOMAIN 4: INTAKE & UI SPECIFICATION
    # =========================================================================
    def intake_save_raw_ticket(
        self,
        change_id: str,
        ticket_id: str,
        title: str,
        description: str,
        raw_status: Optional[str] = None,
        assignee: Optional[str] = None,
        figma_url: Optional[str] = None
    ) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO intake_packages (ticket_id, change_id, title, description, raw_status, assignee, figma_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                raw_status = excluded.raw_status,
                assignee = excluded.assignee,
                figma_url = excluded.figma_url;
        """, (ticket_id, change_id, title, description, raw_status, assignee, figma_url))
        self.conn.commit()
        return {"ticket_id": ticket_id, "status": "SAVED"}

    def intake_save_ui_screen(
        self,
        change_id: str,
        screen_id: str,
        screen_name: str,
        purpose: str,
        route: Optional[str],
        figma_image_path: Optional[str],
        layout_spec: str,
        components_json: Union[List, Dict, str],
        data_fields_json: Union[List, Dict, str],
        figma_url: Optional[str] = None
    ) -> Dict[str, Any]:
        comp_str = json.dumps(components_json) if not isinstance(components_json, str) else components_json
        fields_str = json.dumps(data_fields_json) if not isinstance(data_fields_json, str) else data_fields_json

        self.conn.execute("""
            INSERT INTO intake_ui_screens (screen_id, change_id, screen_name, purpose, route, figma_image_path, figma_url, layout_spec, components_json, data_fields_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(screen_id) DO UPDATE SET
                screen_name = excluded.screen_name,
                purpose = excluded.purpose,
                route = excluded.route,
                figma_image_path = excluded.figma_image_path,
                layout_spec = excluded.layout_spec,
                components_json = excluded.components_json,
                data_fields_json = excluded.data_fields_json;
        """, (screen_id, change_id, screen_name, purpose, route, figma_image_path, figma_url, layout_spec, comp_str, fields_str))
        self.conn.commit()
        return {"screen_id": screen_id, "status": "SAVED"}

    def intake_get_summary(self, change_id: str) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM intake_packages WHERE change_id = ?;", (change_id,))
        pkg = cursor.fetchone()
        cursor.execute("SELECT screen_id, screen_name, route FROM intake_ui_screens WHERE change_id = ?;", (change_id,))
        screens = [dict(r) for r in cursor.fetchall()]
        return {
            "ticket": dict(pkg) if pkg else None,
            "ui_screens_count": len(screens),
            "ui_screens": screens
        }

    def intake_get_ui_screen(self, change_id: str, screen_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM intake_ui_screens WHERE change_id = ? AND screen_id = ?;", (change_id, screen_id))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        for f in ("components_json", "data_fields_json"):
            try:
                res[f] = json.loads(res[f])
            except Exception:
                pass
        return res

    def intake_list_ui_screens(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT screen_id, screen_name, route, purpose FROM intake_ui_screens WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def intake_attach_figma_ref(self, change_id: str, screen_id: str, figma_node_id: str, image_local_path: str) -> Dict[str, Any]:
        self.conn.execute("""
            UPDATE intake_ui_screens
            SET figma_url = coalesce(figma_url, '') || ' [node:' || ? || ']',
                figma_image_path = ?
            WHERE change_id = ? AND screen_id = ?;
        """, (figma_node_id, image_local_path, change_id, screen_id))
        self.conn.commit()
        return {"screen_id": screen_id, "image_path": image_local_path}

    # =========================================================================
    # DOMAIN 5: PROJECT KNOWLEDGE & DRIFT
    # =========================================================================
    def knowledge_set_topic(self, topic: str, content_json: Union[Dict, List, str], author: str = "onboarder") -> Dict[str, Any]:
        c_str = json.dumps(content_json) if not isinstance(content_json, str) else content_json
        self.conn.execute("""
            INSERT INTO project_knowledge (topic, content_json, version, last_updated_by)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(topic) DO UPDATE SET
                content_json = excluded.content_json,
                version = version + 1,
                last_updated_by = excluded.last_updated_by,
                updated_at = CURRENT_TIMESTAMP;
        """, (topic, c_str, author))

        # Also update knowledge_fts
        self.conn.execute("DELETE FROM knowledge_fts WHERE topic = ?;", (topic,))
        self.conn.execute("INSERT INTO knowledge_fts (topic, title, body_text) VALUES (?, ?, ?);", (topic, topic.capitalize(), c_str))
        self.conn.commit()
        return {"topic": topic, "status": "STORED"}

    def knowledge_get_topic(self, topic: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM project_knowledge WHERE topic = ?;", (topic,))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["content"] = json.loads(res["content_json"])
        except Exception:
            res["content"] = res["content_json"]
        return res

    def knowledge_get_section(self, topic: str, section_key: str) -> Any:
        topic_data = self.knowledge_get_topic(topic)
        if not topic_data or not isinstance(topic_data.get("content"), dict):
            return None
        return topic_data["content"].get(section_key)

    def knowledge_search(self, query: str, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if topic:
            cursor.execute("""
                SELECT topic, title, body_text FROM knowledge_fts
                WHERE topic = ? AND knowledge_fts MATCH ?;
            """, (topic, query))
        else:
            cursor.execute("""
                SELECT topic, title, body_text FROM knowledge_fts
                WHERE knowledge_fts MATCH ?;
            """, (query,))
        return [dict(r) for r in cursor.fetchall()]

    def knowledge_detect_drift(self, detected_manifest_facts: Dict[str, Any]) -> Dict[str, Any]:
        """Detect drift between actual detected code facts and stored context."""
        drift_items = []
        stack_topic = self.knowledge_get_topic("stack")
        stored_stack = stack_topic.get("content", {}) if stack_topic else {}

        for k, v in detected_manifest_facts.items():
            if k not in stored_stack:
                drift_items.append({"field": k, "status": "NEW_UNRECORDED", "detected": v})
            elif stored_stack[k] != v:
                drift_items.append({"field": k, "status": "MODIFIED", "stored": stored_stack[k], "detected": v})

        return {"drift_detected": len(drift_items) > 0, "drift_count": len(drift_items), "drifts": drift_items}

    def knowledge_diff_report(self) -> str:
        return "Drift check complete. Use knowledge_detect_drift with detected facts."

    def knowledge_apply_drift_patch(self, topic: str, patch_data: Dict[str, Any], reason: str, author: str = "context-refresh") -> Dict[str, Any]:
        t = self.knowledge_get_topic(topic)
        base = t.get("content", {}) if (t and isinstance(t.get("content"), dict)) else {}
        base.update(patch_data)
        return self.knowledge_set_topic(topic, base, author=author)

    # =========================================================================
    # DOMAIN 6: REQUIREMENTS & STRIDE (Analyst S1/S2)
    # =========================================================================
    def spec_add_requirement(self, change_id: str, req_id: str, type: str, tag: str, title: str, gwt: Optional[str] = None) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO spec_requirements (req_id, change_id, type, tag, title, given_when_then, status)
            VALUES (?, ?, ?, ?, ?, ?, 'SPECIFIED')
            ON CONFLICT(req_id) DO UPDATE SET tag = excluded.tag, title = excluded.title, given_when_then = excluded.given_when_then;
        """, (req_id, change_id, type, tag, title, gwt))
        self.conn.commit()
        return {"req_id": req_id, "status": "SPECIFIED"}

    def spec_list_requirements(self, change_id: str, type: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        query = "SELECT * FROM spec_requirements WHERE change_id = ?"
        params = [change_id]
        if type:
            query += " AND type = ?"
            params.append(type)
        if tag:
            query += " AND tag = ?"
            params.append(tag)
        query += " ORDER BY req_id ASC;"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

    def spec_get_requirement(self, req_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM spec_requirements WHERE req_id = ?;", (req_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def spec_add_edge_case(self, change_id: str, category: str, scenario: str, expected_behavior: str, mapped_ac_id: Optional[str] = None) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO spec_edge_cases (change_id, category, scenario, expected_behavior, mapped_ac_id)
            VALUES (?, ?, ?, ?, ?);
        """, (change_id, category, scenario, expected_behavior, mapped_ac_id))
        self.conn.commit()
        return {"scenario": scenario, "category": category, "status": "STORED"}

    def spec_list_edge_cases(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM spec_edge_cases WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def spec_record_clarification(self, change_id: str, question: str, impact: str, proposed_guess: str) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM spec_clarifications WHERE change_id = ? AND status = 'OPEN';", (change_id,))
        if cursor.fetchone()["count"] >= 5:
            raise SDLCServiceException("Clarification budget exceeded: maximum 5 open clarification questions allowed.")

        self.conn.execute("""
            INSERT INTO spec_clarifications (change_id, question, impact, proposed_guess, status)
            VALUES (?, ?, ?, ?, 'OPEN');
        """, (change_id, question, impact, proposed_guess))
        self.conn.commit()
        return {"question": question, "status": "OPEN"}

    def spec_list_clarifications(self, change_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if status:
            cursor.execute("SELECT * FROM spec_clarifications WHERE change_id = ? AND status = ?;", (change_id, status))
        else:
            cursor.execute("SELECT * FROM spec_clarifications WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def spec_answer_clarification(self, clarification_id: int, answer: str) -> Dict[str, Any]:
        self.conn.execute("""
            UPDATE spec_clarifications SET answer = ?, status = 'ANSWERED' WHERE id = ?;
        """, (answer, clarification_id))
        self.conn.commit()
        return {"clarification_id": clarification_id, "status": "ANSWERED"}

    def spec_add_stride_threat(self, threat_id: str, change_id: str, category: str, description: str, mitigation_strategy: str, mapped_ac_id: Optional[str] = None) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO spec_stride_threats (threat_id, change_id, category, description, mitigation_strategy, mapped_ac_id)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (threat_id, change_id, category, description, mitigation_strategy, mapped_ac_id))
        self.conn.commit()
        return {"threat_id": threat_id, "status": "STORED"}

    def spec_commit_spec_lock(self, change_id: str, scope: str = "standard") -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM spec_requirements WHERE change_id = ? AND tag IN ('UNCLEAR', 'MISSING');", (change_id,))
        unclear_count = cursor.fetchone()["count"]
        if unclear_count > 0:
            raise SDLCServiceException(f"Cannot lock spec: {unclear_count} requirements still tagged UNCLEAR/MISSING.")

        self.conn.execute("UPDATE change_state SET scope = ? WHERE change_id = ?;", (scope, change_id))
        self.conn.commit()
        return {"change_id": change_id, "spec_locked": True, "scope": scope}

    # =========================================================================
    # DOMAIN 7: TECHNICAL DESIGN & CONTRACTS (Architect S3)
    # =========================================================================
    def design_add_adr(self, change_id: str, adr_id: str, title: str, context: str, options: List[str], chosen: str, rationale: str) -> Dict[str, Any]:
        if len(options) < 2:
            raise SDLCServiceException("ADR hard rule violated: at least 2 options must be considered.")

        decision_text = f"{title}: Chosen '{chosen}'"
        reasoning_text = f"Context: {context}. Rationale: {rationale}"
        rejected_text = json.dumps([opt for opt in options if opt != chosen])

        return self.decision_record(change_id, adr_id, type="design", decision=decision_text, reasoning=reasoning_text, rejected_alternatives=rejected_text)

    def design_list_adrs(self, change_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.decision_list(change_id, type="design")

    def design_get_adr(self, adr_id: str) -> Optional[Dict[str, Any]]:
        return self.decision_get(adr_id)

    def design_set_schema(self, change_id: str, table_name: str, columns: List[Dict], indexes: Optional[List] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        col_str = json.dumps(columns)
        idx_str = json.dumps(indexes or [])
        self.conn.execute("""
            INSERT INTO design_schemas (change_id, table_name, columns_json, indexes_json, migration_notes, status)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE')
            ON CONFLICT(change_id, table_name) DO UPDATE SET
                columns_json = excluded.columns_json,
                indexes_json = excluded.indexes_json,
                migration_notes = excluded.migration_notes;
        """, (change_id, table_name, col_str, idx_str, notes))
        self.conn.commit()
        return {"table_name": table_name, "status": "STORED"}

    def design_get_schema(self, change_id: str, table_name: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM design_schemas WHERE change_id = ? AND table_name = ?;", (change_id, table_name))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        for f in ("columns_json", "indexes_json"):
            try:
                res[f] = json.loads(res[f])
            except Exception:
                pass
        return res

    def design_list_schemas(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT table_name, status, migration_notes FROM design_schemas WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def design_set_endpoint(self, change_id: str, method: str, path: str, req_schema: Optional[Dict] = None, res_schema: Optional[Dict] = None, errors: Optional[List] = None) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO design_endpoints (change_id, method, path, request_schema_json, response_schema_json, error_codes_json, status)
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
            ON CONFLICT(change_id, method, path) DO UPDATE SET
                request_schema_json = excluded.request_schema_json,
                response_schema_json = excluded.response_schema_json,
                error_codes_json = excluded.error_codes_json;
        """, (change_id, method.upper(), path, json.dumps(req_schema or {}), json.dumps(res_schema or {}), json.dumps(errors or [])))
        self.conn.commit()
        return {"method": method.upper(), "path": path, "status": "STORED"}

    def design_get_endpoint(self, change_id: str, method: str, path: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM design_endpoints WHERE change_id = ? AND method = ? AND path = ?;", (change_id, method.upper(), path))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        for f in ("request_schema_json", "response_schema_json", "error_codes_json"):
            try:
                res[f] = json.loads(res[f])
            except Exception:
                pass
        return res

    def design_list_endpoints(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, method, path, status FROM design_endpoints WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def design_add_component(self, change_id: str, component_id: str, name: str, layer: str, responsibility: str, deps: Optional[List[str]] = None) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO design_components (component_id, change_id, name, layer, responsibility, dependencies_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(component_id) DO UPDATE SET responsibility = excluded.responsibility, dependencies_json = excluded.dependencies_json;
        """, (component_id, change_id, name, layer, responsibility, json.dumps(deps or [])))
        self.conn.commit()
        return {"component_id": component_id, "name": name}

    def design_list_components(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM design_components WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def design_commit_review(self, change_id: str) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM task_graph WHERE change_id = ?;", (change_id,))
        if cursor.fetchone()["count"] == 0:
            raise SDLCServiceException("Cannot complete S3 design review: task graph is empty.")
        return {"change_id": change_id, "design_review_ready": True}

    # =========================================================================
    # DOMAIN 8: TASK GRAPH & IMPLEMENTATION (Developer S4/S6)
    # =========================================================================
    def task_create(self, change_id: str, task_id: str, order: int, title: str, file: str, mapped_acs: List[str], depends_on: Optional[List[str]] = None, is_checkpoint: bool = False) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO task_graph (task_id, change_id, order_index, title, target_file, mapped_acs_json, depends_on_json, is_checkpoint, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TODO');
        """, (task_id, change_id, order, title, file, json.dumps(mapped_acs), json.dumps(depends_on or []), 1 if is_checkpoint else 0))
        self.conn.commit()
        return {"task_id": task_id, "order": order, "status": "TODO"}

    def task_get_next_active(self, change_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        # Find first TODO task whose dependencies are all COMPLETED
        cursor.execute("SELECT * FROM task_graph WHERE change_id = ? AND status = 'TODO' ORDER BY order_index ASC;", (change_id,))
        candidates = cursor.fetchall()
        for cand in candidates:
            deps = json.loads(cand["depends_on_json"] or "[]")
            all_done = True
            for d in deps:
                cursor.execute("SELECT status FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, d))
                dep_row = cursor.fetchone()
                if not dep_row or dep_row["status"] != "COMPLETED":
                    all_done = False
                    break
            if all_done:
                res = dict(cand)
                res["mapped_acs"] = json.loads(res["mapped_acs_json"])
                res["depends_on"] = json.loads(res["depends_on_json"])
                return res
        return None

    def task_list_all(self, change_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if status:
            cursor.execute("SELECT * FROM task_graph WHERE change_id = ? AND status = ? ORDER BY order_index ASC;", (change_id, status))
        else:
            cursor.execute("SELECT * FROM task_graph WHERE change_id = ? ORDER BY order_index ASC;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def task_get_details(self, change_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM task_graph WHERE change_id = ? AND task_id = ?;", (change_id, task_id))
        row = cursor.fetchone()
        return dict(row) if row else None

    def dev_record_deviation(self, change_id: str, task_id: str, dev_type: str, desc: str, impact: str) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO dev_deviations (change_id, task_id, deviation_type, description, impact)
            VALUES (?, ?, ?, ?, ?);
        """, (change_id, task_id, dev_type, desc, impact))
        self.conn.commit()
        return {"task_id": task_id, "deviation_type": dev_type, "status": "RECORDED"}

    def dev_list_deviations(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM dev_deviations WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def dev_submit_checkpoint(self, change_id: str, checkpoint_name: str, passed: int, failed: int, coverage_pct: float) -> Dict[str, Any]:
        is_clean = failed == 0 and coverage_pct >= 80.0
        return {
            "checkpoint": checkpoint_name,
            "tests_passed": passed,
            "tests_failed": failed,
            "coverage_pct": coverage_pct,
            "checkpoint_passed": is_clean
        }

    def dev_get_bugs_to_fix(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM qa_bugs WHERE change_id = ? AND status IN ('OPEN', 'IN_FIX');", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def dev_generate_release_plan(self, change_id: str, migration_steps: str, rollback_plan: str, post_checks: str) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO release_plans (change_id, migration_steps, rollback_plan, post_checks, status)
            VALUES (?, ?, ?, ?, 'APPROVED')
            ON CONFLICT(change_id) DO UPDATE SET
                migration_steps = excluded.migration_steps,
                rollback_plan = excluded.rollback_plan,
                post_checks = excluded.post_checks;
        """, (change_id, migration_steps, rollback_plan, post_checks))
        self.conn.commit()
        return {"change_id": change_id, "release_plan_status": "APPROVED"}

    def dev_get_release_plan(self, change_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM release_plans WHERE change_id = ?;", (change_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # =========================================================================
    # DOMAIN 9: QUALITY ASSURANCE & BUG RCA (QA S5)
    # =========================================================================
    def qa_create_test_scenario(self, change_id: str, scenario_id: str, mapped_ac: str, title: str, steps: str, expected: str, priority: str = "P1") -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO qa_test_scenarios (scenario_id, change_id, mapped_ac_id, title, steps, expected_result, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (scenario_id, change_id, mapped_ac, title, steps, expected, priority))
        self.conn.commit()
        return {"scenario_id": scenario_id, "mapped_ac": mapped_ac, "status": "STORED"}

    def qa_list_test_scenarios(self, change_id: str, ac_id: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if ac_id:
            cursor.execute("SELECT * FROM qa_test_scenarios WHERE change_id = ? AND mapped_ac_id = ?;", (change_id, ac_id))
        else:
            cursor.execute("SELECT * FROM qa_test_scenarios WHERE change_id = ?;", (change_id,))
        return [dict(r) for r in cursor.fetchall()]

    def qa_get_verification_matrix(self, change_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT req_id, title, status FROM spec_requirements WHERE change_id = ? AND type = 'AC';", (change_id,))
        acs = cursor.fetchall()
        matrix = []
        for ac in acs:
            cursor.execute("SELECT scenario_id, priority, execution_status FROM qa_test_scenarios WHERE change_id = ? AND mapped_ac_id = ?;", (change_id, ac["req_id"]))
            tcs = [dict(r) for r in cursor.fetchall()]
            matrix.append({
                "ac_id": ac["req_id"],
                "ac_title": ac["title"],
                "ac_status": ac["status"],
                "test_scenarios_count": len(tcs),
                "test_scenarios": tcs
            })
        return matrix

    def qa_report_bug(self, change_id: str, bug_id: str, severity: str, classification: str, rca_phase: str, title: str, repro: str) -> Dict[str, Any]:
        from .state_machine import SDLCStateMachine
        sm = SDLCStateMachine(self.conn)
        return sm.bug_open(change_id, bug_id, title, severity, classification, rca_phase, repro)

    def qa_list_bugs(self, change_id: str, severity: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        q = "SELECT * FROM qa_bugs WHERE change_id = ?"
        p = [change_id]
        if severity:
            q += " AND severity = ?"
            p.append(severity)
        if status:
            q += " AND status = ?"
            p.append(status)
        cursor.execute(q, p)
        return [dict(r) for r in cursor.fetchall()]

    def qa_get_bug_details(self, bug_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM qa_bugs WHERE bug_id = ?;", (bug_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def qa_record_hollow_test(self, change_id: str, test_file: str, hollow_type: str, desc: str) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO qa_hollow_tests (change_id, test_file, hollow_type, description)
            VALUES (?, ?, ?, ?);
        """, (change_id, test_file, hollow_type, desc))
        self.conn.commit()
        return {"test_file": test_file, "hollow_type": hollow_type, "status": "FLAGGED"}

    def qa_record_verification(self, change_id: str, scope: str, total: int, passed: int, failed: int, coverage: float, verdict: str, notes: str) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO qa_verifications (change_id, test_scope, total_tests, passed_tests, failed_tests, coverage_pct, verdict, verdict_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (change_id, scope, total, passed, failed, coverage, verdict, notes))
        self.conn.commit()
        return {"change_id": change_id, "verdict": verdict, "passed_tests": passed, "failed_tests": failed}

    def qa_export_testcases(self, change_id: str, format: str = "json") -> Union[str, List]:
        tcs = self.qa_list_test_scenarios(change_id)
        if format == "json":
            return json.dumps(tcs, indent=2)
        elif format == "md":
            lines = ["| Scenario ID | AC | Title | Priority | Status |", "|---|---|---|---|---|"]
            for tc in tcs:
                lines.append(f"| {tc['scenario_id']} | {tc['mapped_ac_id']} | {tc['title']} | {tc['priority']} | {tc['execution_status']} |")
            return "\n".join(lines)
        return json.dumps(tcs)

    # =========================================================================
    # DOMAIN 11: ROLE MEMORY & DUAL-LAYER GIT SYNC
    # =========================================================================
    def memory_writeback(self, role: str, change_id: str, domain_tag: str, lesson: str, pattern: Optional[str] = None) -> Dict[str, Any]:
        self.conn.execute("""
            INSERT INTO role_memory (role, change_id, domain_tag, lesson_learned, reusable_pattern)
            VALUES (?, ?, ?, ?, ?);
        """, (role, change_id, domain_tag, lesson, pattern))
        self.conn.commit()
        return {"role": role, "domain_tag": domain_tag, "status": "SAVED"}

    def memory_search(self, role: str, domain_tag: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        q = "SELECT * FROM role_memory WHERE role = ?"
        p = [role]
        if domain_tag:
            q += " AND domain_tag = ?"
            p.append(domain_tag)
        if query:
            q += " AND lesson_learned LIKE ?"
            p.append(f"%{query}%")
        cursor.execute(q, p)
        return [dict(r) for r in cursor.fetchall()]

    def sync_export_all_markdown(self, change_id: str, output_dir: str) -> List[str]:
        """Export artifacts to human-readable Markdown files for Git commit and PR review."""
        os.makedirs(output_dir, exist_ok=True)
        exported = []

        # 1. Proposal & Spec Markdown
        reqs = self.spec_list_requirements(change_id)
        proposal_path = os.path.join(output_dir, "proposal.md")
        with open(proposal_path, "w", encoding="utf-8") as f:
            f.write(f"# Proposal for {change_id}\n\n## Acceptance Criteria\n\n")
            for r in reqs:
                f.write(f"- **{r['req_id']}** [{r['tag']}]: {r['title']}\n  {r.get('given_when_then') or ''}\n\n")
        exported.append(proposal_path)

        # 2. Design Markdown
        schemas = self.design_list_schemas(change_id)
        endpoints = self.design_list_endpoints(change_id)
        adrs = self.decision_list(change_id, type="design")
        design_path = os.path.join(output_dir, "design.md")
        with open(design_path, "w", encoding="utf-8") as f:
            f.write(f"# Technical Design for {change_id}\n\n## Architecture Decisions\n\n")
            for a in adrs:
                f.write(f"### {a['decision_id']}\n- Decision: {a['decision']}\n- Reasoning: {a['reasoning']}\n\n")
            f.write("## Database Schemas\n\n")
            for s in schemas:
                f.write(f"- Table `{s['table_name']}`: {s['status']}\n")
            f.write("\n## Endpoints\n\n")
            for e in endpoints:
                f.write(f"- `{e['method']} {e['path']}`\n")
        exported.append(design_path)

        # 3. Tasks Markdown
        tasks = self.task_list_all(change_id)
        tasks_path = os.path.join(output_dir, "tasks.md")
        with open(tasks_path, "w", encoding="utf-8") as f:
            f.write(f"# Tasks for {change_id}\n\n")
            for t in tasks:
                box = "[x]" if t["status"] == "COMPLETED" else "[ ]"
                f.write(f"- {box} **{t['task_id']}**: {t['title']} (`{t['target_file']}`)\n")
        exported.append(tasks_path)

        return exported

    def sync_import_all_markdown(self, change_id: str, source_dir: str) -> Dict[str, Any]:
        """Placeholder for bidirectional re-import from modified markdown."""
        return {"change_id": change_id, "source_dir": source_dir, "synced": True}

    # =========================================================================
    # DOMAIN 13: BATCH OPERATIONS & CHUNKY COMPOSITE QUERIES
    # =========================================================================
    def knowledge_index_file(self, file_path: str, doc_type: str = "context") -> Dict[str, Any]:
        """Index a single markdown file into project knowledge and FTS."""
        if not os.path.exists(file_path):
            raise SDLCServiceException(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        topic = os.path.splitext(os.path.basename(file_path))[0]
        self.conn.execute("""
            INSERT INTO project_knowledge (topic, content_json, version, last_updated_by)
            VALUES (?, ?, 1, 'indexer')
            ON CONFLICT(topic) DO UPDATE SET
                content_json = excluded.content_json,
                version = version + 1,
                updated_at = CURRENT_TIMESTAMP;
        """, (topic, json.dumps({"raw_markdown": content, "doc_type": doc_type})))
        self.conn.execute("DELETE FROM knowledge_fts WHERE topic = ?;", (topic,))
        self.conn.execute("INSERT INTO knowledge_fts (topic, title, body_text) VALUES (?, ?, ?);", (topic, topic.capitalize(), content))
        self.conn.commit()
        return {"file_path": file_path, "topic": topic, "status": "INDEXED"}

    def knowledge_index_batch(self, files_or_dir: Union[str, List[str]], doc_type: str = "context") -> Dict[str, Any]:
        """Atomically index multiple markdown files or an entire directory in a single transaction."""
        file_list = []
        if isinstance(files_or_dir, str):
            if os.path.isdir(files_or_dir):
                for f in sorted(os.listdir(files_or_dir)):
                    if f.endswith(".md"):
                        file_list.append(os.path.join(files_or_dir, f))
            elif "," in files_or_dir:
                file_list = [f.strip() for f in files_or_dir.split(",") if f.strip()]
            else:
                file_list = [files_or_dir]
        else:
            file_list = files_or_dir

        indexed = []
        for path in file_list:
            if not os.path.exists(path) or os.path.isdir(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            topic = os.path.splitext(os.path.basename(path))[0]
            self.conn.execute("""
                INSERT INTO project_knowledge (topic, content_json, version, last_updated_by)
                VALUES (?, ?, 1, 'batch_indexer')
                ON CONFLICT(topic) DO UPDATE SET
                    content_json = excluded.content_json,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP;
            """, (topic, json.dumps({"raw_markdown": content, "doc_type": doc_type})))
            self.conn.execute("DELETE FROM knowledge_fts WHERE topic = ?;", (topic,))
            self.conn.execute("INSERT INTO knowledge_fts (topic, title, body_text) VALUES (?, ?, ?);", (topic, topic.capitalize(), content))
            indexed.append({"path": path, "topic": topic})

        self.conn.commit()
        return {"indexed_count": len(indexed), "topics": [i["topic"] for i in indexed], "status": "BATCH_INDEXED"}

    def spec_add_requirements_batch(self, change_id: str, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert or update a batch of acceptance criteria in a single atomic transaction."""
        for r in requirements:
            self.conn.execute("""
                INSERT INTO spec_requirements (req_id, change_id, type, tag, title, given_when_then, status)
                VALUES (?, ?, ?, ?, ?, ?, 'SPECIFIED')
                ON CONFLICT(req_id) DO UPDATE SET
                    tag = excluded.tag,
                    title = excluded.title,
                    given_when_then = excluded.given_when_then;
            """, (
                r["req_id"],
                change_id,
                r.get("type", "AC"),
                r.get("tag", "CONFIRMED"),
                r.get("title", ""),
                r.get("gwt") or r.get("given_when_then")
            ))
        self.conn.commit()
        return {"change_id": change_id, "inserted_count": len(requirements), "status": "BATCH_COMPLETED"}

    def spec_add_edge_cases_batch(self, change_id: str, edge_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert a batch of edge cases in a single atomic transaction."""
        for e in edge_cases:
            cat = str(e.get("category", "boundary")).lower()
            self.conn.execute("""
                INSERT INTO spec_edge_cases (change_id, category, scenario, expected_behavior, mapped_ac_id)
                VALUES (?, ?, ?, ?, ?);
            """, (
                change_id,
                cat,
                e.get("scenario", ""),
                e.get("expected", e.get("expected_behavior", "Error or fallback")),
                e.get("mapped_ac") or e.get("mapped_ac_id")
            ))
        self.conn.commit()
        return {"change_id": change_id, "inserted_count": len(edge_cases), "status": "BATCH_COMPLETED"}

    def task_inspect_work_context(self, change_id: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Chunky composite query for Developer role.
        Consolidates active task details, mapped AC requirements, architecture ADRs,
        endpoints, and latest handoff into a single sub-millisecond query.
        """
        cursor = self.conn.cursor()

        # 1. Active or specified task
        if task_id:
            task = self.task_get_details(change_id, task_id)
        else:
            task = self.task_get_next_active(change_id)

        if not task:
            return {"change_id": change_id, "status": "NO_ACTIVE_TASKS", "task": None}

        # 2. Extract mapped ACs
        mapped_acs = task.get("mapped_acs")
        if not mapped_acs:
            raw_json = task.get("mapped_acs_json", "[]")
            try:
                mapped_acs = json.loads(raw_json) if isinstance(raw_json, str) else []
            except Exception:
                mapped_acs = []

        requirements = []
        if mapped_acs:
            placeholders = ",".join(["?"] * len(mapped_acs))
            cursor.execute(f"SELECT * FROM spec_requirements WHERE change_id = ? AND req_id IN ({placeholders});", [change_id] + mapped_acs)
            requirements = [dict(r) for r in cursor.fetchall()]

        # 3. Latest handoff context (reading order, risky areas)
        handoff = self.handoff_get_latest(change_id) or {}

        # 4. Relevant design artifacts
        adrs = self.design_list_adrs(change_id)
        endpoints = self.design_list_endpoints(change_id)
        schemas = self.design_list_schemas(change_id)

        return {
            "change_id": change_id,
            "task": task,
            "requirements": requirements,
            "handoff": {
                "reading_order": handoff.get("reading_order", []),
                "risky_areas": handoff.get("risky_areas", []),
                "contentious_points": handoff.get("contentious_points", [])
            },
            "architecture": {
                "adrs": adrs,
                "endpoints": endpoints,
                "schemas": schemas
            }
        }

    def qa_inspect_audit_context(self, change_id: str) -> Dict[str, Any]:
        """
        Chunky composite query for QA role.
        Consolidates change state, verification matrix, open bugs, and gate status
        into a single sub-millisecond query.
        """
        cursor = self.conn.cursor()

        # 1. Change state
        cursor.execute("SELECT * FROM change_state WHERE change_id = ?;", (change_id,))
        change_row = cursor.fetchone()
        change_info = dict(change_row) if change_row else {}

        # 2. Verification matrix
        matrix = self.qa_get_verification_matrix(change_id)

        # 3. Open bugs
        open_bugs = self.qa_list_bugs(change_id, status="OPEN")

        # 4. Risky areas from handoff
        risky_areas = self.handoff_get_risky_areas(change_id)

        # 5. QA Gate inspection
        from .state_machine import SDLCStateMachine
        sm = SDLCStateMachine(self.conn)
        gate_status = sm.gate_inspect(change_id, "QA")

        return {
            "change_id": change_id,
            "change": change_info,
            "gate_status": gate_status,
            "verification_matrix": matrix,
            "open_bugs": open_bugs,
            "risky_areas": risky_areas
        }

    def qa_create_scenarios_batch(self, change_id: str, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert a batch of test scenarios in a single atomic transaction."""
        for s in scenarios:
            self.conn.execute("""
                INSERT INTO qa_test_scenarios (scenario_id, change_id, mapped_ac_id, title, steps, expected_result, priority, execution_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'UNTESTED')
                ON CONFLICT(scenario_id) DO UPDATE SET
                    title = excluded.title,
                    steps = excluded.steps,
                    expected_result = excluded.expected_result,
                    priority = excluded.priority;
            """, (
                s["scenario_id"],
                change_id,
                s.get("mapped_ac") or s.get("mapped_ac_id", ""),
                s.get("title", ""),
                s.get("steps", ""),
                s.get("expected", s.get("expected_result", "")),
                s.get("priority", "P1")
            ))
        self.conn.commit()
        return {"change_id": change_id, "inserted_count": len(scenarios), "status": "BATCH_COMPLETED"}

    def qa_record_tests_batch(self, change_id: str, test_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update execution statuses for a batch of test scenarios in a single transaction."""
        for tr in test_runs:
            raw_st = str(tr.get("status", "PASSED")).upper()
            status = "PASSED" if raw_st in ("PASS", "PASSED") else ("FAILED" if raw_st in ("FAIL", "FAILED") else raw_st)
            self.conn.execute("""
                UPDATE qa_test_scenarios
                SET execution_status = ?
                WHERE change_id = ? AND scenario_id = ?;
            """, (status, change_id, tr.get("scenario_id") or tr.get("test_id")))
        self.conn.commit()
        return {"change_id": change_id, "updated_count": len(test_runs), "status": "BATCH_COMPLETED"}

