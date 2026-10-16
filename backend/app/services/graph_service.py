import logging
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from falkordb import FalkorDB
from app.config import settings

logger = logging.getLogger("agentmesh.graph_service")

# In-memory cache for fast lookups & offline fallback
_in_memory_messages: Dict[str, List[Dict[str, Any]]] = {}
_in_memory_conflicts: Dict[str, Dict[str, Any]] = {}
_in_memory_memories: Dict[str, Dict[str, Any]] = {}
_in_memory_sessions: Dict[str, Dict[str, Any]] = {}

class GraphService:
    def __init__(self):
        self.host = settings.FALKORDB_HOST
        self.port = settings.FALKORDB_PORT
        self.password = settings.FALKORDB_PASSWORD or None
        self.graph_name = settings.FALKORDB_GRAPH
        self._client: Optional[FalkorDB] = None
        self._graph = None

    def get_graph(self):
        if self._graph is None:
            self._client = FalkorDB(
                host=self.host,
                port=self.port,
                password=self.password
            )
            self._graph = self._client.select_graph(self.graph_name)
        return self._graph

    def check_health(self) -> Dict[str, Any]:
        try:
            g = self.get_graph()
            res = g.query("MATCH (n) RETURN count(n) AS node_count")
            return {
                "status": "ok",
                "database": True,
                "mode": "live"
            }
        except Exception as e:
            return {
                "status": "ok",
                "database": False,
                "mode": "demo"
            }

    def init_indices(self):
        """Create indices in FalkorDB safely."""
        try:
            g = self.get_graph()
            index_queries = [
                "CREATE INDEX FOR (m:Memory) ON (m.id)",
                "CREATE INDEX FOR (s:Session) ON (s.id)",
                "CREATE INDEX FOR (a:Agent) ON (a.name)",
                "CREATE INDEX FOR (c:Conflict) ON (c.id)"
            ]
            for q in index_queries:
                try:
                    g.query(q)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Indices init note: {e}")

    # --- Session Operations ---

    def create_session(self, title: Optional[str] = None, session_id: Optional[str] = None, project_id: str = "default_project") -> Dict[str, Any]:
        sid = session_id or f"sess_{uuid.uuid4().hex[:6]}"
        now = datetime.utcnow().isoformat()
        
        if not title:
            existing = self.list_sessions(project_id)
            count = len(existing) + 1
            stitle = f"Session {count}"
        else:
            stitle = title

        session_obj = {"id": sid, "title": stitle, "created_at": now, "project_id": project_id, "message_count": len(_in_memory_messages.get(sid, []))}
        _in_memory_sessions[sid] = session_obj

        try:
            query = """
            MERGE (s:Session {id: $sid})
            ON CREATE SET s.title = $title, s.created_at = $created_at, s.project_id = $project_id
            RETURN s.id, s.title, s.created_at
            """
            res = self.get_graph().query(query, params={"sid": sid, "title": stitle, "created_at": now, "project_id": project_id})
            r = res.result_set[0]
            return {"id": str(r[0]), "title": str(r[1]), "created_at": str(r[2]), "message_count": len(_in_memory_messages.get(sid, []))}
        except Exception as e:
            logger.error(f"Error creating session in FalkorDB: {e}")
            return session_obj

    def update_session_title(self, session_id: str, new_title: str) -> Dict[str, Any]:
        stitle = new_title.strip() or "Untitled Session"
        now = datetime.utcnow().isoformat()
        if session_id in _in_memory_sessions:
            _in_memory_sessions[session_id]["title"] = stitle

        try:
            query = """
            MATCH (s:Session {id: $sid})
            SET s.title = $title
            RETURN s.id, s.title, s.created_at
            """
            res = self.get_graph().query(query, params={"sid": session_id, "title": stitle})
            if res.result_set:
                r = res.result_set[0]
                return {
                    "id": str(r[0]),
                    "title": str(r[1]),
                    "created_at": str(r[2]),
                    "message_count": len(_in_memory_messages.get(session_id, []))
                }
        except Exception as e:
            logger.warning(f"Failed to update session title in FalkorDB: {e}")

        return _in_memory_sessions.get(session_id, {
            "id": session_id,
            "title": stitle,
            "created_at": now,
            "message_count": len(_in_memory_messages.get(session_id, []))
        })

    def list_sessions(self, project_id: str = "default_project") -> List[Dict[str, Any]]:
        sessions = []
        try:
            query = """
            MATCH (s:Session)
            OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(msg:Message)
            OPTIONAL MATCH (s)-[:CONTAINS]->(mem:Memory)
            RETURN s.id, s.title, s.created_at, count(msg) AS msg_count, count(mem) AS mem_count
            ORDER BY s.created_at DESC
            """
            res = self.get_graph().query(query)
            for r in res.result_set:
                sid = str(r[0])
                msg_count = int(r[3]) if len(r) > 3 and r[3] is not None else 0
                cached_msgs = len(_in_memory_messages.get(sid, []))
                total_msgs = max(msg_count, cached_msgs)
                sessions.append({
                    "id": sid,
                    "title": str(r[1]) if r[1] else f"Session {sid}",
                    "created_at": str(r[2]),
                    "message_count": total_msgs
                })
        except Exception as e:
            logger.warning(f"Error listing sessions from FalkorDB: {e}")

        # Merge any in-memory sessions that haven't shown up in FalkorDB yet
        seen_sids = {s["id"] for s in sessions}
        for sid, sess in _in_memory_sessions.items():
            if sid not in seen_sids:
                sessions.append(sess)

        if not sessions:
            default_id = "default"
            default_sess = {
                "id": default_id,
                "title": "Main Project Session",
                "created_at": datetime.utcnow().isoformat(),
                "message_count": len(_in_memory_messages.get(default_id, []))
            }
            _in_memory_sessions[default_id] = default_sess
            sessions.append(default_sess)

        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Completely delete session, messages, memories, and any residue from FalkorDB & memory."""
        # 1. Clean in-memory cache
        _in_memory_sessions.pop(session_id, None)
        _in_memory_messages.pop(session_id, None)

        deleted_mem_ids = {
            mid for mid, m in _in_memory_memories.items()
            if m.get("session_id") == session_id
        }
        for mid in deleted_mem_ids:
            _in_memory_memories.pop(mid, None)

        deleted_conf_ids = {
            cid for cid, c in _in_memory_conflicts.items()
            if c.get("a", {}).get("id") in deleted_mem_ids or c.get("b", {}).get("id") in deleted_mem_ids
        }
        for cid in deleted_conf_ids:
            _in_memory_conflicts.pop(cid, None)

        # 2. Clean FalkorDB graph
        try:
            g = self.get_graph()
            # Delete conflicts involving memories from this session
            q_conflicts = """
            MATCH (m:Memory)
            WHERE m.session_id = $sid
            OPTIONAL MATCH (c:Conflict)-[:INVOLVES]->(m)
            DETACH DELETE c
            """
            g.query(q_conflicts, params={"sid": session_id})

            # Delete memories belonging to this session
            q_memories = """
            MATCH (m:Memory)
            WHERE m.session_id = $sid
            DETACH DELETE m
            """
            g.query(q_memories, params={"sid": session_id})

            # Delete session and its messages
            q_session = """
            MATCH (s:Session {id: $sid})
            OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(msg:Message)
            OPTIONAL MATCH (s)-[:CONTAINS]->(rem_mem:Memory)
            DETACH DELETE s, msg, rem_mem
            """
            g.query(q_session, params={"sid": session_id})
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id} from FalkorDB: {e}")
            return False

    # --- Message History Operations ---

    def save_message(self, session_id: str, message: Dict[str, Any]):
        if session_id not in _in_memory_messages:
            _in_memory_messages[session_id] = []
        _in_memory_messages[session_id].append(message)

        try:
            mid = message.get("id") or f"msg_{uuid.uuid4().hex[:6]}"
            role = message.get("role", "user")
            content = message.get("content", "")
            created_at = message.get("created_at") or datetime.utcnow().isoformat()
            raw_json = json.dumps(message)
            query = """
            MERGE (m:Message {id: $mid})
            ON CREATE SET m.role = $role, m.content = $content, m.created_at = $created_at, m.data = $data
            WITH m
            MATCH (s:Session {id: $sid})
            MERGE (s)-[:HAS_MESSAGE]->(m)
            """
            self.get_graph().query(query, params={"mid": mid, "role": role, "content": content, "created_at": created_at, "data": raw_json, "sid": session_id})
        except Exception as e:
            logger.warning(f"Error saving message to FalkorDB: {e}")

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        mem_msgs = _in_memory_messages.get(session_id, [])
        if mem_msgs:
            return mem_msgs
        try:
            query = """
            MATCH (s:Session {id: $sid})-[:HAS_MESSAGE]->(m:Message)
            RETURN m.data, m.created_at
            ORDER BY m.created_at ASC
            """
            res = self.get_graph().query(query, params={"sid": session_id})
            msgs = []
            for r in res.result_set:
                if r[0]:
                    try:
                        msgs.append(json.loads(r[0]))
                    except Exception:
                        pass
            if msgs:
                _in_memory_messages[session_id] = msgs
                return msgs
        except Exception as e:
            logger.warning(f"Error loading messages from FalkorDB: {e}")
        return mem_msgs

    # --- Memory Operations ---

    def create_memory(
        self,
        text: str,
        memory_type: str,
        confidence: float,
        source: str,
        project_id: str,
        agent_name: str,
        session_id: str,
        memory_id: Optional[str] = None
    ) -> Dict[str, Any]:
        mid = memory_id or f"mem_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        mem_obj = {
            "id": mid,
            "text": text,
            "type": memory_type,
            "source": source,
            "session_id": session_id,
            "agent": agent_name,
            "created_at": now,
            "confidence": confidence
        }
        _in_memory_memories[mid] = mem_obj

        try:
            self.create_session(session_id=session_id, project_id=project_id)
            query = """
            MERGE (m:Memory {id: $id})
            ON CREATE SET 
                m.text = $text,
                m.type = $mtype,
                m.confidence = $confidence,
                m.source = $source,
                m.project_id = $project_id,
                m.created_at = $created_at,
                m.agent = $agent,
                m.session_id = $session_id
            WITH m
            MATCH (s:Session {id: $session_id})
            MERGE (s)-[:CONTAINS]->(m)
            RETURN m.id, m.text, m.type, m.source, m.session_id, m.agent, m.created_at, m.confidence
            """
            params = {
                "id": mid,
                "text": text,
                "mtype": memory_type,
                "confidence": confidence,
                "source": source,
                "project_id": project_id,
                "created_at": now,
                "agent": agent_name,
                "session_id": session_id
            }
            res = self.get_graph().query(query, params=params)
            r = res.result_set[0]
            return {
                "id": str(r[0]),
                "text": str(r[1]),
                "type": str(r[2]),
                "source": str(r[3]),
                "session_id": str(r[4]),
                "agent": str(r[5]),
                "created_at": str(r[6]),
                "confidence": float(r[7]) if r[7] else 1.0
            }
        except Exception as e:
            logger.error(f"Error creating memory in FalkorDB: {e}")
            return mem_obj

    def search_memories(self, query_str: Optional[str] = None, project_id: str = "default_project") -> List[Dict[str, Any]]:
        try:
            if query_str:
                query = """
                MATCH (m:Memory)
                WHERE toLower(m.text) CONTAINS toLower($q)
                RETURN m.id, m.text, m.type, m.source, m.session_id, m.agent, m.created_at, m.confidence
                LIMIT 30
                """
                res = self.get_graph().query(query, params={"q": query_str})
            else:
                query = """
                MATCH (m:Memory)
                RETURN m.id, m.text, m.type, m.source, m.session_id, m.agent, m.created_at, m.confidence
                ORDER BY m.created_at DESC
                LIMIT 30
                """
                res = self.get_graph().query(query)

            memories = []
            for r in res.result_set:
                memories.append({
                    "id": str(r[0]),
                    "text": str(r[1]),
                    "type": str(r[2]),
                    "source": str(r[3]),
                    "session_id": str(r[4]),
                    "agent": str(r[5]),
                    "created_at": str(r[6]),
                    "confidence": float(r[7]) if r[7] else 1.0
                })
            return memories
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            mems = list(_in_memory_memories.values())
            if query_str:
                q_lower = query_str.lower()
                mems = [m for m in mems if q_lower in m.get("text", "").lower()]
            return mems

    # --- Conflict Operations ---

    def create_conflict(self, reason: str, memory_a: Dict[str, Any], memory_b: Dict[str, Any]) -> Dict[str, Any]:
        cid = f"conf_{uuid.uuid4().hex[:6]}"
        now = datetime.utcnow().isoformat()
        conflict_obj = {
            "id": cid,
            "reason": reason,
            "status": "open",
            "a": memory_a,
            "b": memory_b
        }
        _in_memory_conflicts[cid] = conflict_obj

        try:
            g = self.get_graph()
            q = """
            CREATE (c:Conflict {id: $cid, reason: $reason, status: 'open', created_at: $created_at})
            WITH c
            MATCH (ma:Memory {id: $aid}), (mb:Memory {id: $bid})
            MERGE (c)-[:INVOLVES]->(ma)
            MERGE (c)-[:INVOLVES]->(mb)
            MERGE (ma)-[:CONTRADICTS]->(mb)
            MERGE (mb)-[:CONTRADICTS]->(ma)
            """
            g.query(q, params={"cid": cid, "reason": reason, "created_at": now, "aid": memory_a["id"], "bid": memory_b["id"]})
        except Exception as e:
            logger.error(f"Error creating conflict in FalkorDB: {e}")

        return conflict_obj

    def list_conflicts(self) -> List[Dict[str, Any]]:
        try:
            q = """
            MATCH (c:Conflict)
            OPTIONAL MATCH (c)-[:INVOLVES]->(m:Memory)
            RETURN c.id, c.reason, c.status, collect(m.id) AS mem_ids
            """
            res = self.get_graph().query(q)
            results = []
            for r in res.result_set:
                cid = str(r[0])
                if cid in _in_memory_conflicts:
                    results.append(_in_memory_conflicts[cid])
                else:
                    results.append({
                        "id": cid,
                        "reason": str(r[1]),
                        "status": str(r[2]),
                        "a": {"id": "m1", "text": "Historical decision", "type": "fact", "source": "history", "session_id": "prev", "created_at": datetime.utcnow().isoformat(), "confidence": 1.0},
                        "b": {"id": "m2", "text": "Conflicting decision", "type": "fact", "source": "current", "session_id": "curr", "created_at": datetime.utcnow().isoformat(), "confidence": 0.9}
                    })
            if results:
                return results
        except Exception as e:
            logger.warning(f"Error listing conflicts: {e}")
        return list(_in_memory_conflicts.values())

    def resolve_conflict(self, conflict_id: str, resolution: str, note: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        conf = _in_memory_conflicts.get(conflict_id, {
            "id": conflict_id,
            "reason": "Architectural contradiction",
            "status": "resolved",
            "resolution": resolution,
            "note": note or "",
            "resolved_at": now
        })
        conf["status"] = "resolved"
        conf["resolution"] = resolution
        conf["note"] = note or ""
        conf["resolved_at"] = now
        _in_memory_conflicts[conflict_id] = conf

        try:
            g = self.get_graph()
            # 1. Update conflict node
            q = """
            MATCH (c:Conflict {id: $cid})
            SET c.status = 'resolved', c.resolution = $res, c.note = $note, c.resolved_at = $now
            RETURN c.id, c.status
            """
            g.query(q, params={"cid": conflict_id, "res": resolution, "note": note or "", "now": now})

            # 2. Get memories involved
            q_mems = """
            MATCH (c:Conflict {id: $cid})-[:INVOLVES]->(m:Memory)
            RETURN m.id
            """
            involved = [str(r[0]) for r in g.query(q_mems, params={"cid": conflict_id}).result_set]

            mem_a_id = conf.get("a", {}).get("id")
            mem_b_id = conf.get("b", {}).get("id")
            if not involved and mem_a_id and mem_b_id:
                involved = [mem_a_id, mem_b_id]

            if len(involved) >= 2:
                id_a = involved[0]
                id_b = involved[1]

                # 3. Delete CONTRADICTS edges between them
                q_del = """
                MATCH (ma:Memory {id: $ida})-[r:CONTRADICTS]-(mb:Memory {id: $idb})
                DELETE r
                """
                g.query(q_del, params={"ida": id_a, "idb": id_b})

                # 4. Create SUPERSEDES relationship
                if resolution == "accept_b":
                    q_sup = """
                    MATCH (ma:Memory {id: $ida}), (mb:Memory {id: $idb})
                    MERGE (mb)-[:SUPERSEDES]->(ma)
                    SET ma.status = 'superseded'
                    """
                    g.query(q_sup, params={"ida": id_a, "idb": id_b})
                elif resolution == "accept_a":
                    q_sup = """
                    MATCH (ma:Memory {id: $ida}), (mb:Memory {id: $idb})
                    MERGE (ma)-[:SUPERSEDES]->(mb)
                    SET mb.status = 'superseded'
                    """
                    g.query(q_sup, params={"ida": id_a, "idb": id_b})
        except Exception as e:
            logger.error(f"Error resolving conflict in FalkorDB: {e}")

        return conf

    # --- Graph Serialization for ReactFlow / GraphExplorer ---

    def get_full_graph(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_ids = set()

        try:
            g = self.get_graph()

            # 1. Sessions
            sq = "MATCH (s:Session) RETURN s.id, s.title"
            for r in g.query(sq).result_set:
                sid = str(r[0])
                if session_id and sid != session_id:
                    continue
                if sid not in node_ids:
                    node_ids.add(sid)
                    nodes.append({"id": sid, "type": "Session", "label": r[1] or f"Session {sid}", "data": {}})

            # 2. Agents
            for agent in ["Researcher", "Planner", "Reviewer"]:
                aid = f"agent_{agent.lower()}"
                if aid not in node_ids:
                    node_ids.add(aid)
                    nodes.append({"id": aid, "type": "Agent", "label": agent, "data": {}})

            # 3. Memories
            if session_id:
                mq = "MATCH (m:Memory) WHERE m.session_id = $sid RETURN m.id, m.text, m.type, m.session_id, m.agent"
                m_res = g.query(mq, params={"sid": session_id}).result_set
            else:
                mq = "MATCH (m:Memory) RETURN m.id, m.text, m.type, m.session_id, m.agent"
                m_res = g.query(mq).result_set

            for r in m_res:
                mid = str(r[0])
                if mid not in node_ids:
                    node_ids.add(mid)
                    nodes.append({"id": mid, "type": "Memory", "label": r[1], "data": {"type": r[2], "agent": r[4]}})
                    if r[3] and str(r[3]) in node_ids:
                        edges.append({"id": f"e_s_{mid}", "source": str(r[3]), "target": mid, "label": "CONTAINS"})
                    if r[4]:
                        edges.append({"id": f"e_a_{mid}", "source": f"agent_{str(r[4]).lower()}", "target": mid, "label": "CREATED"})

            # 4. Conflicts
            for c in list(_in_memory_conflicts.values()):
                cid = c["id"]
                if cid not in node_ids:
                    node_ids.add(cid)
                    nodes.append({"id": cid, "type": "Conflict", "label": c["reason"], "data": {"status": c["status"]}})
                    if "a" in c and "id" in c["a"] and c["a"]["id"] in node_ids:
                        edges.append({"id": f"e_{cid}_a", "source": cid, "target": c["a"]["id"], "label": "INVOLVES"})
                    if "b" in c and "id" in c["b"] and c["b"]["id"] in node_ids:
                        edges.append({"id": f"e_{cid}_b", "source": cid, "target": c["b"]["id"], "label": "INVOLVES"})
                    if c.get("status") == "open" and "a" in c and "b" in c and "id" in c["a"] and "id" in c["b"] and c["a"]["id"] in node_ids and c["b"]["id"] in node_ids:
                        edges.append({"id": f"e_contra_{cid}", "source": c["a"]["id"], "target": c["b"]["id"], "label": "CONTRADICTS"})

            # 5. Graph Relationships directly from FalkorDB
            eq = "MATCH (a)-[r]->(b) RETURN a.id, b.id, type(r)"
            for r in g.query(eq).result_set:
                src, tgt, lbl = str(r[0]), str(r[1]), str(r[2])
                if src in node_ids and tgt in node_ids:
                    edges.append({"id": f"e_{src}_{tgt}_{lbl}", "source": src, "target": tgt, "label": lbl})

        except Exception as e:
            logger.error(f"Error fetching graph: {e}")
            for sid, sess in _in_memory_sessions.items():
                if session_id and sid != session_id:
                    continue
                if sid not in node_ids:
                    node_ids.add(sid)
                    nodes.append({"id": sid, "type": "Session", "label": sess.get("title", f"Session {sid}"), "data": {}})

            for agent in ["Researcher", "Planner", "Reviewer"]:
                aid = f"agent_{agent.lower()}"
                if aid not in node_ids:
                    node_ids.add(aid)
                    nodes.append({"id": aid, "type": "Agent", "label": agent, "data": {}})

            for mid, m in _in_memory_memories.items():
                if session_id and m.get("session_id") != session_id:
                    continue
                if mid not in node_ids:
                    node_ids.add(mid)
                    nodes.append({"id": mid, "type": "Memory", "label": m["text"], "data": {"type": m.get("type", "fact"), "agent": m.get("agent", "Researcher")}})
                    if m.get("session_id") and m.get("session_id") in node_ids:
                        edges.append({"id": f"e_s_{mid}", "source": m["session_id"], "target": mid, "label": "CONTAINS"})
                    if m.get("agent"):
                        edges.append({"id": f"e_a_{mid}", "source": f"agent_{m['agent'].lower()}", "target": mid, "label": "CREATED"})

        if not nodes:
            for a in ["Researcher", "Planner", "Reviewer"]:
                nodes.append({"id": f"agent_{a.lower()}", "type": "Agent", "label": a, "data": {}})

        return {"nodes": nodes, "edges": edges}

graph_service = GraphService()
