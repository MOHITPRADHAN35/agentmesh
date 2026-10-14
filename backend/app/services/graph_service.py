import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from falkordb import FalkorDB
from app.config import settings

logger = logging.getLogger("agentmesh.graph_service")

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
            # Simple query to test connectivity
            res = g.query("MATCH (n) RETURN count(n) AS node_count")
            node_count = res.result_set[0][0] if res.result_set else 0

            res_e = g.query("MATCH ()-[r]->() RETURN count(r) AS edge_count")
            edge_count = res_e.result_set[0][0] if res_e.result_set else 0

            return {
                "status": "healthy",
                "database_connected": True,
                "graph_name": self.graph_name,
                "node_count": node_count,
                "edge_count": edge_count,
                "error": None
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "database_connected": False,
                "graph_name": self.graph_name,
                "node_count": 0,
                "edge_count": 0,
                "error": str(e)
            }

    def init_indices(self):
        """Create indices for performant node lookups."""
        try:
            g = self.get_graph()
            # FalkorDB index syntax
            index_queries = [
                "CREATE INDEX FOR (m:Memory) ON (m.id)",
                "CREATE INDEX FOR (m:Memory) ON (m.project_id)",
                "CREATE INDEX FOR (s:Session) ON (s.session_id)",
                "CREATE INDEX FOR (a:Agent) ON (a.name)",
                "CREATE INDEX FOR (t:Task) ON (t.id)",
                "CREATE INDEX FOR (c:Conflict) ON (c.id)"
            ]
            for query in index_queries:
                try:
                    g.query(query)
                except Exception as ex:
                    # Index might already exist, which is fine
                    logger.debug(f"Index query '{query}' notice: {ex}")
        except Exception as e:
            logger.warning(f"Could not initialize indices: {e}")

    # --- Session Operations ---

    def create_session(self, session_id: Optional[str] = None, project_id: str = "default_project") -> Dict[str, Any]:
        sid = session_id or str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()
        query = """
        MERGE (s:Session {session_id: $session_id, project_id: $project_id})
        ON CREATE SET s.created_at = $created_at
        RETURN s.session_id AS session_id, s.created_at AS created_at, s.project_id AS project_id
        """
        res = self.get_graph().query(query, params={"session_id": sid, "project_id": project_id, "created_at": now})
        record = res.result_set[0]
        return {
            "session_id": record[0],
            "created_at": record[1],
            "project_id": record[2],
            "memory_count": 0
        }

    def list_sessions(self, project_id: str) -> List[Dict[str, Any]]:
        query = """
        MATCH (s:Session {project_id: $project_id})
        OPTIONAL MATCH (s)-[:CONTAINS]->(m:Memory)
        RETURN s.session_id AS session_id, s.created_at AS created_at, s.project_id AS project_id, count(m) AS memory_count
        ORDER BY s.created_at DESC
        """
        res = self.get_graph().query(query, params={"project_id": project_id})
        sessions = []
        for r in res.result_set:
            sessions.append({
                "session_id": r[0],
                "created_at": str(r[1]) if r[1] else "",
                "project_id": r[2],
                "memory_count": r[3]
            })
        return sessions

    # --- Agent Operations ---

    def ensure_agent(self, name: str, role: str):
        query = """
        MERGE (a:Agent {name: $name})
        ON CREATE SET a.role = $role
        RETURN a.name
        """
        self.get_graph().query(query, params={"name": name, "role": role})

    # --- Memory Operations ---

    def create_memory(
        self,
        content: str,
        memory_type: str,
        confidence: float,
        source: str,
        project_id: str,
        agent_name: str,
        session_id: str,
        memory_id: Optional[str] = None
    ) -> Dict[str, Any]:
        mid = memory_id or f"mem_{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()

        # Ensure Agent and Session exist
        self.ensure_agent(agent_name, "orchestrator_subagent")
        self.create_session(session_id, project_id)

        query = """
        MERGE (m:Memory {id: $id})
        ON CREATE SET 
            m.content = $content,
            m.memory_type = $memory_type,
            m.confidence = $confidence,
            m.source = $source,
            m.project_id = $project_id,
            m.timestamp = $timestamp
        WITH m
        MATCH (s:Session {session_id: $session_id, project_id: $project_id})
        MERGE (s)-[:CONTAINS]->(m)
        WITH m
        MATCH (a:Agent {name: $agent_name})
        MERGE (a)-[:CREATED]->(m)
        RETURN m.id, m.content, m.memory_type, m.confidence, m.source, m.project_id, m.timestamp
        """
        params = {
            "id": mid,
            "content": content,
            "memory_type": memory_type,
            "confidence": confidence,
            "source": source,
            "project_id": project_id,
            "timestamp": now,
            "session_id": session_id,
            "agent_name": agent_name
        }
        res = self.get_graph().query(query, params=params)
        r = res.result_set[0]
        return {
            "id": r[0],
            "content": r[1],
            "memory_type": r[2],
            "confidence": float(r[3]),
            "source": r[4],
            "project_id": r[5],
            "timestamp": str(r[6]),
            "created_by_agent": agent_name,
            "session_id": session_id
        }

    def link_memories(self, source_id: str, target_id: str, relation_type: str, properties: Optional[Dict[str, Any]] = None):
        """Link two memories with RELATES_TO, SUPPORTS, or CONTRADICTS."""
        rel = relation_type.upper()
        if rel not in ["RELATES_TO", "SUPPORTS", "CONTRADICTS"]:
            rel = "RELATES_TO"

        query = f"""
        MATCH (m1:Memory {id: $source_id}), (m2:Memory {id: $target_id})
        MERGE (m1)-[r:{rel}]->(m2)
        RETURN type(r)
        """
        self.get_graph().query(query, params={"source_id": source_id, "target_id": target_id})

    def search_memories(self, project_id: str, query_str: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if query_str:
            query = """
            MATCH (m:Memory {project_id: $project_id})
            WHERE toLower(m.content) CONTAINS toLower($q)
            OPTIONAL MATCH (s:Session)-[:CONTAINS]->(m)
            OPTIONAL MATCH (a:Agent)-[:CREATED]->(m)
            RETURN m.id, m.content, m.memory_type, m.confidence, m.source, m.project_id, m.timestamp, a.name, s.session_id
            LIMIT $limit
            """
            params = {"project_id": project_id, "q": query_str, "limit": limit}
        else:
            query = """
            MATCH (m:Memory {project_id: $project_id})
            OPTIONAL MATCH (s:Session)-[:CONTAINS]->(m)
            OPTIONAL MATCH (a:Agent)-[:CREATED]->(m)
            RETURN m.id, m.content, m.memory_type, m.confidence, m.source, m.project_id, m.timestamp, a.name, s.session_id
            ORDER BY m.timestamp DESC
            LIMIT $limit
            """
            params = {"project_id": project_id, "limit": limit}

        res = self.get_graph().query(query, params=params)
        memories = []
        for r in res.result_set:
            memories.append({
                "id": r[0],
                "content": r[1],
                "memory_type": r[2],
                "confidence": float(r[3]),
                "source": r[4],
                "project_id": r[5],
                "timestamp": str(r[6]),
                "created_by_agent": r[7],
                "session_id": r[8]
            })
        return memories

    def get_related_memories(self, project_id: str, memory_ids: List[str]) -> List[Dict[str, Any]]:
        """Traverse 1..2 hops to find related context and historical decisions."""
        if not memory_ids:
            return []

        query = """
        MATCH (m:Memory {project_id: $project_id})
        WHERE m.id IN $mids
        MATCH (m)-[r:RELATES_TO|SUPPORTS|CONTRADICTS*1..2]-(related:Memory {project_id: $project_id})
        WHERE NOT related.id IN $mids
        OPTIONAL MATCH (s:Session)-[:CONTAINS]->(related)
        OPTIONAL MATCH (a:Agent)-[:CREATED]->(related)
        RETURN DISTINCT related.id, related.content, related.memory_type, related.confidence, 
                        related.source, related.project_id, related.timestamp, a.name, s.session_id
        LIMIT 15
        """
        res = self.get_graph().query(query, params={"project_id": project_id, "mids": memory_ids})
        results = []
        for r in res.result_set:
            results.append({
                "id": r[0],
                "content": r[1],
                "memory_type": r[2],
                "confidence": float(r[3]),
                "source": r[4],
                "project_id": r[5],
                "timestamp": str(r[6]),
                "created_by_agent": r[7],
                "session_id": r[8]
            })
        return results

    # --- Conflict Operations ---

    def create_conflict(self, explanation: str, project_id: str, memory_ids: List[str]) -> Dict[str, Any]:
        cid = f"conf_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        query = """
        CREATE (c:Conflict {
            id: $id,
            status: 'open',
            explanation: $explanation,
            project_id: $project_id,
            created_at: $created_at
        })
        RETURN c.id, c.status, c.explanation, c.project_id, c.created_at
        """
        res = self.get_graph().query(query, params={
            "id": cid,
            "explanation": explanation,
            "project_id": project_id,
            "created_at": now
        })
        r = res.result_set[0]

        # Link conflict to memories and link memories to each other with CONTRADICTS
        for mid in memory_ids:
            link_query = """
            MATCH (c:Conflict {id: $cid}), (m:Memory {id: $mid})
            MERGE (c)-[:INVOLVES]->(m)
            """
            self.get_graph().query(link_query, params={"cid": cid, "mid": mid})

        if len(memory_ids) >= 2:
            self.link_memories(memory_ids[0], memory_ids[1], "CONTRADICTS")
            self.link_memories(memory_ids[1], memory_ids[0], "CONTRADICTS")

        return {
            "id": r[0],
            "status": r[1],
            "explanation": r[2],
            "project_id": r[3],
            "created_at": str(r[4]),
            "involved_memory_ids": memory_ids,
            "resolution_note": None
        }

    def list_conflicts(self, project_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        status_filter = "AND c.status = $status" if status else ""
        query = f"""
        MATCH (c:Conflict {project_id: $project_id})
        WHERE 1=1 {status_filter}
        OPTIONAL MATCH (c)-[:INVOLVES]->(m:Memory)
        RETURN c.id, c.status, c.explanation, c.project_id, c.created_at, c.resolution_note, collect(m.id) AS mem_ids
        ORDER BY c.created_at DESC
        """
        params = {"project_id": project_id}
        if status:
            params["status"] = status

        res = self.get_graph().query(query, params=params)
        conflicts = []
        for r in res.result_set:
            conflicts.append({
                "id": r[0],
                "status": r[1],
                "explanation": r[2],
                "project_id": r[3],
                "created_at": str(r[4]) if r[4] else None,
                "resolution_note": r[5],
                "involved_memory_ids": r[6] if r[6] else []
            })
        return conflicts

    def resolve_conflict(self, conflict_id: str, status: str, resolution_note: str, winning_memory_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (c:Conflict {id: $id})
        SET c.status = $status, c.resolution_note = $resolution_note
        WITH c
        OPTIONAL MATCH (c)-[:INVOLVES]->(m:Memory)
        RETURN c.id, c.status, c.explanation, c.project_id, c.created_at, c.resolution_note, collect(m.id) AS mem_ids
        """
        res = self.get_graph().query(query, params={
            "id": conflict_id,
            "status": status,
            "resolution_note": resolution_note
        })
        if not res.result_set:
            return None
        r = res.result_set[0]

        # If a winning memory was chosen, adjust confidence or annotate
        if winning_memory_id:
            win_query = """
            MATCH (m:Memory {id: $mid})
            SET m.confidence = 1.0, m.resolution = 'accepted_in_conflict'
            """
            self.get_graph().query(win_query, params={"mid": winning_memory_id})

        return {
            "id": r[0],
            "status": r[1],
            "explanation": r[2],
            "project_id": r[3],
            "created_at": str(r[4]) if r[4] else None,
            "resolution_note": r[5],
            "involved_memory_ids": r[6] if r[6] else []
        }

    # --- Task Operations ---

    def create_task(self, title: str, priority: str, project_id: str, informing_memory_ids: List[str]) -> Dict[str, Any]:
        tid = f"task_{uuid.uuid4().hex[:8]}"
        query = """
        CREATE (t:Task {
            id: $id,
            title: $title,
            status: 'todo',
            priority: $priority,
            project_id: $project_id
        })
        RETURN t.id, t.title, t.status, t.priority, t.project_id
        """
        res = self.get_graph().query(query, params={
            "id": tid,
            "title": title,
            "priority": priority,
            "project_id": project_id
        })
        r = res.result_set[0]

        # Link memory to task: Memory -[:INFORMS]-> Task
        for mid in informing_memory_ids:
            link_q = """
            MATCH (m:Memory {id: $mid}), (t:Task {id: $tid})
            MERGE (m)-[:INFORMS]->(t)
            """
            self.get_graph().query(link_q, params={"mid": mid, "tid": tid})

        return {
            "id": r[0],
            "title": r[1],
            "status": r[2],
            "priority": r[3],
            "project_id": r[4],
            "informing_memory_ids": informing_memory_ids
        }

    # --- Graph Serialization for Visualization (/api/graph) ---

    def get_full_graph(self, project_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns nodes and edges formatted for Cytoscape.js or Force Graph."""
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        edges_list: List[Dict[str, Any]] = []

        # 1. Fetch Memories
        mem_query = """
        MATCH (m:Memory {project_id: $project_id})
        RETURN m.id, m.content, m.memory_type, m.confidence, m.timestamp
        """
        res_mem = self.get_graph().query(mem_query, params={"project_id": project_id})
        for r in res_mem.result_set:
            nodes_dict[r[0]] = {
                "id": r[0],
                "label": "Memory",
                "properties": {
                    "content": r[1],
                    "memory_type": r[2],
                    "confidence": float(r[3]),
                    "timestamp": str(r[4])
                }
            }

        # 2. Fetch Sessions
        sess_query = """
        MATCH (s:Session {project_id: $project_id})
        RETURN s.session_id, s.created_at
        """
        res_sess = self.get_graph().query(sess_query, params={"project_id": project_id})
        for r in res_sess.result_set:
            nodes_dict[f"session_{r[0]}"] = {
                "id": f"session_{r[0]}",
                "label": "Session",
                "properties": {
                    "session_id": r[0],
                    "created_at": str(r[1])
                }
            }

        # 3. Fetch Agents
        agent_query = """
        MATCH (a:Agent)
        RETURN a.name, a.role
        """
        res_agent = self.get_graph().query(agent_query)
        for r in res_agent.result_set:
            nodes_dict[f"agent_{r[0]}"] = {
                "id": f"agent_{r[0]}",
                "label": "Agent",
                "properties": {
                    "name": r[0],
                    "role": r[1]
                }
            }

        # 4. Fetch Tasks
        task_query = """
        MATCH (t:Task {project_id: $project_id})
        RETURN t.id, t.title, t.status, t.priority
        """
        res_task = self.get_graph().query(task_query, params={"project_id": project_id})
        for r in res_task.result_set:
            nodes_dict[r[0]] = {
                "id": r[0],
                "label": "Task",
                "properties": {
                    "title": r[1],
                    "status": r[2],
                    "priority": r[3]
                }
            }

        # 5. Fetch Conflicts
        conf_query = """
        MATCH (c:Conflict {project_id: $project_id})
        RETURN c.id, c.status, c.explanation
        """
        res_conf = self.get_graph().query(conf_query, params={"project_id": project_id})
        for r in res_conf.result_set:
            nodes_dict[r[0]] = {
                "id": r[0],
                "label": "Conflict",
                "properties": {
                    "status": r[1],
                    "explanation": r[2]
                }
            }

        # 6. Fetch all Edges between matched nodes
        edge_query = """
        MATCH (n)-[r]->(m)
        WHERE (n.project_id = $project_id OR n:Agent) AND (m.project_id = $project_id OR m:Agent)
        RETURN id(r) AS eid, 
               CASE WHEN n:Session THEN 'session_' + n.session_id 
                    WHEN n:Agent THEN 'agent_' + n.name 
                    ELSE coalesce(n.id, id(n)) END AS src,
               CASE WHEN m:Session THEN 'session_' + m.session_id 
                    WHEN m:Agent THEN 'agent_' + m.name 
                    ELSE coalesce(m.id, id(m)) END AS tgt,
               type(r) AS rel_type
        """
        res_edge = self.get_graph().query(edge_query, params={"project_id": project_id})
        edge_seen = set()
        for r in res_edge.result_set:
            eid = str(r[0])
            src = str(r[1])
            tgt = str(r[2])
            rel = str(r[3])
            edge_key = f"{src}->{tgt}:{rel}"
            if edge_key not in edge_seen:
                edge_seen.add(edge_key)
                edges_list.append({
                    "id": f"e_{eid}_{src}_{tgt}",
                    "source": src,
                    "target": tgt,
                    "label": rel,
                    "properties": {}
                })

        return {
            "nodes": list(nodes_dict.values()),
            "edges": edges_list
        }

graph_service = GraphService()
