"""Production data purge — wipes all transactional data while preserving
every piece of master/configuration data. Callable both via HTTP
(`POST /api/production/purge`) and via CLI (`python -m scripts.production_purge`).

Preserved (master data):
    departments, classes, fee_heads, fee_structures, receipt_types,
    bus_stops, bus_routes, users, settings, config_defaults

Deleted (transactional data):
    students, receipts, vouchers (all rows in receipts collection),
    adjustments, payment_extensions, reminders, notices, audit_log,
    config_snapshots, updates, backups (records only — ZIP files on disk
    kept unless `also_clear_backup_files=true`), staged updates on disk,
    every counter is reset to 0 so numbering restarts.

Every purge action is atomic per-collection; if a delete fails half-way the
result document reports exactly what was and was not cleared so the admin
can retry.
"""
from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime, timezone
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from core import db, audit, now_iso, require_admin_pin

router = APIRouter(prefix="/api/production", tags=["production"])

# Every transactional collection we know about.
TRANSACTIONAL_COLLECTIONS: List[str] = [
    "students",
    "receipts",
    "adjustments",
    "payment_extensions",
    "reminders",
    "notices",
    "audit_log",
    "config_snapshots",
    "updates",
    "backups",
    "diagnostics_snapshots",
]

MASTER_COLLECTIONS: List[str] = [
    "departments", "classes", "fee_heads", "fee_structures",
    "receipt_types", "bus_stops", "bus_routes", "users",
    "settings", "config_defaults",
]

STAGING_DIRS = [
    Path("/app/updates/staging"),
    Path("/app/updates/rollback"),
]
BACKUPS_DIR = Path("/app/backups")


class PurgeIn(BaseModel):
    confirm_phrase: str
    also_clear_backup_files: bool = False
    also_clear_staged_updates: bool = True


@router.post("/purge")
async def purge(
    body: PurgeIn = Body(...),
    user = Depends(require_admin_pin),
):
    """Requires Administrator PIN AND the exact phrase "PURGE DEMO DATA"."""
    if body.confirm_phrase != "PURGE DEMO DATA":
        raise HTTPException(400, 'Confirmation phrase must be exactly: "PURGE DEMO DATA"')

    result: Dict[str, Any] = {
        "started_at": now_iso(),
        "collections_deleted": {},
        "counters_reset": 0,
        "master_data_preserved": {},
        "disk_actions": [],
    }

    # 1) Delete every transactional collection
    for coll in TRANSACTIONAL_COLLECTIONS:
        try:
            r = await db[coll].delete_many({})
            result["collections_deleted"][coll] = r.deleted_count
        except Exception as e:
            result["collections_deleted"][coll] = f"ERROR: {e}"

    # 2) Count master data (for confidence in the report)
    for coll in MASTER_COLLECTIONS:
        try:
            result["master_data_preserved"][coll] = await db[coll].count_documents({})
        except Exception as e:
            result["master_data_preserved"][coll] = f"ERROR: {e}"

    # 3) Reset receipt / voucher / snapshot / adm-no counters
    try:
        cr = await db.counters.delete_many({})
        result["counters_reset"] = cr.deleted_count
    except Exception as e:
        result["counters_reset"] = f"ERROR: {e}"

    # 4) Optional disk clean-up
    if body.also_clear_staged_updates:
        for d in STAGING_DIRS:
            if d.exists():
                try:
                    for child in d.iterdir():
                        if child.is_dir(): shutil.rmtree(child, ignore_errors=True)
                        else: child.unlink(missing_ok=True)
                    result["disk_actions"].append(f"cleared {d}")
                except Exception as e:
                    result["disk_actions"].append(f"ERROR clearing {d}: {e}")

    if body.also_clear_backup_files and BACKUPS_DIR.exists():
        try:
            removed = 0
            for f in BACKUPS_DIR.glob("*.zip"):
                f.unlink(); removed += 1
            result["disk_actions"].append(f"deleted {removed} backup zip(s)")
        except Exception as e:
            result["disk_actions"].append(f"ERROR clearing backup files: {e}")

    result["completed_at"] = now_iso()

    # 5) Audit — first entry of the fresh production database
    try:
        await audit(user, "production_purge", "system", "purge", {
            "collections_deleted": result["collections_deleted"],
            "counters_reset": result["counters_reset"],
            "also_clear_backup_files": body.also_clear_backup_files,
        })
    except Exception:
        pass

    return result


@router.get("/purge/preview")
async def purge_preview(user = Depends(require_admin_pin)):
    """Read-only counts of what a purge WOULD delete vs. preserve."""
    tx = {}
    for coll in TRANSACTIONAL_COLLECTIONS:
        try:
            tx[coll] = await db[coll].count_documents({})
        except Exception as e:
            tx[coll] = f"ERROR: {e}"
    master = {}
    for coll in MASTER_COLLECTIONS:
        try:
            master[coll] = await db[coll].count_documents({})
        except Exception as e:
            master[coll] = f"ERROR: {e}"
    try:
        counter_count = await db.counters.count_documents({})
    except Exception as e:
        counter_count = f"ERROR: {e}"
    return {
        "would_delete": tx,
        "would_reset_counters": counter_count,
        "would_preserve": master,
        "confirm_phrase_required": "PURGE DEMO DATA",
    }
