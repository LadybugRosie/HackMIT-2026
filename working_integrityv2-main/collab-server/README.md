# Editorrah Collab Server

Yjs/Hocuspocus WebSocket server for real-time collaborative research topics; clients connect with `@hocuspocus/provider` using `name: "topic:<assignment_id>"` and an Editorrah auth token, which is verified against the FastAPI backend (`GET /api/research/collab-access/{assignment_id}`).

Run: `npm install && npm start` (from this directory).

Env vars: `PORT` (default 1235), `BACKEND_URL` (default http://localhost:8080), `DATA_DIR` (SQLite persistence dir, default ./data).
