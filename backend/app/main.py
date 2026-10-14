import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.services.graph_service import graph_service
from app.api import health, sessions, chat, memories, graph, conflicts

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure indices in FalkorDB
    try:
        graph_service.init_indices()
    except Exception as e:
        print(f"Index initialization warning: {e}")
    yield
    # Shutdown logic if needed

app = FastAPI(
    title="AgentMesh Backend",
    description="Multi-agent persistent memory application with FalkorDB graph layer",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(health.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(memories.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(conflicts.router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>AgentMesh - FalkorDB Multi-Agent Memory</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
        <style>
            :root {
                --bg: #090d16;
                --panel: #111827;
                --panel-border: rgba(255, 255, 255, 0.08);
                --accent: #6366f1;
                --accent-glow: rgba(99, 102, 241, 0.25);
                --text: #f3f4f6;
                --text-muted: #9ca3af;
                --danger: #ef4444;
                --warning: #f59e0b;
                --success: #10b981;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                background: var(--bg);
                color: var(--text);
                font-family: 'Outfit', sans-serif;
                height: 100vh;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            header {
                height: 60px;
                padding: 0 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid var(--panel-border);
                background: rgba(17, 24, 39, 0.8);
                backdrop-filter: blur(10px);
                z-index: 10;
            }
            .logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.25rem; letter-spacing: -0.5px; }
            .badge {
                font-size: 0.75rem;
                padding: 3px 8px;
                border-radius: 9999px;
                background: var(--accent-glow);
                color: #818cf8;
                border: 1px solid rgba(99, 102, 241, 0.4);
                font-family: 'JetBrains Mono', monospace;
            }
            .status-pill {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.8rem;
                padding: 4px 12px;
                border-radius: 999px;
                background: #1f2937;
                border: 1px solid var(--panel-border);
            }
            .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
            main {
                flex: 1;
                display: grid;
                grid-template-columns: 360px 1fr 340px;
                overflow: hidden;
            }
            .panel {
                background: var(--panel);
                border-right: 1px solid var(--panel-border);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            .panel-header {
                padding: 14px 18px;
                font-weight: 600;
                font-size: 0.9rem;
                border-bottom: 1px solid var(--panel-border);
                display: flex;
                justify-content: space-between;
                align-items: center;
                color: #e5e7eb;
            }
            .chat-messages {
                flex: 1;
                padding: 16px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .chat-bubble {
                padding: 12px 14px;
                border-radius: 10px;
                font-size: 0.88rem;
                line-height: 1.45;
                max-width: 90%;
            }
            .user-bubble {
                align-self: flex-end;
                background: var(--accent);
                color: white;
            }
            .agent-bubble {
                align-self: flex-start;
                background: #1f2937;
                border: 1px solid var(--panel-border);
                color: #d1d5db;
                font-family: 'Outfit', sans-serif;
            }
            .agent-steps {
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.72rem;
                color: #9ca3af;
            }
            .chat-input-bar {
                padding: 14px;
                border-top: 1px solid var(--panel-border);
                display: flex;
                gap: 8px;
                background: #0f172a;
            }
            .chat-input-bar input {
                flex: 1;
                background: #1e293b;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px 14px;
                color: white;
                font-family: inherit;
                outline: none;
            }
            .chat-input-bar button {
                background: var(--accent);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
                font-weight: 600;
                cursor: pointer;
            }
            #graph-container {
                position: relative;
                width: 100%;
                height: 100%;
                background: #080c14;
            }
            #cy { width: 100%; height: 100%; }
            .conflict-list, .task-list {
                padding: 12px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .card {
                background: #1e293b;
                border: 1px solid var(--panel-border);
                border-radius: 8px;
                padding: 12px;
                font-size: 0.84rem;
            }
            .conflict-card { border-left: 4px solid var(--danger); }
            .task-card { border-left: 4px solid var(--accent); }
            .btn-sm {
                margin-top: 8px;
                padding: 4px 10px;
                font-size: 0.75rem;
                border-radius: 4px;
                background: rgba(239, 68, 68, 0.2);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
                cursor: pointer;
            }
            .session-select {
                background: #1e293b;
                color: white;
                border: 1px solid var(--panel-border);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 0.8rem;
            }
        </style>
    </head>
    <body>
        <header>
            <div class="logo">
                <span>🕸️ AgentMesh</span>
                <span class="badge">FalkorDB Context Engine</span>
            </div>
            <div style="display: flex; align-items: center; gap: 16px;">
                <div>
                    <label style="font-size: 0.8rem; color: var(--text-muted); margin-right: 6px;">Session:</label>
                    <select id="session-select" class="session-select" onchange="changeSession()">
                        <option value="session-1">Session 1 (Arch Setup)</option>
                        <option value="session-2">Session 2 (Revision / Conflict)</option>
                        <option value="session-3">Session 3 (Execution)</option>
                    </select>
                </div>
                <div class="status-pill">
                    <span class="status-dot" id="status-dot"></span>
                    <span id="status-text">FalkorDB Connected</span>
                </div>
                <a href="/docs" target="_blank" style="color: #818cf8; font-size: 0.8rem; text-decoration: none;">API Docs ↗</a>
            </div>
        </header>
        <main>
            <!-- Left: Multi-Agent Conversation -->
            <div class="panel">
                <div class="panel-header">
                    <span>Multi-Agent Chat</span>
                    <span style="font-size: 0.72rem; color: var(--text-muted);">Researcher • Reviewer • Planner</span>
                </div>
                <div class="chat-messages" id="chat-messages">
                    <div class="chat-bubble agent-bubble">
                        Welcome to AgentMesh! I use <strong>FalkorDB</strong> as my active context layer. Speak naturally: state decisions, change architectural specs, or assign tasks. I track cross-session state and detect contradictions automatically.
                    </div>
                </div>
                <div class="chat-input-bar">
                    <input type="text" id="chat-input" placeholder="e.g. We chose PostgreSQL for our database..." onkeydown="if(event.key==='Enter') sendChat()">
                    <button onclick="sendChat()">Send</button>
                </div>
            </div>

            <!-- Center: Interactive Memory Graph -->
            <div id="graph-container">
                <div style="position: absolute; top: 12px; left: 16px; z-index: 5; pointer-events: none;">
                    <h3 style="font-size: 0.95rem; font-weight: 600; color: #e5e7eb;">Live FalkorDB Graph</h3>
                    <p style="font-size: 0.75rem; color: var(--text-muted);">Nodes: Memories, Agents, Tasks, Conflicts | Edges: CONTAINS, CREATED, RELATES_TO, CONTRADICTS, INFORMS</p>
                </div>
                <button onclick="refreshGraph()" style="position: absolute; top: 12px; right: 16px; z-index: 5; background: #1f2937; color: #e5e7eb; border: 1px solid var(--panel-border); border-radius: 6px; padding: 6px 12px; font-size: 0.75rem; cursor: pointer;">↻ Refresh Graph</button>
                <div id="cy"></div>
            </div>

            <!-- Right: Conflicts & Tasks -->
            <div class="panel" style="border-right: none; border-left: 1px solid var(--panel-border);">
                <div class="panel-header" style="color: #f87171;">
                    <span>⚠️ Contradictions</span>
                    <span id="conflict-count" class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border-color: rgba(239, 68, 68, 0.4);">0 Open</span>
                </div>
                <div class="conflict-list" id="conflict-list">
                    <div style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 16px;">No conflicts detected yet.</div>
                </div>
                <div class="panel-header" style="border-top: 1px solid var(--panel-border);">
                    <span>📋 Derived Tasks</span>
                    <span id="task-count" class="badge">0</span>
                </div>
                <div class="task-list" id="task-list">
                    <div style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 16px;">No tasks created yet.</div>
                </div>
            </div>
        </main>

        <script>
            let currentSession = 'session-1';
            let cy = null;

            async function init() {
                checkHealth();
                initCytoscape();
                refreshGraph();
                refreshConflicts();
            }

            async function checkHealth() {
                try {
                    const res = await fetch('/api/health');
                    const data = await res.json();
                    if(data.database_connected) {
                        document.getElementById('status-dot').style.background = '#10b981';
                        document.getElementById('status-text').textContent = `FalkorDB (${data.node_count} nodes, ${data.edge_count} edges)`;
                    } else {
                        document.getElementById('status-dot').style.background = '#ef4444';
                        document.getElementById('status-text').textContent = 'FalkorDB Offline (Mock Mode)';
                    }
                } catch(e) {
                    document.getElementById('status-dot').style.background = '#f59e0b';
                    document.getElementById('status-text').textContent = 'Connecting...';
                }
            }

            function changeSession() {
                currentSession = document.getElementById('session-select').value;
                addMessage('agent', `Switched to <strong>${currentSession}</strong>. FalkorDB context will span all sessions in this project.`);
                refreshGraph();
            }

            function addMessage(sender, text, steps = []) {
                const box = document.getElementById('chat-messages');
                const div = document.createElement('div');
                div.className = `chat-bubble ${sender === 'user' ? 'user-bubble' : 'agent-bubble'}`;
                
                let html = text.replace(/\\n/g, '<br>');
                if(steps && steps.length > 0) {
                    html += '<div class="agent-steps"><strong>Agent Execution Trace:</strong><br>';
                    steps.forEach(s => {
                        html += `• [${s.agent}] ${s.action}<br>`;
                    });
                    html += '</div>';
                }
                div.innerHTML = html;
                box.appendChild(div);
                box.scrollTop = box.scrollHeight;
            }

            async function sendChat() {
                const input = document.getElementById('chat-input');
                const msg = input.value.trim();
                if(!msg) return;

                addMessage('user', msg);
                input.value = '';

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            message: msg,
                            session_id: currentSession,
                            project_id: 'default_project'
                        })
                    });
                    const data = await res.json();
                    addMessage('agent', data.response, data.agent_steps);
                    refreshGraph();
                    refreshConflicts();
                    if(data.new_tasks && data.new_tasks.length > 0) {
                        renderTasks(data.new_tasks);
                    }
                } catch(e) {
                    addMessage('agent', 'Error connecting to AgentMesh API.');
                }
            }

            async function refreshConflicts() {
                try {
                    const res = await fetch('/api/conflicts?project_id=default_project');
                    const conflicts = await res.json();
                    const container = document.getElementById('conflict-list');
                    const badge = document.getElementById('conflict-count');
                    badge.textContent = `${conflicts.length} Open`;

                    if(conflicts.length === 0) {
                        container.innerHTML = '<div style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 16px;">No conflicts detected.</div>';
                        return;
                    }

                    container.innerHTML = '';
                    conflicts.forEach(c => {
                        const div = document.createElement('div');
                        div.className = 'card conflict-card';
                        div.innerHTML = `
                            <div style="font-weight: 600; color: #f87171; margin-bottom: 4px;">Conflict #${c.id}</div>
                            <div>${c.explanation}</div>
                            <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 6px;">Involves: ${c.involved_memory_ids.join(', ')}</div>
                            <button class="btn-sm" onclick="resolveConflict('${c.id}')">Resolve Conflict</button>
                        `;
                        container.appendChild(div);
                    });
                } catch(e) {}
            }

            async function resolveConflict(id) {
                const note = prompt("Enter resolution notes (e.g. 'Accepted newer architecture decision'):");
                if(!note) return;
                await fetch(`/api/conflicts/${id}/resolve`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ status: 'resolved', resolution_note: note })
                });
                refreshConflicts();
                refreshGraph();
            }

            function renderTasks(tasks) {
                const container = document.getElementById('task-list');
                const badge = document.getElementById('task-count');
                badge.textContent = tasks.length;
                container.innerHTML = '';
                tasks.forEach(t => {
                    const div = document.createElement('div');
                    div.className = 'card task-card';
                    div.innerHTML = `
                        <div style="font-weight: 600;">${t.title}</div>
                        <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 4px;">Priority: ${t.priority} | Status: ${t.status}</div>
                    `;
                    container.appendChild(div);
                });
            }

            function initCytoscape() {
                cy = cytoscape({
                    container: document.getElementById('cy'),
                    style: [
                        {
                            selector: 'node',
                            style: {
                                'label': 'data(name)',
                                'color': '#ffffff',
                                'font-size': '10px',
                                'text-valign': 'bottom',
                                'text-margin-y': '6px',
                                'background-color': '#6366f1'
                            }
                        },
                        { selector: 'node[type="Memory"]', style: { 'background-color': '#3b82f6', 'shape': 'ellipse' } },
                        { selector: 'node[type="Agent"]', style: { 'background-color': '#10b981', 'shape': 'round-rectangle' } },
                        { selector: 'node[type="Session"]', style: { 'background-color': '#8b5cf6', 'shape': 'hexagon' } },
                        { selector: 'node[type="Task"]', style: { 'background-color': '#f59e0b', 'shape': 'diamond' } },
                        { selector: 'node[type="Conflict"]', style: { 'background-color': '#ef4444', 'shape': 'octagon' } },
                        {
                            selector: 'edge',
                            style: {
                                'label': 'data(label)',
                                'font-size': '8px',
                                'color': '#9ca3af',
                                'line-color': '#374151',
                                'target-arrow-color': '#374151',
                                'target-arrow-shape': 'triangle',
                                'curve-style': 'bezier',
                                'width': 1.5
                            }
                        },
                        { selector: 'edge[label="CONTRADICTS"]', style: { 'line-color': '#ef4444', 'target-arrow-color': '#ef4444', 'width': 2.5 } },
                        { selector: 'edge[label="INFORMS"]', style: { 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b' } },
                        { selector: 'edge[label="INVOLVES"]', style: { 'line-color': '#ef4444' } }
                    ],
                    layout: { name: 'cose', animate: true, padding: 50 }
                });
            }

            async function refreshGraph() {
                try {
                    const res = await fetch('/api/graph?project_id=default_project');
                    const data = await res.json();
                    if(!cy) return;

                    const elements = [];
                    data.nodes.forEach(n => {
                        let name = n.id;
                        if(n.label === 'Memory') name = (n.properties.content || '').substring(0, 20) + '...';
                        if(n.label === 'Agent') name = n.properties.name || n.id;
                        if(n.label === 'Session') name = n.properties.session_id || n.id;
                        if(n.label === 'Task') name = n.properties.title || n.id;
                        if(n.label === 'Conflict') name = 'Conflict: ' + (n.properties.explanation || '').substring(0, 15) + '...';

                        elements.push({
                            data: { id: n.id, name: name, type: n.label }
                        });
                    });

                    data.edges.forEach(e => {
                        elements.push({
                            data: { id: e.id, source: e.source, target: e.target, label: e.label }
                        });
                    });

                    cy.elements().remove();
                    cy.add(elements);
                    cy.layout({ name: 'cose', animate: false }).run();
                } catch(e) {
                    console.error("Could not fetch graph data:", e);
                }
            }

            window.onload = init;
        </script>
    </body>
    </html>
    """
