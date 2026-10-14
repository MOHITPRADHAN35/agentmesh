import logging
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from falkordb import FalkorDB
from app.config import settings

logger = logging.getLogger("agentmesh.graph_service")

# Fallback in-memory storage for message history & when FalkorDB is offline
_in_memory_messages: Dict[str, List[Dict[str, Any]]] = {}
_in_memory_conflicts: Dict[str, Dict[str, Any]] = {}

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
            node_count = res.result_set[0][0] if res.result_set else 0
            return {
                "status": "ok",
                "database": True,
                "mode": "live"
            }
        except Exception as e:
            logger.warning(f"FalkorDB check failed (falling back to demo mode): {e}")
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
                "CREATE INDEX FOR (t:Task) ON (t.id)",
                "CREATE INDEX FOR (c:Conflict) ON (c.id)"
            ]
            for query in index_queries:
                try:
                    g.query(query)
                except Exception as ex:
                    logger.debug(f"Index notice: {ex}")
        except Exception as e:
            logger.warning(f"Indices init note: {e}")

    # --- Session Operations ---

    def create_session(self, title: Optional[str] = None, session_id: Optional[str] = None, project_id: str = "default_project") -> Dict[str, Any]:
        sid = session_id or f"sess_{uuid.uuid4().hex[:6]}"
        stitle = title or f"Session {sid}"
        now = datetime.utcnow().isoformat()
        try:
            query = """
            MERGE (s:Session {id: $sid})
            ON CREATE SET s.title = $title, s.created_at = $created_at, s.project_id = $project_id
            RETURN s.id, s.title, s.created_at
            """
            res = self.get_graph().query(query, params={"sid": sid, "title": stitle, "created_at": now, "project_id": project_id})
            r = res.result_set[0]
            return {"id": r[0], "title": r[1], "created_at": str(r[2]), "message_count": len(_in_memory_messages.get(sid, []))}
        except Exception as e:
            logger.warning(f"FalkorDB session fallback: {e}")
            return {"id": sid, "title": stitle, "created_at": now, "message_count": len(_in_memory_messages.get(sid, []))}

    def list_sessions(self, project_id: str = "default_project") -> List[Dict[str, Any]]:
        sessions = []
        try:
            query = """
            MATCH (s:Session)
            OPTIONAL MATCH (s)-[:CONTAINS]->(m:Memory)
            RETURN s.id, s.title, s.created_at, count(m) AS mem_count
            ORDER BY s.created_at DESC
            """
            res = self.get_graph().query(query)
            for r in res.result_set:
                sid = r[0]
                sessions.append({
                    "id": sid,
                    "title": r[1] or f"Session {sid}",
                    "created_at": str(r[2]) if r[2] else datetime.utcnow().isoformat(),
                    "message_count": len(_in_memory_messages.get(sid, []))
                })
        except Exception as e:
            logger.warning(f"FalkorDB list_sessions fallback: {e}")

        if not sessions:
            # Provide default initial session
            default_id = "default"
            sessions.append({
                "id": default_id,
                "title": "Main Project Session",
                "created_at": datetime.utcnow().isoformat(),
                "message_count": len(_in_memory_messages.get(default_id, []))
            })
        return sessions

    # --- Message History Operations ---

    def save_message(self, session_id: str, message: Dict[str, Any]):
        if session_id not in _in_memory_messages:
            _in_memory_messages[session_id] = []
        _in_memory_messages[session_id].append(message)

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        return _in_memory_messages.get(session_id, [])

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
                "id": r[0],
                "text": r[1],
                "type": r[2],
                "source": r[3],
                "session_id": r[4],
                "agent": r[5],
                "created_at": str(r[6]),
                "confidence": float(r[7])
            }
        except Exception as e:
            logger.warning(f"FalkorDB create_memory fallback: {e}")
            return {
                "id": mid,
                "text": text,
                "type": memory_type,
                "source": source,
                "session_id": session_id,
                "agent": agent_name,
                "created_at": now,
                "confidence": confidence
            }

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
                    "id": r[0],
                    "text": r[1],
                    "type": r[2],
                    "source": r[3],
                    "session_id": r[4],
                    "agent": r[5],
                    "created_at": str(r[6]),
                    "confidence": float(r[7]) if r[7] else 1.0
                })
            return memories
        except Exception as e:
            logger.warning(f"FalkorDB search_memories fallback: {e}")
            return []

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
            logger.warning(f"FalkorDB create_conflict link fallback: {e}")

        return conflict_obj

    def list_conflicts(self) -> List[Dict[str, Any]]:
        # Read from FalkorDB first if possible
        try:
            q = """
            MATCH (c:Conflict)
            OPTIONAL MATCH (c)-[:INVOLVES]->(m:Memory)
            RETURN c.id, c.reason, c.status, collect(m.id) AS mem_ids
            """
            res = self.get_graph().query(q)
            results = []
            for r in res.result_set:
                cid = r[0]
                if cid in _in_memory_conflicts:
                    results.append(_in_memory_conflicts[cid])
                else:
                    results.append({
                        "id": cid,
                        "reason": r[1],
                        "status": r[2],
                        "a": {"id": "m1", "text": "Historical decision", "type": "fact", "source": "history", "session_id": "prev", "created_at": datetime.utcnow().isoformat(), "confidence": 1.0},
                        "b": {"id": "m2", "text": "Conflicting decision", "type": "fact", "source": "current", "session_id": "curr", "created_at": datetime.utcnow().isoformat(), "confidence": 0.9}
                    })
            if results:
                return results
        except Exception:
            pass
        return list(_in_memory_conflicts.values())

    def resolve_conflict(self, conflict_id: str, resolution: str, note: Optional[str] = None) -> Dict[str, Any]:
        if conflict_id in _in_memory_conflicts:
            _in_memory_conflicts[conflict_id]["status"] = "resolved"
            conf = _in_memory_conflicts[conflict_id]
        else:
            conf = {
                "id": conflict_id,
                "reason": "Resolved contradiction",
                "status": "resolved",
                "a": {"id": "m1", "text": "Resolved A", "type": "fact", "source": "user", "session_id": "prev", "created_at": datetime.utcnow().isoformat(), "confidence": 1.0},
                "b": {"id": "m2", "text": "Resolved B", "type": "fact", "source": "user", "session_id": "curr", "created_at": datetime.utcnow().isoformat(), "confidence": 1.0}
            }

        try:
            q = """
            MATCH (c:Conflict {id: $cid})
            SET c.status = 'resolved', c.resolution = $res, c.note = $note
            """
            self.get_graph().query(q, params={"cid": conflict_id, "res": resolution, "note": note or ""})
        except Exception:
            pass

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
            mq = "MATCH (m:Memory) RETURN m.id, m.text, m.type, m.session_id, m.agent"
            for r in g.query(mq).result_set:
                mid = str(r[0])
                if mid not in node_ids:
                    node_ids.add(mid)
                    nodes.append({"id": mid, "type": "Memory", "label": r[1], "data": {"type": r[2], "agent": r[4]}})
                    # Session -> Memory
                    if r[3]:
                        edges.append({"id": f"e_s_{mid}", "source": str(r[3]), "target": mid, "label": "CONTAINS"})
                    # Agent -> Memory
                    if r[4]:
                        edges.append({"id": f"e_a_{mid}", "source": f"agent_{str(r[4]).lower()}", "target": mid, "label": "CREATED"})

            # 4. Conflicts
            for c in list(_in_memory_conflicts.values()):
                cid = c["id"]
                if cid not in node_ids:
                    node_ids.add(cid)
                    nodes.append({"id": cid, "type": "Conflict", "label": c["reason"], "data": {"status": c["status"]}})
                    edges.append({"id": f"e_{cid}_a", "source": cid, "target": c["a"]["id"], "label": "INVOLVES"})
                    edges.append({"id": f"e_{cid}_b", "source": cid, "target": c["b"]["id"], "label": "INVOLVES"})
                    edges.append({"id": f"e_contra_{cid}", "source": c["a"]["id"], "target": c["b"]["id"], "label": "CONTRADICTS"})

            # 5. Edges from FalkorDB
            eq = "MATCH (a)-[r]->(b) RETURN a.id, b.id, type(r)"
            for r in g.query(eq).result_set:
                src, tgt, lbl = str(r[0]), str(r[1]), str(r[2])
                if src in node_ids and tgt in node_ids:
                    edges.append({"id": f"e_{src}_{tgt}_{lbl}", "source": src, "target": tgt, "label": lbl})

        except Exception as e:
            logger.warning(f"FalkorDB get_full_graph fallback: {e}")

        # Ensure at least agents exist so GraphExplorer isn't empty
        if not nodes:
            for a in ["Researcher", "Planner", "Reviewer"]:
                nodes.append({"id": f"agent_{a.lower()}", "type": "Agent", "label": a, "data": {}})

        return {"nodes": nodes, "edges": edges}

graph_service = GraphService()
