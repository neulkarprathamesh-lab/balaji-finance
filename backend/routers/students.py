"""Students CRUD, ledger, siblings, bulk import/delete/reassign."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from core import (
    db, StudentIn, audit, gen_id, get_current_user, now_iso, require_roles,
)

router = APIRouter(prefix="/api", tags=["students"])

@router.get("/students")
async def list_students(
    q: Optional[str] = None,
    department_id: Optional[str] = None,
    class_id: Optional[str] = None,
    limit: int = 100,
    user = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if department_id: query["department_id"] = department_id
    if class_id: query["class_id"] = class_id
    if q:
        query["$or"] = [
            {"admission_no": {"$regex": q, "$options": "i"}},
            {"name": {"$regex": q, "$options": "i"}},
            {"guardian_mobile": {"$regex": q, "$options": "i"}},
        ]
    return await db.students.find(query, {"_id":0}).limit(limit).to_list(limit)

@router.get("/students/{sid}")
async def get_student(sid: str, user = Depends(get_current_user)):
    s = await db.students.find_one({"id": sid}, {"_id":0})
    if not s: raise HTTPException(404, "Student not found")
    return s

@router.get("/students/{sid}/ledger")
async def student_ledger(sid: str, user = Depends(get_current_user)):
    s = await db.students.find_one({"id": sid}, {"_id":0})
    if not s: raise HTTPException(404, "Not found")
    receipts = await db.receipts.find({"student_id": sid, "status":{"$ne":"cancelled"}}, {"_id":0}).sort("created_at", -1).to_list(500)
    adjustments = await db.adjustments.find({"student_id": sid, "status":"approved"}, {"_id":0}).to_list(200)
    fs = None
    if s.get("fee_structure_id"):
        fs = await db.fee_structures.find_one({"id": s["fee_structure_id"]}, {"_id":0})
    total_paid = sum(r.get("total", 0) for r in receipts if r.get("receipt_type") not in ("refund","debit_voucher"))
    total_refunded = sum(r.get("total", 0) for r in receipts if r.get("receipt_type") == "refund")
    total_adjusted = sum(a.get("amount", 0) for a in adjustments)
    payable = (fs.get("total") if fs else 0) - total_paid - total_adjusted + total_refunded
    return {
        "student": s, "fee_structure": fs, "receipts": receipts, "adjustments": adjustments,
        "total_paid": total_paid, "total_refunded": total_refunded,
        "total_adjusted": total_adjusted, "outstanding": max(0, payable),
    }

@router.post("/students")
async def create_student(body: StudentIn, user = Depends(require_roles("administrator","manager","accountant","cashier"))):
    existing = await db.students.find_one({"admission_no": body.admission_no})
    if existing:
        raise HTTPException(400, "Admission number already exists")
    sid = gen_id()
    doc = {"id": sid, **body.model_dump(), "status":"active", "created_at": now_iso()}
    await db.students.insert_one(doc)
    await audit(user, "create", "student", sid, {"admission_no": body.admission_no})
    return {k:v for k,v in doc.items() if k != "_id"}

@router.post("/students/bulk-import")
async def bulk_import_students(body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    rows = body.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise HTTPException(400, "rows must be a non-empty array")
    batch_id = body.get("batch_id") or gen_id()
    depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(100)}
    classes = await db.classes.find({}, {"_id":0}).to_list(500)
    created, skipped, errors = 0, 0, []
    for idx, r in enumerate(rows):
        try:
            adm = str(r.get("admission_no","")).strip()
            name = str(r.get("name","")).strip()
            dcode = str(r.get("department_code","")).strip().upper()
            cname = str(r.get("class_name","")).strip()
            if not adm or not name or not dcode or not cname:
                errors.append({"row": idx+1, "error": "admission_no, name, department_code, class_name required"}); continue
            if await db.students.find_one({"admission_no": adm}):
                skipped += 1; continue
            d = depts.get(dcode)
            if not d:
                errors.append({"row": idx+1, "error": f"unknown department code {dcode}"}); continue
            cls = next((c for c in classes if c["department_id"]==d["id"] and c["name"].lower()==cname.lower()), None)
            if not cls:
                errors.append({"row": idx+1, "error": f"unknown class {cname} in {dcode}"}); continue
            await db.students.insert_one({
                "id": gen_id(), "admission_no": adm, "name": name,
                "department_id": d["id"], "class_id": cls["id"],
                "guardian_name": r.get("guardian_name"), "guardian_mobile": str(r.get("guardian_mobile","") or ""),
                "address": r.get("address"), "status":"active", "created_at": now_iso(),
                "imported_at": now_iso(), "imported_by": user["id"], "import_batch_id": batch_id,
            })
            created += 1
        except Exception as e:
            errors.append({"row": idx+1, "error": str(e)})
    await db.import_batches.insert_one({
        "id": batch_id, "type": "students", "created": created, "skipped": skipped,
        "errors_count": len(errors), "total": len(rows),
        "user_id": user["id"], "user_name": user["name"], "created_at": now_iso(),
    })
    await audit(user, "bulk_import", "student", batch_id, {"created": created, "skipped": skipped, "errors": len(errors)})
    return {"created": created, "skipped": skipped, "errors": errors, "total": len(rows), "batch_id": batch_id}

@router.post("/students/bulk-delete")
async def bulk_delete_students(body: Dict[str, Any], user = Depends(require_roles("administrator","manager"))):
    batch_id = body.get("batch_id")
    ids = body.get("student_ids") or []
    q: Dict[str, Any] = {}
    if batch_id:
        q["import_batch_id"] = batch_id
    elif ids:
        q["id"] = {"$in": ids}
    else:
        raise HTTPException(400, "Provide batch_id or student_ids")
    stus = await db.students.find(q, {"_id": 0}).to_list(5000)
    if not stus:
        return {"deleted": 0, "protected_with_receipts": 0}
    with_receipts = await db.receipts.distinct("student_id", {"student_id": {"$in": [s["id"] for s in stus]}})
    protected_ids = set(with_receipts)
    deletable = [s["id"] for s in stus if s["id"] not in protected_ids]
    if deletable:
        await db.students.delete_many({"id": {"$in": deletable}})
    if batch_id:
        await db.import_batches.update_one({"id": batch_id}, {"$set": {"undone_at": now_iso(), "undone_by": user["name"], "undone_deleted": len(deletable), "undone_protected": len(protected_ids)}})
    await audit(user, "bulk_delete", "student", batch_id or "", {"deleted": len(deletable), "protected": len(protected_ids)})
    return {"deleted": len(deletable), "protected_with_receipts": len(protected_ids), "batch_id": batch_id}

@router.get("/students/{sid}/siblings")
async def student_siblings(sid: str, user = Depends(get_current_user)):
    s = await db.students.find_one({"id": sid}, {"_id":0})
    if not s: raise HTTPException(404, "Not found")
    gm = (s.get("guardian_mobile") or "").strip()
    if not gm: return {"siblings": []}
    others = await db.students.find(
        {"guardian_mobile": gm, "status": "active", "id": {"$ne": sid}},
        {"_id":0}
    ).to_list(20)
    return {"siblings": others}

@router.post("/students/bulk-reassign")
async def bulk_reassign_students(body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    ids = body.get("student_ids", [])
    to_class_id = body.get("to_class_id")
    if not ids or not to_class_id:
        raise HTTPException(400, "student_ids and to_class_id required")
    to_cls = await db.classes.find_one({"id": to_class_id})
    if not to_cls: raise HTTPException(400, "Target class not found")
    upd: Dict[str, Any] = {"class_id": to_class_id, "department_id": to_cls["department_id"]}
    if body.get("to_fee_structure_id"): upd["fee_structure_id"] = body["to_fee_structure_id"]
    result = await db.students.update_many({"id": {"$in": ids}}, {"$set": upd, "$push": {"reassign_history": {"to_class_id": to_class_id, "at": now_iso(), "by": user["name"]}}})
    await audit(user, "bulk_reassign", "student", "", {"count": result.modified_count, "to_class_id": to_class_id})
    return {"reassigned": result.modified_count}

@router.patch("/students/{sid}")
async def update_student(sid: str, body: Dict[str,Any], user = Depends(require_roles("administrator","manager","accountant"))):
    upd = {k:v for k,v in body.items() if k in ("name","class_id","section","guardian_name","guardian_mobile","address","fee_structure_id","bus_route","status")}
    await db.students.update_one({"id": sid}, {"$set": upd})
    await audit(user, "update", "student", sid, upd)
    return {"ok": True}
