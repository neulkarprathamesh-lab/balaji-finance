"""Departments, Classes, Fee Heads, Fee Structures + bulk import, promotion, rollover, seed-2026."""
import json as _json
from typing import Any, Dict, List, Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from core import (
    db, DepartmentIn, ClassIn, FeeHeadIn, FeeStructureIn, PromoteIn, RolloverIn,
    audit, gen_id, get_current_user, now_iso, require_roles,
)

router = APIRouter(prefix="/api", tags=["catalog"])

# ---------- Departments ----------
@router.get("/departments")
async def list_departments(user = Depends(get_current_user)):
    return await db.departments.find({}, {"_id":0}).to_list(100)

@router.post("/departments")
async def create_department(body: DepartmentIn, user = Depends(require_roles("administrator"))):
    did = gen_id()
    doc = {"id": did, **body.model_dump(), "created_at": now_iso()}
    await db.departments.insert_one(doc)
    await audit(user, "create", "department", did, body.model_dump())
    return {k:v for k,v in doc.items() if k != "_id"}

# ---------- Classes ----------
@router.get("/classes")
async def list_classes(department_id: Optional[str] = None, user = Depends(get_current_user)):
    q = {"department_id": department_id} if department_id else {}
    return await db.classes.find(q, {"_id":0}).to_list(500)

@router.post("/classes")
async def create_class(body: ClassIn, user = Depends(require_roles("administrator","manager"))):
    cid = gen_id()
    doc = {"id": cid, **body.model_dump(), "created_at": now_iso()}
    await db.classes.insert_one(doc)
    await audit(user, "create", "class", cid, body.model_dump())
    return {k:v for k,v in doc.items() if k != "_id"}

# ---------- Fee Heads ----------
@router.get("/fee-heads")
async def list_fee_heads(user = Depends(get_current_user)):
    return await db.fee_heads.find({}, {"_id":0}).to_list(200)

@router.post("/fee-heads")
async def create_fee_head(body: FeeHeadIn, user = Depends(require_roles("administrator","manager"))):
    fid = gen_id()
    doc = {"id": fid, **body.model_dump(), "created_at": now_iso()}
    await db.fee_heads.insert_one(doc)
    await audit(user, "create", "fee_head", fid, body.model_dump())
    return {k:v for k,v in doc.items() if k != "_id"}

# ---------- Fee Structures ----------
@router.get("/fee-structures")
async def list_fee_structures(department_id: Optional[str] = None, class_id: Optional[str] = None, user = Depends(get_current_user)):
    q = {}
    if department_id: q["department_id"] = department_id
    if class_id: q["class_id"] = class_id
    return await db.fee_structures.find(q, {"_id":0}).to_list(500)

@router.post("/fee-structures")
async def create_fee_structure(body: FeeStructureIn, user = Depends(require_roles("administrator","manager","accountant"))):
    fid = gen_id()
    total = sum(float(i.get("amount", 0)) for i in body.items)
    doc = {"id": fid, **body.model_dump(), "total": total, "created_at": now_iso()}
    await db.fee_structures.insert_one(doc)
    await audit(user, "create", "fee_structure", fid, {"total": total})
    return {k:v for k,v in doc.items() if k != "_id"}

