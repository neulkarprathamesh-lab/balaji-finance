"""Receipt Types (DB-backed) + Receipts + Adjustments + Extensions + Reminders + cancel/reprint."""
from typing import Any, Dict, List, Optional, Literal
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from core import (
    db, ReceiptTypeIn, ReceiptIn, AdjustmentIn, ExtensionIn, ReminderFollowupIn,
    audit, gen_id, get_current_user, now_iso, require_roles,
    require_admin_pin, require_admin_dual, get_settings_doc,
    next_receipt_number, next_voucher_number, amount_in_words_inr,
    DEFAULT_RECEIPT_TYPES, _seed_receipt_types_if_empty,
)

router = APIRouter(prefix="/api", tags=["receipts"])

# ---------- Receipt Types ----------
@router.get("/receipt-types")
async def list_receipt_types(
    category: Optional[Literal["school","bus","finance","misc"]] = None,
    include_disabled: bool = False,
    include_archived: bool = False,
    user = Depends(get_current_user),
):
    await _seed_receipt_types_if_empty()
    q: Dict[str, Any] = {}
    if not include_archived: q["archived"] = {"$ne": True}
    if not include_disabled: q["enabled"] = True
    if category: q["category"] = category
    return await db.receipt_types.find(q, {"_id":0}).sort("display_order", 1).to_list(200)

@router.get("/receipt-types/{rtid}")
async def get_receipt_type(rtid: str, user = Depends(get_current_user)):
    doc = await db.receipt_types.find_one({"id": rtid}, {"_id":0})
    if not doc: raise HTTPException(404, "Not found")
    return doc

