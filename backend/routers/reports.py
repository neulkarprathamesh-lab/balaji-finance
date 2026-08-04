"""Dashboard, reports (collection, audit, cancellations, concessions, defaulters, day-end),
bus routes, outstanding notices, quarterly reminders trigger, public lookups (no-auth)."""
import os, hmac, asyncio
from datetime import datetime, timezone, date, timedelta
from typing import Any, Dict, List, Optional, Literal
from fastapi import APIRouter, HTTPException, Depends, Request
from core import (
    db, BusRouteIn, audit, gen_id, get_current_user, get_settings_doc,
    now_iso, require_roles, _generate_quarterly_reminders,
)

router = APIRouter(prefix="/api", tags=["reports"])

# ---------- Dashboard ----------
@router.get("/dashboard")
async def dashboard(user = Depends(get_current_user)):
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    receipts_today = await db.receipts.find({"created_at":{"$gte": today}, "status":{"$ne":"cancelled"}}, {"_id":0}).to_list(2000)
    collection_today = sum(r.get("total",0) for r in receipts_today if r.get("receipt_type") not in ("refund","debit_voucher"))
    pending_adj = await db.adjustments.count_documents({"status":"pending"})
    pending_ext = await db.extensions.count_documents({"status":"pending"})
    reminders = await db.reminders.find({"status":"pending"}, {"_id":0}).to_list(2000)
    due_today = sum(1 for r in reminders if (r.get("due_date") or "")[:10] == today)
    due_tomorrow = sum(1 for r in reminders if (r.get("due_date") or "")[:10] == tomorrow)
    overdue = sum(1 for r in reminders if (r.get("due_date") or "")[:10] < today)
    recent = await db.receipts.find({}, {"_id":0}).sort("created_at",-1).limit(10).to_list(10)
    dept_totals: Dict[str,float] = {}
    for r in receipts_today:
        if r.get("receipt_type") in ("refund","debit_voucher"): continue
        dept_totals[r.get("department_name","-")] = dept_totals.get(r.get("department_name","-"),0) + r.get("total",0)
    return {
        "collection_today": collection_today,
        "receipts_today_count": len([x for x in receipts_today if x.get("receipt_type") not in ("refund","debit_voucher")]),
        "pending_approvals": pending_adj + pending_ext,
        "pending_adjustments": pending_adj, "pending_extensions": pending_ext,
        "pending_big_waivers": await db.adjustments.count_documents({"status":"pending","amount":{"$gt": float((await get_settings_doc()).get("manager_waiver_cap", 5000) or 5000)}}),
        "due_today": due_today, "due_tomorrow": due_tomorrow, "overdue": overdue,
        "recent_receipts": recent,
        "dept_totals_today": [{"department": k, "total": v} for k,v in dept_totals.items()],
    }

# ---------- Reports ----------
@router.get("/reports/collection")
async def collection_report(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    department_id: Optional[str] = None, cashier_id: Optional[str] = None,
    user = Depends(get_current_user),
):
    today = date.today().isoformat()
    if not date_from: date_from = today
    if not date_to: date_to = today
    q: Dict[str, Any] = {"created_at":{"$gte": date_from, "$lte": date_to + "T23:59:59"}, "status":{"$ne":"cancelled"}}
    if department_id: q["department_id"] = department_id
    if cashier_id: q["cashier_id"] = cashier_id
    rows = await db.receipts.find(q, {"_id":0}).sort("created_at",1).to_list(5000)
    total = sum(r.get("total",0) for r in rows if r.get("receipt_type") not in ("refund","debit_voucher"))
    refund = sum(r.get("total",0) for r in rows if r.get("receipt_type") == "refund")
    vouchers = sum(r.get("total",0) for r in rows if r.get("receipt_type") == "debit_voucher")
    by_mode: Dict[str,float] = {}; by_type: Dict[str,float] = {}
    for r in rows:
        if r.get("receipt_type") in ("refund","debit_voucher"): continue
        by_mode[r.get("payment_mode","-")] = by_mode.get(r.get("payment_mode","-"),0) + r.get("total",0)
        by_type[r.get("receipt_type","-")] = by_type.get(r.get("receipt_type","-"),0) + r.get("total",0)
    return {"rows": rows, "gross_collection": total, "refunds": refund, "vouchers": vouchers,
            "net": total - refund - vouchers, "by_mode": by_mode, "by_type": by_type, "count": len(rows)}

