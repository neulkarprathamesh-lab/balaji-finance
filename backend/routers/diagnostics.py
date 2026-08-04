"""System Diagnostics — server-side checks for DB, backup folder, disk, versions."""
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from core import db, client, get_current_user, now_iso, BACKUP_DIR

router = APIRouter(prefix="/api", tags=["diagnostics"])

APP_VERSION = "1.0.0"
DATABASE_VERSION = "1"


def _check(name: str, ok: bool, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    return {"name": name, "ok": ok, "status": "ok" if ok else "fail", "message": message, "details": details or {}}


@router.get("/diagnostics")
async def system_diagnostics(user = Depends(get_current_user)):
    """Runs every server-side diagnostic check and returns a structured report.
    The frontend adds its own checks (Main Server latency, printer, camera/scanner, LAN)
    and merges the results into a single view."""
    checks: List[Dict[str, Any]] = []

    # 1. Database connection
    try:
        t0 = time.perf_counter()
        pong = await client.admin.command("ping")
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        checks.append(_check(
            "Database connection", bool(pong.get("ok")),
            f"MongoDB responded to ping in {latency_ms} ms",
            {"latency_ms": latency_ms, "database": db.name},
        ))
    except Exception as e:
        checks.append(_check("Database connection", False, f"Cannot reach MongoDB: {e}"))

    # 2. Database version + schema version
    try:
        info = await client.admin.command("buildInfo")
        mongo_version = info.get("version", "unknown")
        collections = await db.list_collection_names()
        checks.append(_check(
            "Database version", True,
            f"MongoDB {mongo_version}, schema v{DATABASE_VERSION}, {len(collections)} collections",
            {"mongo_version": mongo_version, "schema_version": DATABASE_VERSION,
             "collections_count": len(collections)},
        ))
    except Exception as e:
        checks.append(_check("Database version", False, f"Cannot read database version: {e}"))

    # 3. Software version
    checks.append(_check(
        "Software version", True,
        f"Balaji Convent Fee Software v{APP_VERSION}",
        {"app_version": APP_VERSION, "build_date": "2026-02-04"},
    ))

    # 4. Backup folder access
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        test_file = BACKUP_DIR / ".diag_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        backups = sorted(BACKUP_DIR.glob("*.zip"))
        latest = backups[-1].name if backups else None
        checks.append(_check(
            "Backup folder access", True,
            f"Writable — {len(backups)} backup(s) on disk"
            + (f", latest: {latest}" if latest else ", no backups yet"),
            {"path": str(BACKUP_DIR), "backups_count": len(backups), "latest_backup": latest},
        ))
    except PermissionError as e:
        checks.append(_check("Backup folder access", False,
            f"Backup folder is not writable: {BACKUP_DIR} — {e}",
            {"path": str(BACKUP_DIR)}))
    except Exception as e:
        checks.append(_check("Backup folder access", False,
            f"Backup folder not found or inaccessible: {e}",
            {"path": str(BACKUP_DIR)}))

    # 5. Storage space
    try:
        target = BACKUP_DIR if BACKUP_DIR.exists() else Path("/app")
        total, used, free = shutil.disk_usage(target)
        gb = 1024 ** 3
        free_gb = round(free / gb, 2)
        used_pct = round((used / total) * 100, 1) if total else 0
        low = free_gb < 2
        checks.append(_check(
            "Storage space", not low,
            f"{free_gb} GB free ({used_pct}% used)" + (" — LOW, keep at least 2 GB free" if low else ""),
            {"free_gb": free_gb, "total_gb": round(total/gb, 2), "used_percent": used_pct,
             "path": str(target)},
        ))
    except Exception as e:
        checks.append(_check("Storage space", False, f"Cannot read disk usage: {e}"))

    # 6. Data-integrity spot-checks
    try:
        users_count = await db.users.count_documents({})
        students_count = await db.students.count_documents({})
        receipts_count = await db.receipts.count_documents({})
        rtypes_count = await db.receipt_types.count_documents({})
        ok = users_count > 0 and rtypes_count > 0
        checks.append(_check(
            "Seed data", ok,
            f"{users_count} users · {students_count} students · {receipts_count} receipts · {rtypes_count} receipt types"
            + ("" if ok else " — seed missing"),
            {"users": users_count, "students": students_count, "receipts": receipts_count,
             "receipt_types": rtypes_count},
        ))
    except Exception as e:
        checks.append(_check("Seed data", False, f"Cannot read collections: {e}"))

    overall_ok = all(c["ok"] for c in checks)
    return {
        "generated_at": now_iso(),
        "generated_by": user["name"],
        "overall_ok": overall_ok,
        "server_side_checks": checks,
        "app_version": APP_VERSION,
        "database_version": DATABASE_VERSION,
    }