@router.post("/receipt-types")
async def create_receipt_type(body: ReceiptTypeIn, user = Depends(require_admin_pin)):
    if await db.receipt_types.find_one({"code": body.code.upper()}):
        raise HTTPException(400, f"Receipt type with prefix {body.code} already exists")
    rid = gen_id()
    doc = {"id": rid, **body.model_dump(), "code": body.code.upper(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.receipt_types.insert_one(doc)
    await audit(user, "create", "receipt_type", rid, {"code": doc["code"], "name": doc["name"]})
    return {k:v for k,v in doc.items() if k != "_id"}

@router.patch("/receipt-types/{rtid}")
async def update_receipt_type(rtid: str, body: Dict[str, Any], user = Depends(require_admin_pin)):
    existing = await db.receipt_types.find_one({"id": rtid})
    if not existing: raise HTTPException(404, "Not found")
    allowed = {"name","department_name","department_id","category","description","icon","display_order","enabled","tabs","default_payment_modes","print_template","report_category","notes","archived",
               "paper_size","orientation","header_text","footer_text","watermark_text","watermark_enabled","barcode_enabled","qr_enabled","signature_area_enabled","computer_generated_note",
               "starting_number","current_number","auto_reset_yearly","fields"}
    upd = {k: v for k, v in body.items() if k in allowed}
    if "code" in body and body["code"]:
        new_code = str(body["code"]).upper()
        if new_code != existing.get("code"):
            if await db.receipt_types.find_one({"code": new_code, "id": {"$ne": rtid}}):
                raise HTTPException(400, f"Another receipt type already uses prefix {new_code}")
            upd["code"] = new_code
    if not upd:
        raise HTTPException(400, "Nothing to update")
    upd["updated_at"] = now_iso()
    await db.receipt_types.update_one({"id": rtid}, {"$set": upd})
    await audit(user, "update", "receipt_type", rtid, {"before": {k: existing.get(k) for k in upd.keys()}, "after": upd})
    doc = await db.receipt_types.find_one({"id": rtid}, {"_id":0})
    return doc

@router.delete("/receipt-types/{rtid}")
async def delete_receipt_type(rtid: str, user = Depends(require_admin_pin)):
    doc = await db.receipt_types.find_one({"id": rtid})
    if not doc: raise HTTPException(404, "Not found")
    used = await db.receipts.count_documents({"receipt_type_id": rtid})
    if used > 0:
        raise HTTPException(409, {"message": f"This receipt type has {used} existing transactions. Disable or archive it instead.", "used_count": used, "can_archive": True})
    await db.receipt_types.delete_one({"id": rtid})
    await audit(user, "delete", "receipt_type", rtid, {"code": doc.get("code"), "name": doc.get("name")})
    return {"deleted": True}

@router.post("/receipt-types/{rtid}/archive")
async def archive_receipt_type(rtid: str, user = Depends(require_admin_pin)):
    doc = await db.receipt_types.find_one({"id": rtid})
    if not doc: raise HTTPException(404, "Not found")
    await db.receipt_types.update_one({"id": rtid}, {"$set": {"archived": True, "enabled": False, "updated_at": now_iso()}})
    await audit(user, "archive", "receipt_type", rtid, {"code": doc.get("code")})
    return {"archived": True}

@router.post("/receipt-types/{rtid}/reset-sequence")
async def reset_receipt_type_sequence(rtid: str, body: Dict[str, Any], user = Depends(require_admin_dual)):
    """Manual Sequence Reset — DUAL-AUTH required (PIN + password)."""
    doc = await db.receipt_types.find_one({"id": rtid})
    if not doc: raise HTTPException(404, "Not found")
    try: new_number = int(body.get("new_number", 0))
    except Exception: raise HTTPException(400, "new_number must be an integer")
    reason = str(body.get("reason","")).strip()
    if new_number < 1: raise HTTPException(400, "new_number must be >= 1")
    if len(reason) < 5: raise HTTPException(400, "Reason must be at least 5 characters")
    prefix = doc["code"]
    academic_year = body.get("academic_year") or "2026-27"
    year4 = academic_year.split("-")[0]
    conflict = await db.receipts.find_one(
        {"number": {"$regex": f"^{prefix}-{year4}-\\d{{6}}$"}},
        sort=[("number", -1)]
    )
    highest_seq = 0
    if conflict:
        try: highest_seq = int(conflict["number"].rsplit("-", 1)[-1])
        except Exception: highest_seq = 0
    if new_number <= highest_seq:
        raise HTTPException(409, f"Would create duplicate numbers — highest existing receipt is #{highest_seq:06d}. new_number must be > {highest_seq}.")
    counter_key = f"RT-{prefix}-{academic_year}"
    prev = await db.counters.find_one({"key": counter_key}) or {"seq": 0}
    prev_seq = prev.get("seq", 0)
    await db.counters.update_one({"key": counter_key}, {"$set": {"seq": new_number - 1}}, upsert=True)
    await db.receipt_types.update_one({"id": rtid}, {"$set": {"current_number": new_number - 1, "updated_at": now_iso()}})
    await audit(user, "sequence_reset", "receipt_type", rtid, {
        "code": prefix, "academic_year": academic_year,
        "previous_seq": prev_seq, "new_next_number": new_number, "highest_existing": highest_seq,
        "reason": reason,
    })
    return {"ok": True, "prefix": prefix, "previous_seq": prev_seq, "next_will_be": f"{prefix}-{year4}-{new_number:06d}", "reason": reason}

@router.post("/receipt-types/reseed-defaults")
async def reseed_receipt_types(user = Depends(require_admin_pin)):
    """Idempotent — only adds any DEFAULT_RECEIPT_TYPES rows whose prefix is missing."""
    depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(50)}
    now = now_iso(); added = []
    for t in DEFAULT_RECEIPT_TYPES:
        if await db.receipt_types.find_one({"code": t["code"]}):
            continue
        dept = depts.get(t["code"])
        await db.receipt_types.insert_one({
            "id": gen_id(), **t,
            "department_id": dept["id"] if dept else None,
            "enabled": True, "archived": False,
            "default_payment_modes": ["cash","upi","card"],
            "print_template": "a4-navy", "report_category": t["category"],
            "created_at": now, "updated_at": now,
        })
        added.append(t["code"])
    await audit(user, "reseed", "receipt_type", "", {"added": added})
    return {"added": added, "count": len(added)}

# ---------- Receipts ----------
@router.post("/receipts")
async def create_receipt(body: ReceiptIn, user = Depends(require_roles("administrator","manager","accountant","cashier"))):
    dept = await db.departments.find_one({"id": body.department_id})
    if not dept: raise HTTPException(400, "Invalid department")
    student = None
    if body.student_id:
        student = await db.students.find_one({"id": body.student_id})
        if not student: raise HTTPException(400, "Invalid student")
    total = sum(l.amount for l in body.lines)
    if body.receipt_type in ("refund","debit_voucher"):
        if user["role"] not in ("administrator","manager"):
            raise HTTPException(403, "Refund/voucher requires manager or admin")
    ay = dept.get("academic_year", "2026-27")
    if body.receipt_type == "debit_voucher":
        number = await next_voucher_number(ay)
    else:
        number = await next_receipt_number(dept["code"], ay)
    rid = gen_id()
    doc = {
        "id": rid, "number": number, "receipt_type": body.receipt_type,
        "department_id": body.department_id, "department_name": dept["name"], "department_code": dept["code"],
        "department_header1": dept.get("header_line1"), "department_header2": dept.get("header_line2"),
        "student_id": body.student_id,
        "student_snapshot": {"admission_no": student["admission_no"], "name": student["name"], "class_id": student.get("class_id")} if student else None,
        "payer_name": body.payer_name or (student["name"] if student else None),
        "purpose": body.purpose, "payment_mode": body.payment_mode, "payment_reference": body.payment_reference,
        "lines": [l.model_dump() for l in body.lines], "total": total,
        "amount_in_words": amount_in_words_inr(total),
        "remarks": body.remarks, "linked_receipt_id": body.linked_receipt_id,
        "metadata": body.metadata or {},
        "academic_year": ay, "cashier_id": user["id"], "cashier_name": user["name"],
        "status": "issued", "reprint_count": 0,
        "created_at": now_iso(),
    }
    await db.receipts.insert_one(doc)
    await audit(user, "create", "receipt", rid, {"number": number, "total": total, "type": body.receipt_type})
    return {k:v for k,v in doc.items() if k != "_id"}

@router.get("/receipts")
async def list_receipts(
    q: Optional[str] = None, department_id: Optional[str] = None,
    receipt_type: Optional[str] = None, student_id: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    cashier_id: Optional[str] = None, limit: int = 200,
    user = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if department_id: query["department_id"] = department_id
    if receipt_type: query["receipt_type"] = receipt_type
    if student_id: query["student_id"] = student_id
    if cashier_id: query["cashier_id"] = cashier_id
    if q: query["number"] = {"$regex": q, "$options": "i"}
    if date_from or date_to:
        rng = {}
        if date_from: rng["$gte"] = date_from
        if date_to: rng["$lte"] = date_to + "T23:59:59"
        query["created_at"] = rng
    return await db.receipts.find(query, {"_id":0}).sort("created_at", -1).limit(limit).to_list(limit)

@router.get("/receipts/{rid}")
async def get_receipt(rid: str, user = Depends(get_current_user)):
    r = await db.receipts.find_one({"id": rid}, {"_id":0})
    if not r: raise HTTPException(404, "Not found")
    return r

@router.post("/receipts/{rid}/reprint")
async def reprint_receipt(rid: str, user = Depends(get_current_user)):
    r = await db.receipts.find_one({"id": rid})
    if not r: raise HTTPException(404, "Not found")
    await db.receipts.update_one({"id": rid}, {"$inc": {"reprint_count": 1}, "$set":{"last_reprint_at": now_iso(), "last_reprint_by": user["name"]}})
    await audit(user, "reprint", "receipt", rid, {"number": r["number"]})
    return {"ok": True}

@router.post("/receipts/{rid}/cancel")
async def cancel_receipt(rid: str, body: Dict[str, str], user = Depends(require_roles("administrator","manager"))):
    reason = body.get("reason","").strip()
    if not reason: raise HTTPException(400, "Reason required")
    r = await db.receipts.find_one({"id": rid})
    if not r: raise HTTPException(404, "Not found")
    await db.receipts.update_one({"id": rid}, {"$set":{"status":"cancelled","cancel_reason": reason,"cancelled_at": now_iso(),"cancelled_by": user["name"]}})
    await audit(user, "cancel", "receipt", rid, {"reason": reason})
    return {"ok": True}

# ---------- Adjustments ----------
@router.post("/adjustments")
async def create_adjustment(body: AdjustmentIn, user = Depends(require_roles("administrator","manager","accountant","cashier"))):
    aid = gen_id()
    doc = {"id": aid, **body.model_dump(), "status":"pending", "requested_by": user["id"], "requested_by_name": user["name"], "created_at": now_iso()}
    await db.adjustments.insert_one(doc)
    await audit(user, "create", "adjustment", aid, {"amount": body.amount, "type": body.adjustment_type})
    return {k:v for k,v in doc.items() if k != "_id"}

@router.get("/adjustments")
async def list_adjustments(status: Optional[str] = None, user = Depends(get_current_user)):
    q = {"status": status} if status else {}
    return await db.adjustments.find(q, {"_id":0}).sort("created_at", -1).to_list(500)

@router.post("/adjustments/{aid}/approve")
async def approve_adjustment(aid: str, user = Depends(require_roles("administrator","manager"))):
    adj = await db.adjustments.find_one({"id": aid})
    if not adj: raise HTTPException(404, "Not found")
    settings = await get_settings_doc()
    cap = float(settings.get("manager_waiver_cap", 5000) or 5000)
    if user["role"] == "manager" and float(adj.get("amount", 0)) > cap:
        raise HTTPException(403, f"Adjustments over ₹{int(cap):,} require administrator approval")
    await db.adjustments.update_one({"id": aid}, {"$set":{"status":"approved","approved_by": user["id"],"approved_by_name": user["name"],"approved_at": now_iso()}})
    await audit(user, "approve", "adjustment", aid, {"amount": adj.get("amount")})
    return {"ok": True}

@router.post("/adjustments/{aid}/reject")
async def reject_adjustment(aid: str, body: Dict[str,str], user = Depends(require_roles("administrator","manager"))):
    await db.adjustments.update_one({"id": aid}, {"$set":{"status":"rejected","reject_reason": body.get("reason",""),"approved_by_name": user["name"],"approved_at": now_iso()}})
    await audit(user, "reject", "adjustment", aid)
    return {"ok": True}

# ---------- Extensions ----------
@router.post("/extensions")
async def create_extension(body: ExtensionIn, user = Depends(require_roles("administrator","manager","accountant","cashier"))):
    if len(body.installments) > 4:
        raise HTTPException(400, "Max 4 installments allowed")
    total = sum(float(i.get("amount",0)) for i in body.installments)
    if abs(total - body.outstanding_amount) > 0.01:
        raise HTTPException(400, f"Installments total (₹{total}) must equal outstanding (₹{body.outstanding_amount})")
    eid = gen_id()
    doc = {"id": eid, **body.model_dump(), "status":"pending", "requested_by": user["id"], "requested_by_name": user["name"], "created_at": now_iso()}
    await db.extensions.insert_one(doc)
    await audit(user, "create", "extension", eid, {"amount": total})
    return {k:v for k,v in doc.items() if k != "_id"}

@router.get("/extensions")
async def list_extensions(status: Optional[str] = None, student_id: Optional[str] = None, user = Depends(get_current_user)):
    q = {}
    if status: q["status"] = status
    if student_id: q["student_id"] = student_id
    return await db.extensions.find(q, {"_id":0}).sort("created_at", -1).to_list(500)

@router.post("/extensions/{eid}/approve")
async def approve_extension(eid: str, user = Depends(require_roles("administrator","manager"))):
    ext = await db.extensions.find_one({"id": eid})
    if not ext: raise HTTPException(404, "Not found")
    await db.extensions.update_one({"id": eid}, {"$set":{"status":"approved","approved_by_name": user["name"],"approved_at": now_iso()}})
    for idx, inst in enumerate(ext.get("installments", [])):
        await db.reminders.insert_one({
            "id": gen_id(), "extension_id": eid, "student_id": ext["student_id"],
            "installment_index": idx, "installment_name": inst.get("name") or f"Installment {idx+1}",
            "amount": float(inst.get("amount",0)), "due_date": inst.get("due_date"),
            "status": "pending", "created_at": now_iso(),
        })
    await audit(user, "approve", "extension", eid)
    return {"ok": True}

@router.post("/extensions/{eid}/reject")
async def reject_extension(eid: str, body: Dict[str,str], user = Depends(require_roles("administrator","manager"))):
    await db.extensions.update_one({"id": eid}, {"$set":{"status":"rejected","reject_reason": body.get("reason",""),"approved_by_name": user["name"],"approved_at": now_iso()}})
    await audit(user, "reject", "extension", eid)
    return {"ok": True}

# ---------- Reminders ----------
@router.get("/reminders")
async def list_reminders(status: str = "pending", user = Depends(get_current_user)):
    reminders = await db.reminders.find({"status": status}, {"_id":0}).to_list(1000)
    sids = list({r["student_id"] for r in reminders})
    students = {s["id"]: s for s in await db.students.find({"id":{"$in": sids}}, {"_id":0}).to_list(len(sids) or 1)}
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    for r in reminders:
        r["student"] = students.get(r["student_id"])
        due = (r.get("due_date") or "")[:10]
        if due < today: r["bucket"] = "overdue"
        elif due == today: r["bucket"] = "today"
        elif due == tomorrow: r["bucket"] = "tomorrow"
        else: r["bucket"] = "future"
    return reminders

@router.post("/reminders/followup")
async def add_followup(body: ReminderFollowupIn, user = Depends(get_current_user)):
    r = await db.reminders.find_one({"id": body.reminder_id})
    if not r: raise HTTPException(404, "Not found")
    followup = {"id": gen_id(), "remark_type": body.remark_type, "details": body.details, "by": user["name"], "at": now_iso()}
    await db.reminders.update_one({"id": body.reminder_id}, {"$push":{"followups": followup}, "$set":{"last_followup_at": now_iso()}})
    if body.remark_type == "payment_received":
        await db.reminders.update_one({"id": body.reminder_id}, {"$set":{"status":"paid"}})
    await audit(user, "followup", "reminder", body.reminder_id, {"type": body.remark_type})
    return {"ok": True}