@router.get("/reports/audit")
async def audit_report(limit: int = 500, user = Depends(require_roles("administrator","manager","accountant"))):
    return await db.audit_log.find({}, {"_id":0}).sort("timestamp",-1).limit(limit).to_list(limit)

@router.get("/reports/cancellations")
async def cancellation_report(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user = Depends(require_roles("administrator","manager","accountant")),
):
    today = date.today().isoformat()
    if not date_from: date_from = "2000-01-01"
    if not date_to: date_to = today
    q = {"status": "cancelled", "cancelled_at": {"$gte": date_from, "$lte": date_to + "T23:59:59"}}
    rows = await db.receipts.find(q, {"_id":0}).sort("cancelled_at", -1).to_list(2000)
    total = sum(r.get("total",0) for r in rows)
    return {"rows": rows, "count": len(rows), "total_cancelled": total}

@router.get("/reports/concessions")
async def concession_ledger(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    department_id: Optional[str] = None,
    user = Depends(require_roles("administrator","manager","accountant")),
):
    today = date.today().isoformat()
    if not date_from: date_from = today[:7] + "-01"
    if not date_to: date_to = today
    q: Dict[str, Any] = {"status": "approved", "approved_at": {"$gte": date_from, "$lte": date_to + "T23:59:59"}}
    rows = await db.adjustments.find(q, {"_id":0}).sort("approved_at", -1).to_list(5000)
    sids = list({r["student_id"] for r in rows if r.get("student_id")})
    students = {s["id"]: s for s in await db.students.find({"id":{"$in": sids}}, {"_id":0}).to_list(len(sids) or 1)}
    if department_id:
        rows = [r for r in rows if students.get(r.get("student_id"), {}).get("department_id") == department_id]
    for r in rows:
        r["student"] = students.get(r.get("student_id"))
    total = sum(r.get("amount", 0) for r in rows)
    by_type: Dict[str, float] = {}; by_month: Dict[str, float] = {}
    for r in rows:
        t = r.get("adjustment_type","-")
        by_type[t] = by_type.get(t, 0) + r.get("amount", 0)
        m = (r.get("approved_at") or "")[:7]
        by_month[m] = by_month.get(m, 0) + r.get("amount", 0)
    return {"rows": rows, "count": len(rows), "total": total, "by_type": by_type, "by_month": by_month}

@router.get("/reports/defaulters")
async def defaulters_report(
    quarter: Literal["Q1","Q2","Q3","total"] = "total",
    department_id: Optional[str] = None,
    class_id: Optional[str] = None,
    user = Depends(get_current_user),
):
    q: Dict[str, Any] = {"status": "active", "fee_structure_id": {"$ne": None}}
    if department_id: q["department_id"] = department_id
    if class_id: q["class_id"] = class_id
    students = await db.students.find(q, {"_id": 0}).to_list(5000)
    if not students:
        return {"count": 0, "total_outstanding": 0, "students": [], "quarter": quarter}
    dept_map = {d["id"]: d for d in await db.departments.find({}, {"_id":0}).to_list(50)}
    class_map = {c["id"]: c for c in await db.classes.find({}, {"_id":0}).to_list(500)}
    fs_ids = list({s.get("fee_structure_id") for s in students if s.get("fee_structure_id")})
    fs_map = {f["id"]: f for f in await db.fee_structures.find({"id": {"$in": fs_ids}}, {"_id":0}).to_list(500)}
    sids = [s["id"] for s in students]
    receipts = await db.receipts.find({"student_id": {"$in": sids}, "status": {"$ne":"cancelled"}, "receipt_type": {"$in":["school","admission"]}}, {"_id":0}).to_list(20000)
    paid_q: Dict[str, Dict[str, float]] = {}
    for r in receipts:
        for line in r.get("lines", []):
            nm = (line.get("fee_head_name") or "").lower()
            for tag in ("q1","q2","q3"):
                if tag in nm:
                    paid_q.setdefault(r["student_id"], {}).setdefault(tag.upper(), 0)
                    paid_q[r["student_id"]][tag.upper()] += float(line.get("amount", 0))
    total_paid: Dict[str, float] = {}
    for r in receipts:
        if r.get("receipt_type") in ("refund","debit_voucher"): continue
        total_paid[r["student_id"]] = total_paid.get(r["student_id"], 0) + r.get("total", 0)
    rows = []
    for s in students:
        fs = fs_map.get(s["fee_structure_id"])
        if not fs: continue
        if quarter in ("Q1","Q2","Q3"):
            qamt = sum(float(it.get("amount", 0)) for it in fs.get("items", []) if quarter.lower() in (it.get("fee_head_name","") or "").lower())
            paid = paid_q.get(s["id"], {}).get(quarter, 0)
            outstanding = qamt - paid
        else:
            qamt = fs.get("total", 0)
            paid = total_paid.get(s["id"], 0)
            outstanding = qamt - paid
        if outstanding <= 0: continue
        rows.append({
            "student_id": s["id"], "admission_no": s["admission_no"], "name": s["name"],
            "guardian_name": s.get("guardian_name"), "guardian_mobile": s.get("guardian_mobile"),
            "department_name": dept_map.get(s["department_id"],{}).get("name"),
            "class_name": class_map.get(s["class_id"],{}).get("name"),
            "fee": qamt, "paid": paid, "outstanding": outstanding,
        })
    rows.sort(key=lambda x: (-x["outstanding"]))
    return {"count": len(rows), "total_outstanding": sum(x["outstanding"] for x in rows), "students": rows, "quarter": quarter}

