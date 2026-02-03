"""
WebSocket manager for real-time progress updates
"""
from fastapi import WebSocket
from typing import Dict, Set
import json
import logging

from ..services.job_processor import ProcessingProgress

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        # Map job_id -> set of WebSocket connections
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        if job_id not in self.connections:
            self.connections[job_id] = set()
        self.connections[job_id].add(websocket)
        logger.info(f"WebSocket connected for job {job_id}")

    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection"""
        if job_id in self.connections:
            self.connections[job_id].discard(websocket)
            if not self.connections[job_id]:
                del self.connections[job_id]
        logger.info(f"WebSocket disconnected for job {job_id}")

    async def broadcast_progress(self, progress: ProcessingProgress):
        """Broadcast progress to all connections for a job"""
        job_id = progress.job_id
        if job_id not in self.connections:
            return

        message = json.dumps({
            "type": "progress",
            "job_id": progress.job_id,
            "status": progress.status,
            "current_chunk": progress.current_chunk,
            "total_chunks": progress.total_chunks,
            "percent_complete": progress.percent_complete,
            "current_phase": progress.current_phase,
            "message": progress.message
        })

        dead_connections: Set[WebSocket] = set()

        for websocket in self.connections[job_id]:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                dead_connections.add(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws, job_id)

    def has_connections(self, job_id: str) -> bool:
        """Check if there are active connections for a job"""
        return job_id in self.connections and len(self.connections[job_id]) > 0
