"""Vercel entrypoint that exposes the FastAPI app."""

from pathlib import Path
import sys

from fastapi import Request

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


@app.middleware("http")
async def restore_vercel_api_path(request: Request, call_next):
    path = request.query_params.get("__orbit_path")
    if path:
        request.scope["path"] = f"/api/{path.lstrip('/')}"
    return await call_next(request)
