"""
Unified Server Runner for Health Intelligence App.

Usage:
    python run.py

This starts the unified backend server that serves both:
- Agent backend at /agent/*
- Analytics backend at /analytics/* and /ai/*
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"\n🚀 Starting Health Intelligence API on http://{host}:{port}\n")
    
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["backend"],
    )
