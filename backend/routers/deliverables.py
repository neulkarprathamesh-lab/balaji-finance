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
    """Day-to-day deliverables the administrator can pull from inside the running app.
    Full source code is delivered separately as a one-shot project ZIP for offline archival."""
    backups = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if BACKUP_DIR.exists() else []
    latest_backup = backups[0] if backups else None
    return {
        "app_version": "1.0.0", "database_version": "1", "generated_at": now_iso(),
        "sections": [
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



