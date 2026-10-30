import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import BASE_DIR, PORT, HOST, has_active_ai_provider, GEMINI_API_KEY, OPENAI_API_KEY, LLM_MODEL
from .database import init_db
from .routers import auth, interviews, candidate, admin

# Initialize DB
init_db()

app = FastAPI(
    title="AI Interview Simulator API",
    description="Backend API powering the AI-powered dynamic mock interview simulator.",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router)
app.include_router(interviews.router)
app.include_router(candidate.router)
app.include_router(admin.router)

@app.get("/api/health")
async def health_check():
    ai_status = "Live LLM Active" if has_active_ai_provider() else "Local Heuristic Engine Active"
    provider = "Gemini" if GEMINI_API_KEY else ("OpenAI" if OPENAI_API_KEY else "Local Heuristic Fallback")
    return {
        "status": "healthy",
        "ai_engine": ai_status,
        "provider": provider,
        "model": LLM_MODEL if has_active_ai_provider() else "built-in rule/context engine",
        "has_credentials": has_active_ai_provider()
    }

# Serve root index.html
@app.get("/")
async def serve_root():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "AI Interview Simulator backend is running. Frontend index.html not found."}

# Mount static frontend files (CSS, JS, and HTML pages)
# Note: StaticFiles will serve /css/style.css, /js/api.js, and any .html file directly
app.mount("/", StaticFiles(directory=str(BASE_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=HOST, port=PORT, reload=True)
