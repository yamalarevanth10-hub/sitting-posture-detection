import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from database.db import (
    init_db, save_session, get_recent_sessions,
    get_analytics_summary, get_settings, update_settings
)

# Initialize database
init_db()

app = FastAPI(
    title="Digital Wellness Monitor - Posture & Eye Blink Detection AI",
    description="Major Project Web Application for real-time sitting posture detection, eye blinking, and break alerts.",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Digital Wellness Monitor", "version": "2.0.0"}

@app.get("/api/settings")
async def fetch_settings():
    return get_settings()

@app.post("/api/settings")
async def save_settings_endpoint(request: Request):
    data = await request.json()
    update_settings(data)
    return {"status": "success", "message": "Settings updated"}

@app.post("/api/sessions/save")
async def record_session(request: Request):
    data = await request.json()
    session_id = save_session(data)
    return {"status": "success", "session_id": session_id}

@app.get("/api/sessions/history")
async def fetch_history(limit: int = 15):
    sessions = get_recent_sessions(limit)
    return {"sessions": sessions}

@app.get("/api/sessions/summary")
async def fetch_summary():
    summary = get_analytics_summary()
    return {"summary": summary}

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  [*] Digital Wellness Monitor Server Starting...")
    print("  [>] Web Interface: http://localhost:8000")
    print("  [>] API Docs:      http://localhost:8000/docs")
    print("=" * 65 + "\n")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
