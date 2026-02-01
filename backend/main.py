"""
Unified Backend Entrypoint for Health Intelligence App.

Composes two backends:
- /agent/* → Deep Analysis (LangGraph + MongoDB)
- /analytics/* and /ai/* → Visual Analytics (DuckDB)

All backend code is consolidated in this backend/ folder.
"""

import os
import sys
from pathlib import Path

# =============================================================================
# ENVIRONMENT LOADING
# =============================================================================

from dotenv import load_dotenv

# Get the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

# Load unified .env from project root
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

# =============================================================================
# PATH SETUP
# =============================================================================
# Add backend directory to sys.path for imports

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# FASTAPI APP CREATION
# =============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Health Intelligence API",
    description="Unified API for Health Analytics and Deep Analysis",
    version="1.0.0",
)

# CORS configuration for unified frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/")
async def root():
    """Root health check for unified backend."""
    return {
        "service": "Health Intelligence API",
        "version": "1.0.0",
        "backends": {
            "agent": "/agent",
            "analytics": "/analytics",
            "ai": "/ai",
        }
    }


@app.get("/health")
async def health_check():
    """Unified health check endpoint."""
    return {"status": "healthy", "service": "unified"}


# =============================================================================
# INCLUDE AGENT BACKEND (Deep Analysis)
# =============================================================================
# The agent backend exposes an APIRouter, we add the /agent prefix here

try:
    from backend.agent.api import router as agent_router
    
    app.include_router(agent_router, prefix="/agent")
    print("✓ Agent backend included at /agent")
except ImportError as e:
    print(f"⚠ Could not import agent backend: {e}")
except Exception as e:
    print(f"⚠ Error including agent backend: {e}")


# =============================================================================
# MOUNT ANALYTICS BACKEND (Visual Analytics)
# =============================================================================
# The visualisation backend exposes routers, not a full app
# We import and include the routers directly

try:
    from backend.healthdata.api.analytics import router as analytics_router
    from backend.healthdata.api.insights import router as insights_router
    from backend.healthdata.ai.api import router as ai_router
    
    # Include routers directly (they already have prefixes)
    app.include_router(analytics_router)
    app.include_router(insights_router)
    app.include_router(ai_router)
    
    print("✓ Analytics routers included at /analytics and /ai")
except ImportError as e:
    print(f"⚠ Could not import analytics backend: {e}")
except Exception as e:
    print(f"⚠ Error including analytics routers: {e}")


# =============================================================================
# STARTUP EVENT
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    print("\n" + "=" * 60)
    print("Health Intelligence API - Unified Backend")
    print("=" * 60)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Backend Dir: {BACKEND_DIR}")
    print(f"Env File: {env_file} (exists: {env_file.exists()})")
    print("=" * 60 + "\n")
