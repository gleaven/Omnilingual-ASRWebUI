"""FastAPI main application."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from typing import Dict, Set

from .core.config import settings
from .database import init_db
from .api import audio, youtube, transcription

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Web interface for Omnilingual ASR transcription system"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(audio.router)
app.include_router(youtube.router)
app.include_router(transcription.router)

# WebSocket connection manager
class ConnectionManager:
    """Manage WebSocket connections for job progress updates."""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, job_id: int, websocket: WebSocket):
        """Connect a WebSocket for a specific job."""
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

    def disconnect(self, job_id: int, websocket: WebSocket):
        """Disconnect a WebSocket."""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: int, message: dict):
        """Broadcast message to all connections for a job."""
        if job_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.add(connection)

            # Remove disconnected clients
            for connection in disconnected:
                self.active_connections[job_id].discard(connection)


manager = ConnectionManager()


@app.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: int):
    """
    WebSocket endpoint for real-time job progress updates.

    Args:
        websocket: WebSocket connection
        job_id: Job ID to monitor
    """
    await manager.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Create database tables
    init_db()

    # Ensure storage directories exist
    storage_path = Path(settings.STORAGE_PATH)
    (storage_path / "raw").mkdir(parents=True, exist_ok=True)
    (storage_path / "processed").mkdir(parents=True, exist_ok=True)
    (storage_path / "chunks").mkdir(parents=True, exist_ok=True)
    (storage_path / "temp").mkdir(parents=True, exist_ok=True)
    (storage_path / "youtube").mkdir(parents=True, exist_ok=True)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Serve frontend static files (if built)
frontend_path = Path(__file__).parent.parent.parent / "frontend" / "build"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")
