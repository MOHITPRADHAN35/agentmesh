from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

app = FastAPI(
    title="AgentMesh Backend",
    description="Multi-agent persistent memory application with FalkorDB graph layer",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration - robust for all localhost ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
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

@app.get("/", response_class=JSONResponse)
def root_info():
    return {
        "name": "AgentMesh FalkorDB API",
        "status": "ok",
        "version": "1.0.0",
        "docs": "/docs"
    }
