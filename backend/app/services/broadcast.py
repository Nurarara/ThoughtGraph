from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str | None = None) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        if user_id:
            self.user_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for user_id, sockets in list(self.user_connections.items()):
            if websocket in sockets:
                sockets.remove(websocket)
            if not sockets:
                self.user_connections.pop(user_id, None)

    async def broadcast_json(self, payload: dict) -> None:
        stale: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        stale: list[WebSocket] = []
        for connection in self.user_connections.get(user_id, []):
            try:
                await connection.send_json(payload)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()
