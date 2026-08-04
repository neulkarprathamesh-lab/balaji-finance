"""Final Delivery Center — one aggregator endpoint that lists every downloadable artefact.
Also exposes lightweight generators for the license doc and the receipt-types JSON."""
import io
import json as _json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse
from core import db, get_current_user, now_iso, require_admin_pin, require_roles

router = APIRouter(prefix="/api", tags=["deliverables"])

DIST_DIR = Path("/app/dist")
DL_DIR = Path("/app/frontend/public/downloads")
BACKUP_DIR = Path("/app/backups")


def _file_meta(p: Path, label: str, category: str) -> Dict[str, Any]:
    if not p.exists():
        return {"label": label, "category": category, "available": False,
                "note": "Not yet built — click 'Rebuild' in Admin → Install Package."}
    size = p.stat().st_size
    mtime = datetime.fromtimestamp(p.stat().st_mtime).isoformat()
    return {
        "label": label, "category": category, "available": True,
        "size_bytes": size, "size_mb": round(size / 1024 / 1024, 2),
        "modified_at": mtime,
        "download_url": f"/downloads/{p.name}" if p.parent == DL_DIR else None,
    }


@router.get("/deliverables/manifest")
async def deliverables_manifest(user = Depends(require_roles("administrator"))):
    """Curated list of every deliverable the administrator can download."""
    zip_path = DL_DIR / "BalajiConventFeeSoftware-v1.0.zip"
    backups = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if BACKUP_DIR.exists() else []
    latest_backup = backups[0] if backups else None
    return {
        "app_version": "1.0.0", "database_version": "1", "generated_at": now_iso(),
        "sections": [
            {"title": "Complete Project Source", "icon": "package",
             "items": [
                 {**_file_meta(zip_path, "Full source ZIP (frontend + backend + docs + assets)", "project_zip"),
                  "endpoint": None, "route": "/downloads/BalajiConventFeeSoftware-v1.0.zip"},
             ]},
            {"title": "Deployment Package", "icon": "server",
             "items": [
                 {"label": "Distribution ZIP (Windows one-click installer)",
                  "available": zip_path.exists(),
                  "route": "/downloads/BalajiConventFeeSoftware-v1.0.zip",
                  "note": "Contains install-main-server.bat, install-client-pc.bat, preflight.bat, START_HERE.md, .env.example files, and the source code.",
                  "size_mb": round(zip_path.stat().st_size / 1024 / 1024, 2) if zip_path.exists() else None,
                  },
             ]},
            {"title": "Database Package", "icon": "database",
             "items": [
                 {"label": "Latest database backup",
                  "endpoint": f"/api/config/backups/{backups[0].stem.split('-')[-1]}/download" if latest_backup else None,
                  "manual_url": "/api/config/backups", "available": bool(latest_backup),
                  "note": "Full mongodump-style JSON per collection, with manifest.json + SHA-256 checksum."},
                 {"label": "Trigger a new backup now",
                  "endpoint": "/api/config/backup", "method": "POST",
                  "available": True,
                  "note": "Requires Administrator PIN."},
             ]},
            {"title": "Configuration Export", "icon": "settings",
             "items": [
                 {"label": "School configuration (settings, departments, classes, fee structures, receipt types, bus routes, users w/o passwords)",
                  "endpoint": "/api/config/export", "method": "GET",
                  "available": True,
                  "note": "Streams a ZIP with one JSON per collection + README + manifest. Requires Admin PIN."},
             ]},
            {"title": "Receipt Templates", "icon": "receipt",
             "items": [
                 {"label": "Receipt types + layout toggles (all 9 types)",
                  "endpoint": "/api/deliverables/receipt-types-json", "method": "GET",
                  "available": True,
                  "note": "Every receipt type with prefix, category, fields, print template, watermark, QR/barcode settings."},
             ]},
            {"title": "Documentation", "icon": "book",
             "items": [
                 {"label": "License & Ownership", "endpoint": "/api/deliverables/license", "method": "GET", "available": True},
                 {"label": "Release Notes v1.0", "endpoint": "/api/deliverables/release-notes", "method": "GET", "available": True},
                 {"label": "Self-Host Guide", "route": "/SELF_HOST_GUIDE.md", "available": Path("/app/SELF_HOST_GUIDE.md").exists()},
             ]},
            {"title": "Version & Audit", "icon": "history",
             "items": [
                 {"label": "Current version snapshot",
                  "endpoint": "/api/version", "method": "GET", "available": True},
                 {"label": "Diagnostics report",
                  "endpoint": "/api/diagnostics", "method": "GET", "available": True},
             ]},
        ],
    }