@router.get("/reports/day-end")
async def day_end_report(
    date: Optional[str] = None,
    cashier_id: Optional[str] = None,
    user = Depends(get_current_user),
):
    from datetime import datetime as _dt, timezone as _tz
    day = date or _dt.now(_tz.utc).date().isoformat()
    q: Dict[str, Any] = {"created_at": {"$gte": day + "T00:00:00", "$lte": day + "T23:59:59.999999"}}
    role = user.get("role")
    if role == "cashier":
        cashier_id = user["id"]
    if cashier_id:
        q["cashier_id"] = cashier_id
    receipts = await db.receipts.find(q, {"_id":0}).sort("created_at", 1).to_list(5000)

    def agg_of(rs):
        by_mode: Dict[str, float] = {}
        by_type: Dict[str, float] = {}
        collected = refunded = 0.0
        issued = cancelled = 0
        for r in rs:
            total = float(r.get("total", 0) or 0)
            mode = (r.get("payment_mode") or "other").lower()
            rt = r.get("receipt_type") or "school"
            if r.get("status") == "cancelled":
                cancelled += 1
                continue
            issued += 1
            if rt in ("refund","debit_voucher"):
                refunded += total
            else:
                collected += total
            by_mode[mode] = by_mode.get(mode, 0) + total
            by_type[rt] = by_type.get(rt, 0) + total
        return {
            "collected": round(collected, 2), "refunded": round(refunded, 2),
            "net": round(collected - refunded, 2), "issued": issued, "cancelled": cancelled,
            "by_mode": [{"mode": k, "amount": round(v,2)} for k, v in sorted(by_mode.items(), key=lambda x: -x[1])],
            "by_type": [{"type": k, "amount": round(v,2)} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
        }

    payload: Dict[str, Any] = {"date": day, "generated_at": now_iso(), "generated_by": user["name"]}
    if cashier_id:
        cashier = await db.users.find_one({"id": cashier_id}, {"_id":0, "password_hash":0}) or {"name": "Unknown"}
        payload["cashier"] = {"id": cashier_id, "name": cashier.get("name"), "role": cashier.get("role")}
        payload.update(agg_of(receipts))
        payload["receipts"] = [
            {"number": r.get("number"), "receipt_type": r.get("receipt_type"), "payer_name": r.get("payer_name"),
             "payment_mode": r.get("payment_mode"), "total": r.get("total"), "status": r.get("status"),
             "created_at": r.get("created_at"), "department_code": r.get("department_code")}
            for r in receipts
        ]
    else:
        by_cashier: Dict[str, List[dict]] = {}
        for r in receipts:
            by_cashier.setdefault(r.get("cashier_id","unknown"), []).append(r)
        cashiers = []
        for cid, rs in by_cashier.items():
            u = await db.users.find_one({"id": cid}, {"_id":0, "password_hash":0}) or {"name": rs[0].get("cashier_name","Unknown")}
            item = {"id": cid, "name": u.get("name"), "role": u.get("role"), **agg_of(rs)}
            cashiers.append(item)
        cashiers.sort(key=lambda x: -x["net"])
        payload["cashiers"] = cashiers
        payload.update(agg_of(receipts))
    return payload

# ---------- Bus Routes ----------
@router.get("/bus-routes")
async def list_bus_routes(user = Depends(get_current_user)):
    return await db.bus_routes.find({}, {"_id":0}).sort("name", 1).to_list(200)

@router.post("/bus-routes")
async def create_bus_route(body: BusRouteIn, user = Depends(require_roles("administrator","manager","accountant"))):
    if await db.bus_routes.find_one({"code": body.code}):
        raise HTTPException(400, "Route code already exists")
    rid = gen_id()
    doc = {"id": rid, **body.model_dump(), "created_at": now_iso()}
    await db.bus_routes.insert_one(doc)
    await audit(user, "create", "bus_route", rid, {"code": body.code})
    return {k:v for k,v in doc.items() if k != "_id"}

@router.patch("/bus-routes/{rid}")
async def update_bus_route(rid: str, body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    allowed = {k: v for k, v in body.items() if k in ("name","driver_name","driver_mobile","vehicle_no","monthly_fee","stops","active")}
    await db.bus_routes.update_one({"id": rid}, {"$set": allowed})
    await audit(user, "update", "bus_route", rid, allowed)
    return {"ok": True}

@router.get("/bus-routes/{rid}/roster")
async def bus_route_roster(rid: str, month: Optional[str] = None, user = Depends(get_current_user)):
    route = await db.bus_routes.find_one({"id": rid}, {"_id":0})
    if not route: raise HTTPException(404, "Route not found")
    students = await db.students.find({"bus_route": route["code"], "status":"active"}, {"_id":0}).to_list(2000)
    m = month or date.today().isoformat()[:7]
    sids = [s["id"] for s in students]
    receipts = await db.receipts.find({
        "receipt_type": "bus", "student_id": {"$in": sids}, "status": {"$ne":"cancelled"},
        "created_at": {"$gte": m + "-01", "$lte": m + "-31T23:59:59"},
    }, {"_id":0}).to_list(5000)
    paid_by = {}
    for r in receipts:
        paid_by[r["student_id"]] = paid_by.get(r["student_id"], 0) + r.get("total", 0)
    roster = []
    for s in students:
        roster.append({
            "student_id": s["id"], "admission_no": s["admission_no"], "name": s["name"],
            "class_id": s.get("class_id"), "guardian_mobile": s.get("guardian_mobile"),
            "paid_this_month": paid_by.get(s["id"], 0),
            "status": "paid" if paid_by.get(s["id"], 0) >= route.get("monthly_fee", 0) and route.get("monthly_fee", 0) > 0 else "pending",
        })
    collected = sum(paid_by.values())
    return {"route": route, "month": m, "students_count": len(students), "collected": collected, "expected": route.get("monthly_fee",0) * len(students), "roster": roster}

# ---------- Outstanding Notices ----------
@router.get("/notices/outstanding")
async def outstanding_notices(
    department_id: Optional[str] = None, class_id: Optional[str] = None,
    min_amount: float = 1,
    user = Depends(get_current_user),
):
    q: Dict[str, Any] = {"status":"active"}
    if department_id: q["department_id"] = department_id
    if class_id: q["class_id"] = class_id
    students = await db.students.find(q, {"_id":0}).to_list(5000)
    if not students:
        return {"count": 0, "students": []}
    dept_map = {d["id"]: d for d in await db.departments.find({}, {"_id":0}).to_list(50)}
    class_map = {c["id"]: c for c in await db.classes.find({}, {"_id":0}).to_list(500)}
    fs_ids = list({s.get("fee_structure_id") for s in students if s.get("fee_structure_id")})
    fs_map = {f["id"]: f for f in await db.fee_structures.find({"id":{"$in": fs_ids}}, {"_id":0}).to_list(500)} if fs_ids else {}
    routes = await db.bus_routes.find({}, {"_id":0}).to_list(200)
    route_map = {r["code"]: r for r in routes}
    settings = await get_settings_doc()
    bus_months = int(settings.get("bus_annual_months", 12) or 12)
    sids = [s["id"] for s in students]
    receipts = await db.receipts.find({"student_id":{"$in": sids}, "status":{"$ne":"cancelled"}}, {"_id":0}).to_list(20000)
    adjs = await db.adjustments.find({"student_id":{"$in": sids}, "status":"approved"}, {"_id":0}).to_list(5000)
    paid_by: Dict[str,float] = {}; refund_by: Dict[str,float] = {}; adj_by: Dict[str,float] = {}
    for r in receipts:
        if r.get("receipt_type") in ("refund",):
            refund_by[r["student_id"]] = refund_by.get(r["student_id"],0) + r.get("total",0)
        elif r.get("receipt_type") in ("school","admission","bus","misc","department","general_money","general_collection"):
            paid_by[r["student_id"]] = paid_by.get(r["student_id"],0) + r.get("total",0)
    for a in adjs:
        adj_by[a["student_id"]] = adj_by.get(a["student_id"],0) + a.get("amount",0)
    out = []
    for s in students:
        fs = fs_map.get(s.get("fee_structure_id"))
        academic_fee = fs.get("total", 0) if fs else 0
        bus_route = route_map.get(s.get("bus_route")) if s.get("bus_route") else None
        bus_fee_annual = float(bus_route.get("monthly_fee", 0)) * bus_months if bus_route else 0
        total_fee = academic_fee + bus_fee_annual
        paid = paid_by.get(s["id"], 0); refund = refund_by.get(s["id"], 0); adjusted = adj_by.get(s["id"], 0)
        outstanding = max(0, total_fee - paid - adjusted + refund)
        if outstanding < min_amount: continue
        out.append({
            "student_id": s["id"], "admission_no": s["admission_no"], "name": s["name"],
            "guardian_name": s.get("guardian_name"), "guardian_mobile": s.get("guardian_mobile"),
            "department_name": dept_map.get(s["department_id"],{}).get("name"),
            "class_name": class_map.get(s["class_id"],{}).get("name"),
            "academic_year": dept_map.get(s["department_id"],{}).get("academic_year"),
            "total_fee": total_fee, "academic_fee": academic_fee,
            "bus_route_code": s.get("bus_route") if bus_route else None,
            "bus_route_name": bus_route.get("name") if bus_route else None,
            "bus_monthly_fee": bus_route.get("monthly_fee") if bus_route else 0,
            "bus_months": bus_months if bus_route else 0,
            "bus_fee_annual": bus_fee_annual,
            "paid": paid, "adjusted": adjusted, "refunded": refund,
            "outstanding": outstanding,
            "items": fs.get("items", []) if fs else [],
        })
    out.sort(key=lambda x: (-x["outstanding"]))
    return {"count": len(out), "students": out}

# ---------- Quarterly Reminders (cron + manual) ----------
@router.post("/cron/quarterly-reminders")
async def cron_quarterly_reminders(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing auth")
    expected = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not expected or not hmac.compare_digest(auth[7:], expected):
        raise HTTPException(401, "Invalid cron secret")
    asyncio.create_task(_generate_quarterly_reminders())
    return {"accepted": True}

@router.post("/reminders/generate-quarterly")
async def manual_generate_quarterly(user = Depends(require_roles("administrator","manager","accountant"))):
    result = await _generate_quarterly_reminders()
    await audit(user, "generate_quarterly_reminders", "reminder", "", result)
    return result

# ---------- Public (no auth) ----------
@router.get("/public/student-lookup/{admission_no}")
async def public_student_lookup(admission_no: str):
    s = await db.students.find_one({"admission_no": admission_no}, {"_id": 0})
    if not s: raise HTTPException(404, "Student not found")
    guardian_mobile = s.get("guardian_mobile")
    siblings_query = {"status": "active"}
    if guardian_mobile:
        siblings_query["guardian_mobile"] = guardian_mobile
    else:
        siblings_query["id"] = s["id"]
    all_students = await db.students.find(siblings_query, {"_id": 0}).to_list(20)

    async def _ledger(stu):
        receipts = await db.receipts.find({"student_id": stu["id"], "status": {"$ne": "cancelled"}},
                                          {"_id": 0, "cashier_id": 0}).sort("created_at", -1).to_list(200)
        fs = None
        if stu.get("fee_structure_id"):
            fs = await db.fee_structures.find_one({"id": stu["fee_structure_id"]}, {"_id": 0})
        paid = sum(x.get("total", 0) for x in receipts if x.get("receipt_type") not in ("refund","debit_voucher"))
        refunded = sum(x.get("total", 0) for x in receipts if x.get("receipt_type") == "refund")
        adjustments = await db.adjustments.find({"student_id": stu["id"], "status": "approved"}, {"_id": 0}).to_list(100)
        adjusted = sum(a.get("amount", 0) for a in adjustments)
        total_fee = fs.get("total", 0) if fs else 0
        return {
            "student": {"admission_no": stu["admission_no"], "name": stu["name"], "guardian_name": stu.get("guardian_name"), "guardian_mobile": stu.get("guardian_mobile")},
            "ledger": {
                "total_fee": total_fee, "paid": paid, "adjusted": adjusted, "refunded": refunded,
                "outstanding": max(0, total_fee - paid - adjusted + refunded),
                "receipts": [{"number": x["number"], "type": x.get("receipt_type"), "date": x.get("created_at"), "total": x.get("total"), "mode": x.get("payment_mode")} for x in receipts[:10]],
                "receipts_count": len(receipts),
            }
        }

    children = [await _ledger(x) for x in all_students]
    combined = {
        "total_fee": sum(c["ledger"]["total_fee"] for c in children),
        "paid": sum(c["ledger"]["paid"] for c in children),
        "adjusted": sum(c["ledger"]["adjusted"] for c in children),
        "refunded": sum(c["ledger"]["refunded"] for c in children),
        "outstanding": sum(c["ledger"]["outstanding"] for c in children),
    }
    return {"guardian_mobile": guardian_mobile, "children": children, "combined": combined}

@router.get("/public/lookup/{number}")
async def public_lookup(number: str):
    r = await db.receipts.find_one({"number": number}, {"_id": 0, "cashier_id": 0})
    if not r:
        raise HTTPException(404, "Receipt not found")
    payload: Dict[str, Any] = {"receipt": r}
    if r.get("student_id"):
        s = await db.students.find_one({"id": r["student_id"]}, {"_id": 0})
        if s:
            payload["student"] = {
                "admission_no": s["admission_no"], "name": s["name"],
                "guardian_name": s.get("guardian_name"), "guardian_mobile": s.get("guardian_mobile"),
                "department_id": s.get("department_id"), "class_id": s.get("class_id"),
            }
            receipts = await db.receipts.find({"student_id": s["id"], "status": {"$ne": "cancelled"}},
                                              {"_id": 0, "cashier_id": 0}).sort("created_at", -1).to_list(200)
            fs = None
            if s.get("fee_structure_id"):
                fs = await db.fee_structures.find_one({"id": s["fee_structure_id"]}, {"_id": 0})
            paid = sum(x.get("total", 0) for x in receipts if x.get("receipt_type") not in ("refund","debit_voucher"))
            refunded = sum(x.get("total", 0) for x in receipts if x.get("receipt_type") == "refund")
            adjustments = await db.adjustments.find({"student_id": s["id"], "status": "approved"}, {"_id": 0}).to_list(100)
            adjusted = sum(a.get("amount", 0) for a in adjustments)
            total_fee = fs.get("total", 0) if fs else 0
            payload["ledger"] = {
                "total_fee": total_fee, "paid": paid, "adjusted": adjusted, "refunded": refunded,
                "outstanding": max(0, total_fee - paid - adjusted + refunded),
                "receipts": [{"number": x["number"], "type": x.get("receipt_type"), "date": x.get("created_at"), "total": x.get("total"), "mode": x.get("payment_mode")} for x in receipts[:20]],
                "receipts_count": len(receipts),
            }
    return payload