@router.post("/fee-structures/{fid}/duplicate")
async def duplicate_fee_structure(fid: str, body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    src = await db.fee_structures.find_one({"id": fid}, {"_id":0})
    if not src: raise HTTPException(404, "Source structure not found")
    to_class_id = body.get("to_class_id")
    to_academic_year = body.get("to_academic_year") or src.get("academic_year")
    if not to_class_id: raise HTTPException(400, "to_class_id is required")
    to_class = await db.classes.find_one({"id": to_class_id})
    if not to_class: raise HTTPException(400, "Target class not found")
    dup = await db.fee_structures.find_one({"class_id": to_class_id, "academic_year": to_academic_year})
    if dup:
        raise HTTPException(400, f"A structure already exists for that class + academic year")
    new_id = gen_id()
    doc = {
        "id": new_id,
        "department_id": to_class["department_id"],
        "class_id": to_class_id,
        "academic_year": to_academic_year,
        "items": src.get("items", []),
        "total": src.get("total", 0),
        "cloned_from": fid,
        "created_at": now_iso(),
    }
    await db.fee_structures.insert_one(doc)
    await audit(user, "duplicate", "fee_structure", new_id, {"from": fid, "to_class": to_class_id})
    return {k:v for k,v in doc.items() if k != "_id"}

# ---------- Fee-Structure Bulk Import/Delete ----------
@router.post("/fee-structures/bulk-import")
async def bulk_import_fee_structures(body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    """Body: {rows: [{department_code, class_name, academic_year, fee_head_name, amount}], batch_id?}"""
    rows = body.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise HTTPException(400, "rows must be a non-empty array")
    batch_id = body.get("batch_id") or gen_id()
    depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(100)}
    classes = await db.classes.find({}, {"_id":0}).to_list(500)
    groups: Dict[tuple, List[dict]] = {}
    errors: List[dict] = []
    for idx, r in enumerate(rows):
        try:
            dcode = str(r.get("department_code","")).strip().upper()
            cname = str(r.get("class_name","")).strip()
            ay = str(r.get("academic_year","")).strip() or "2026-27"
            head = str(r.get("fee_head_name","")).strip()
            amt = float(r.get("amount") or 0)
            if not dcode or not cname or not head:
                errors.append({"row": idx+1, "error": "department_code, class_name, fee_head_name required", "data": r}); continue
            if amt <= 0:
                errors.append({"row": idx+1, "error": "amount must be > 0", "data": r}); continue
            if dcode not in depts:
                errors.append({"row": idx+1, "error": f"unknown department code {dcode}", "data": r}); continue
            d = depts[dcode]
            cls = next((c for c in classes if c["department_id"]==d["id"] and c["name"].lower()==cname.lower()), None)
            if not cls:
                errors.append({"row": idx+1, "error": f"unknown class '{cname}' in {dcode}", "data": r}); continue
            groups.setdefault((d["id"], cls["id"], ay), []).append({"fee_head_name": head, "amount": amt})
        except Exception as e:
            errors.append({"row": idx+1, "error": str(e), "data": r})
    created, updated, created_ids = 0, 0, []
    for (dept_id, class_id, ay), items in groups.items():
        existing = await db.fee_structures.find_one({"department_id": dept_id, "class_id": class_id, "academic_year": ay})
        total = sum(it["amount"] for it in items)
        if existing:
            existing_items = existing.get("items", [])
            by_name = {it.get("fee_head_name","").strip().lower(): idx for idx, it in enumerate(existing_items)}
            for it in items:
                key = it["fee_head_name"].strip().lower()
                if key in by_name:
                    existing_items[by_name[key]]["amount"] = it["amount"]
                else:
                    existing_items.append({"fee_head_id": None, "fee_head_name": it["fee_head_name"], "amount": it["amount"]})
            new_total = sum(float(x.get("amount",0)) for x in existing_items)
            await db.fee_structures.update_one({"id": existing["id"]}, {"$set": {"items": existing_items, "total": new_total, "last_import_batch_id": batch_id, "last_import_at": now_iso()}})
            updated += 1
        else:
            fid = gen_id()
            doc = {
                "id": fid, "department_id": dept_id, "class_id": class_id, "academic_year": ay,
                "items": [{"fee_head_id": None, **it} for it in items],
                "total": total, "import_batch_id": batch_id,
                "created_at": now_iso(), "created_by": user["name"],
            }
            await db.fee_structures.insert_one(doc)
            created_ids.append(fid); created += 1
    await db.import_batches.insert_one({
        "id": batch_id, "type": "fee_structures", "created": created, "updated": updated,
        "errors_count": len(errors), "total_rows": len(rows), "created_ids": created_ids,
        "user_id": user["id"], "user_name": user["name"], "created_at": now_iso(),
    })
    await audit(user, "bulk_import", "fee_structure", batch_id, {"created": created, "updated": updated, "errors": len(errors)})
    return {"created": created, "skipped": updated, "errors": errors, "total": len(rows), "batch_id": batch_id, "created_ids": created_ids}

@router.post("/fee-structures/bulk-delete")
async def bulk_delete_fee_structures(body: Dict[str, Any], user = Depends(require_roles("administrator","manager"))):
    batch_id = body.get("batch_id")
    if not batch_id:
        raise HTTPException(400, "batch_id required")
    structs = await db.fee_structures.find({"import_batch_id": batch_id}, {"_id":0}).to_list(1000)
    if not structs:
        return {"deleted": 0, "protected_referenced": 0}
    used = await db.students.distinct("fee_structure_id", {"fee_structure_id": {"$in": [s["id"] for s in structs]}})
    protected_ids = set([u for u in used if u])
    deletable = [s["id"] for s in structs if s["id"] not in protected_ids]
    if deletable:
        await db.fee_structures.delete_many({"id": {"$in": deletable}})
    await db.import_batches.update_one({"id": batch_id}, {"$set": {"undone_at": now_iso(), "undone_by": user["name"], "undone_deleted": len(deletable), "undone_protected": len(protected_ids)}})
    await audit(user, "bulk_delete", "fee_structure", batch_id, {"deleted": len(deletable), "protected": len(protected_ids)})
    return {"deleted": len(deletable), "protected_referenced": len(protected_ids)}

# ---------- Imports history ----------
@router.get("/imports/latest")
async def latest_import_batch(kind: Literal["students","fee_structures"], user = Depends(get_current_user)):
    doc = await db.import_batches.find_one({"type": kind, "undone_at": {"$exists": False}}, {"_id":0}, sort=[("created_at", -1)])
    return doc or {}

@router.get("/imports/history")
async def imports_history(
    kind: Optional[Literal["students","fee_structures"]] = None,
    limit: int = 100,
    user = Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if kind: q["type"] = kind
    return await db.import_batches.find(q, {"_id":0}).sort("created_at", -1).limit(limit).to_list(limit)

# ---------- Promotion + Rollover + Seed 2026 ----------
@router.post("/students/promote")
async def promote_students(body: PromoteIn, user = Depends(require_roles("administrator","manager"))):
    from_cls = await db.classes.find_one({"id": body.from_class_id})
    to_cls = await db.classes.find_one({"id": body.to_class_id})
    if not from_cls or not to_cls:
        raise HTTPException(400, "Invalid class")
    q = {"class_id": body.from_class_id, "status": "active"}
    if body.section: q["section"] = body.section
    students = await db.students.find(q, {"_id":0}).to_list(5000)
    upd: Dict[str, Any] = {"class_id": body.to_class_id, "department_id": to_cls["department_id"]}
    if body.to_fee_structure_id:
        upd["fee_structure_id"] = body.to_fee_structure_id
    else:
        upd["fee_structure_id"] = None
    for s in students:
        await db.students.update_one({"id": s["id"]}, {"$set": upd, "$push": {"promotion_history": {"from_class_id": body.from_class_id, "to_class_id": body.to_class_id, "at": now_iso(), "by": user["name"], "academic_year": body.new_academic_year}}})
    await audit(user, "promote", "class", body.to_class_id, {"count": len(students), "from": from_cls["name"], "to": to_cls["name"]})
    return {"promoted": len(students), "from_class": from_cls["name"], "to_class": to_cls["name"]}

@router.post("/fee-structures/rollover")
async def rollover_fee_structures(body: RolloverIn, user = Depends(require_roles("administrator","manager"))):
    existing = await db.fee_structures.find({"academic_year": body.from_academic_year}, {"_id":0}).to_list(500)
    created = 0
    for fs in existing:
        dup = await db.fee_structures.find_one({"academic_year": body.to_academic_year, "department_id": fs["department_id"], "class_id": fs["class_id"]})
        if dup: continue
        new_fs = {
            "id": gen_id(),
            "department_id": fs["department_id"], "class_id": fs["class_id"],
            "academic_year": body.to_academic_year,
            "items": fs.get("items", []), "total": fs.get("total", 0),
            "cloned_from": fs["id"], "created_at": now_iso(),
        }
        await db.fee_structures.insert_one(new_fs); created += 1
    await db.departments.update_many({"academic_year": body.from_academic_year}, {"$set": {"academic_year": body.to_academic_year}})
    await audit(user, "rollover", "fee_structure", "", {"from": body.from_academic_year, "to": body.to_academic_year, "created": created})
    return {"created": created, "from": body.from_academic_year, "to": body.to_academic_year}

@router.post("/fee-structures/seed-2026")
async def seed_2026_fee_structures(user = Depends(require_roles("administrator","manager"))):
    rows: List[dict] = []
    try:
        with open("/app/memory/fee_structure_2026.json", "r") as f:
            rows = _json.load(f)
    except Exception as e:
        raise HTTPException(500, f"Cannot read seed file: {e}")
    fee_head_names = ["Admission Fee", "Continuation Fee", "Tuition Q1", "Tuition Q2", "Tuition Q3", "Term Fees", "Tuition Fee", "Practical Fee"]
    fh_by_name: Dict[str, dict] = {fh["name"]: fh for fh in await db.fee_heads.find({}, {"_id":0}).to_list(200)}
    for nm in fee_head_names:
        if nm not in fh_by_name:
            code = nm.replace(" ","_").upper()[:8]
            fh = {"id": gen_id(), "name": nm, "code": code, "category": "school", "created_at": now_iso()}
            await db.fee_heads.insert_one(fh); fh_by_name[nm] = fh
    depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(50)}
    def pick_dept(class_name: str, medium: str):
        cn = class_name.lower()
        if medium == "Junior College": return depts.get("JC")
        if "9th" in cn or "10th" in cn: return depts.get("SEC")
        if medium == "English": return depts.get("EP")
        if medium in ("Semi-English", "Semi English", "Marathi (Semi)"): return depts.get("MP")
        return depts.get("EP")
    ay = "2026-27"
    created_classes = 0; created_structures = 0; skipped = 0
    for row in rows:
        cname = row["class_name"]; medium = row.get("medium", "English"); fees = row.get("fees", {})
        d = pick_dept(cname, medium)
        if not d: continue
        cls = await db.classes.find_one({"department_id": d["id"], "name": cname, "medium": medium}, {"_id":0})
        if not cls:
            cls = {"id": gen_id(), "department_id": d["id"], "name": cname, "medium": medium, "created_at": now_iso()}
            await db.classes.insert_one(cls); created_classes += 1
        existing_fs = await db.fee_structures.find_one({"class_id": cls["id"], "academic_year": ay})
        if existing_fs:
            skipped += 1; continue
        items = []; total = 0
        for k, v in fees.items():
            if not isinstance(v, (int, float)) or v <= 0: continue
            if k in ("Total", "Total Fees"): continue
            fh = fh_by_name.get(k) or fh_by_name.get(k.replace(" ", ""))
            if not fh:
                fh = {"id": gen_id(), "name": k, "code": k.replace(" ","_").upper()[:8], "category":"school", "created_at": now_iso()}
                await db.fee_heads.insert_one(fh); fh_by_name[k] = fh
            items.append({"fee_head_id": fh["id"], "fee_head_name": k, "amount": float(v),
                          "installment": ("Q1" if "Q1" in k else "Q2" if "Q2" in k else "Q3" if "Q3" in k else None)})
            total += float(v)
        await db.fee_structures.insert_one({
            "id": gen_id(),
            "department_id": d["id"], "class_id": cls["id"],
            "academic_year": ay, "items": items, "total": total,
            "seeded_from": "fee_structure_2026.json", "created_at": now_iso(),
        })
        created_structures += 1
    await audit(user, "seed", "fee_structure", "", {"classes": created_classes, "structures": created_structures, "skipped": skipped})
    return {"classes_created": created_classes, "structures_created": created_structures, "skipped": skipped, "total_rows": len(rows)}