@router.get("/deliverables/license")
async def download_license(user = Depends(require_roles("administrator"))):
    p = DIST_DIR / "BalajiConventFeeSoftware-v1.0" / "LICENSE_AND_OWNERSHIP.md"
    if not p.exists():
        raise HTTPException(404, "License document not yet built.")
    return StreamingResponse(
        open(p, "rb"), media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="LICENSE_AND_OWNERSHIP.md"'},
    )


@router.get("/deliverables/release-notes")
async def download_release_notes(user = Depends(require_roles("administrator"))):
    p = DIST_DIR / "BalajiConventFeeSoftware-v1.0" / "RELEASE_NOTES.md"
    if not p.exists():
        raise HTTPException(404, "Release notes not yet built.")
    return StreamingResponse(
        open(p, "rb"), media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="RELEASE_NOTES_v1.0.md"'},
    )


@router.get("/deliverables/receipt-types-json")
async def download_receipt_types(user = Depends(require_roles("administrator"))):
    rows = await db.receipt_types.find({}, {"_id": 0}).sort("display_order", 1).to_list(200)
    payload = _json.dumps({"exported_at": now_iso(), "count": len(rows), "receipt_types": rows}, indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(payload.encode()), media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="receipt-types-v1.0.json"'},
    )


@router.get("/deliverables/full-project-metadata")
async def full_project_metadata(user = Depends(require_roles("administrator"))):
    """Structural metadata that helps another developer onboard: routes, collections, versions."""
    from fastapi.routing import APIRoute
    from starlette.requests import Request
    routes_info: List[Dict[str, Any]] = []
    # Introspect FastAPI app via db._client (not clean but avoids circular)
    # Simpler: hard-declare structure summary
    collections = await db.list_collection_names()
    return {
        "generated_at": now_iso(),
        "app_version": "1.0.0", "database_version": "1",
        "backend": {
            "framework": "FastAPI",
            "python": "3.11+",
            "entry": "backend/server.py",
            "routers": [
                "routers/auth.py", "routers/catalog.py", "routers/students.py",
                "routers/receipts.py", "routers/reports.py", "routers/config_io.py",
                "routers/diagnostics.py", "routers/deliverables.py",
            ],
            "shared": "backend/core.py",
        },
        "frontend": {
            "framework": "React 19 + Vite (CRA)",
            "css": "Tailwind CSS + Shadcn UI",
            "entry": "frontend/src/App.js",
        },
        "database": {
            "engine": "MongoDB 7",
            "collections": sorted(collections),
        },
        "environment_variables": {
            "backend": ["MONGO_URL", "DB_NAME", "JWT_SECRET", "ADMIN_EMAIL", "ADMIN_PASSWORD", "ADMIN_NAME", "CORS_ORIGINS", "WEBHOOK_CRON_SECRET (optional)"],
            "frontend": ["REACT_APP_BACKEND_URL", "WDS_SOCKET_PORT"],
        },
        "build_commands": {
            "backend_setup": "cd backend && python -m venv .venv && .venv\\Scripts\\activate && pip install -r requirements.txt",
            "backend_run": "uvicorn server:app --host 0.0.0.0 --port 8001",
            "frontend_setup": "cd frontend && yarn install",
            "frontend_build": "cd frontend && yarn build",
            "frontend_dev": "cd frontend && yarn start",
        },
        "verification": {
            "backend_tests": "cd backend && pytest tests/ -q",
            "expected_tests": 47,
        },
    }
