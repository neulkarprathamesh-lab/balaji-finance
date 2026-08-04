from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Any, Dict, Literal
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query, Header, UploadFile, File
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
import io, zipfile, json as _json

# ---------------- DB ----------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = 'HS256'
ACCESS_MIN = 60 * 12  # 12h for LAN use

app = FastAPI(title="Balaji Convent Fee Software")
api = APIRouter(prefix="/api")

# ---------------- Utils ----------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def gen_id() -> str:
    return str(uuid.uuid4())

def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False

def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_MIN),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def clean(doc: dict) -> dict:
    if not doc: return doc
    doc.pop('_id', None)
    doc.pop('password_hash', None)
    return doc

# ---------------- Auth deps ----------------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(401, "User not found")
    return clean(user)

def require_roles(*roles: str):
    async def _dep(user = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"Requires role: {', '.join(roles)}")
        return user
    return _dep

async def audit(user: dict, action: str, entity: str, entity_id: str = "", details: dict = None):
    await db.audit_log.insert_one({
        "id": gen_id(), "user_id": user["id"], "user_email": user["email"],
        "user_role": user["role"], "action": action, "entity": entity,
        "entity_id": entity_id, "details": details or {}, "timestamp": now_iso(),
    })

# ---------------- Models ----------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["cashier", "accountant", "manager", "administrator"]
    department_id: Optional[str] = None

class DepartmentIn(BaseModel):
    name: str
    code: str  # used as receipt prefix eg EP, MP, SEC, JC
    academic_year: str = "2026-27"

class ReceiptTypeIn(BaseModel):
    code: str
    name: str
    department_name: Optional[str] = None
    department_id: Optional[str] = None
    category: Literal["school","bus","finance","misc"] = "school"
    description: Optional[str] = None
    icon: Optional[str] = None
    display_order: int = 100
    enabled: bool = True
    archived: bool = False
    tabs: List[str] = ["school","installment","misc"]
    default_payment_modes: List[str] = ["cash","upi","card"]
    print_template: str = "a4-navy"
    report_category: Optional[str] = None
    notes: Optional[str] = None
    # Phase 2 — Print settings
    paper_size: Literal["A4","A5","Thermal80"] = "A4"
    orientation: Literal["portrait","landscape"] = "portrait"
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    watermark_text: Optional[str] = None
    watermark_enabled: bool = False
    barcode_enabled: bool = False
    qr_enabled: bool = True
    signature_area_enabled: bool = True
    computer_generated_note: str = "This is a computer-generated receipt."
    # Numbering
    starting_number: int = 1
    current_number: Optional[int] = None
    auto_reset_yearly: bool = True
    # Per-type field toggles
    fields: Dict[str, bool] = {
        "admission_no": True, "roll_no": False, "parent_name": True, "mobile": True,
        "class": True, "division": False, "department": True, "academic_year": True,
        "session": False, "fee_head": True, "amount_in_words": True, "payment_mode": True,
        "transaction_id": True, "cashier_name": True, "authorized_by": False, "remarks": True,
    }

class ClassIn(BaseModel):
    department_id: str
    name: str  # e.g. "Class 1", "Class 5"
    section: Optional[str] = None

class FeeHeadIn(BaseModel):
    name: str  # e.g. Tuition, Exam, Activity, Bus
    code: str
    category: Literal["school", "admission", "bus", "misc", "general"] = "school"

class FeeStructureIn(BaseModel):
    department_id: str
    class_id: str
    academic_year: str = "2026-27"
    items: List[Dict[str, Any]]  # [{fee_head_id, amount, installments:[{name,due_date,amount}]}]

class StudentIn(BaseModel):
    admission_no: str
    name: str
    department_id: str
    class_id: str
    section: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_mobile: Optional[str] = None
    address: Optional[str] = None
    fee_structure_id: Optional[str] = None
    bus_route: Optional[str] = None
    admission_category: Optional[str] = None
    admission_date: Optional[str] = None

class ReceiptLineIn(BaseModel):
    fee_head_id: Optional[str] = None
    fee_head_name: str
    installment: Optional[str] = None
    amount: float
    note: Optional[str] = None

class ReceiptIn(BaseModel):
    receipt_type: Literal["school","admission","bus","misc","department","general_money","refund","debit_voucher","general_collection"]
    department_id: str
    student_id: Optional[str] = None
    payer_name: Optional[str] = None
    purpose: Optional[str] = None
    payment_mode: Literal["cash","cheque","dd","upi","neft","card","other"] = "cash"
    payment_reference: Optional[str] = None
    lines: List[ReceiptLineIn]
    remarks: Optional[str] = None
    linked_receipt_id: Optional[str] = None  # for refunds
    approver_id: Optional[str] = None
    metadata: Dict[str, Any] = {}  # {village_name, month, bus_no, paid_to, ac_head, faculti, session, dd_no, on_account_of, class_name}

class AdjustmentIn(BaseModel):
    student_id: str
    adjustment_type: Literal["scholarship","staff_child","management","financial_assistance","special","correction"]
    amount: float
    reason: str
    fee_head_id: Optional[str] = None

class ExtensionIn(BaseModel):
    student_id: str
    outstanding_amount: float
    installments: List[Dict[str, Any]]  # [{amount,due_date}] max 4
    application_note: Optional[str] = None
    scanned_url: Optional[str] = None

class ReminderFollowupIn(BaseModel):
    reminder_id: str
    remark_type: Literal["will_pay_today","will_pay_tomorrow","contacted","not_reachable","visited","payment_received","other"]
    details: Optional[str] = None

class PromoteIn(BaseModel):
    from_class_id: str
    to_class_id: str
    to_fee_structure_id: Optional[str] = None
    new_academic_year: Optional[str] = None
    section: Optional[str] = None

class RolloverIn(BaseModel):
    from_academic_year: str  # e.g. "2026-27"
    to_academic_year: str    # e.g. "2027-28"

class BusStopIn(BaseModel):
    name: str
    monthly_fee: float

class BusRouteIn(BaseModel):
    name: str
    code: str
    driver_name: Optional[str] = None
    driver_mobile: Optional[str] = None
    vehicle_no: Optional[str] = None
    monthly_fee: float = 0
    stops: List[BusStopIn] = []
    active: bool = True

# ---------------- Auth ----------------
@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("active", True):
        raise HTTPException(403, "Account disabled")
    token = create_access_token(user["id"], user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=ACCESS_MIN*60, path="/")
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": now_iso()}})
    return {"token": token, "user": clean(user)}

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user = Depends(get_current_user)):
    return user

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

@api.patch("/auth/me")
async def update_me(body: ProfileUpdate, user = Depends(get_current_user)):
    upd: Dict[str, Any] = {}
    if body.name and body.name.strip():
        upd["name"] = body.name.strip()
    if body.new_password:
        if not body.current_password:
            raise HTTPException(400, "Current password required to change password")
        current = await db.users.find_one({"id": user["id"]})
        if not current or not verify_password(body.current_password, current["password_hash"]):
            raise HTTPException(400, "Current password is incorrect")
        if len(body.new_password) < 6:
            raise HTTPException(400, "New password must be at least 6 characters")
        upd["password_hash"] = hash_password(body.new_password)
    if not upd:
        raise HTTPException(400, "Nothing to update")
    await db.users.update_one({"id": user["id"]}, {"$set": upd})
    await audit(user, "update", "profile", user["id"], {"fields": [k for k in upd.keys() if k != "password_hash"] + (["password"] if "password_hash" in upd else [])})
    fresh = await db.users.find_one({"id": user["id"]})
    return clean(fresh)

class PinSetIn(BaseModel):
    new_pin: str
    current_password: Optional[str] = None
    current_pin: Optional[str] = None

class PinVerifyIn(BaseModel):
    pin: str

@api.get("/auth/me/pin-status")
async def pin_status(user = Depends(get_current_user)):
    current = await db.users.find_one({"id": user["id"]})
    return {"has_pin": bool(current and current.get("pin_hash"))}

@api.post("/auth/me/pin")
async def set_pin(body: PinSetIn, user = Depends(get_current_user)):
    if not body.new_pin.isdigit() or len(body.new_pin) != 4:
        raise HTTPException(400, "PIN must be exactly 4 digits")
    current = await db.users.find_one({"id": user["id"]})
    if current.get("pin_hash"):
        # Changing existing PIN — require current PIN
        if not body.current_pin or not verify_password(body.current_pin, current["pin_hash"]):
            raise HTTPException(400, "Current PIN is incorrect")
    else:
        # Setting for the first time — require password
        if not body.current_password or not verify_password(body.current_password, current["password_hash"]):
            raise HTTPException(400, "Current password is required to set PIN")
    await db.users.update_one({"id": user["id"]}, {"$set": {"pin_hash": hash_password(body.new_pin)}})
    await audit(user, "set_pin", "user", user["id"])
    return {"ok": True}

@api.delete("/auth/me/pin")
async def remove_pin(user = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$unset": {"pin_hash": ""}})
    await audit(user, "remove_pin", "user", user["id"])
    return {"ok": True}

@api.post("/auth/me/pin/verify")
async def verify_pin(body: PinVerifyIn, user = Depends(get_current_user)):
    current = await db.users.find_one({"id": user["id"]})
    if not current or not current.get("pin_hash"):
        raise HTTPException(400, "No PIN set")
    if not verify_password(body.pin, current["pin_hash"]):
        raise HTTPException(401, "Incorrect PIN")
    return {"ok": True}

# ---------------- Settings ----------------
SETTINGS_ID = "school_settings"

async def get_settings_doc():
    doc = await db.settings.find_one({"id": SETTINGS_ID}, {"_id": 0})
    if not doc:
        doc = {
            "id": SETTINGS_ID,
            "school_name": "Balaji Convent & Junior College",
            "school_address": "Butibori, Nagpur",
            "school_phone": "",
            "school_email": "",
            "receipt_footer": "This is a computer-generated receipt.",
            "notice_footer": "Fee counter timing: 9:00 AM – 3:00 PM (Monday to Saturday). Modes accepted: Cash / Cheque / DD / UPI / NEFT.",
            "bus_annual_months": 12,
            "q1_due_date": "2026-06-30",
            "q2_due_date": "2026-09-30",
            "q3_due_date": "2026-12-31",
            "reminder_lead_days": 7,
            "manager_waiver_cap": 5000,
        }
        await db.settings.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc

@api.get("/settings")
async def read_settings(user = Depends(get_current_user)):
    return await get_settings_doc()

@api.patch("/settings")
async def update_settings(body: Dict[str, Any], user = Depends(require_roles("administrator"))):
    await get_settings_doc()  # ensure exists
    allowed = {k: v for k, v in body.items() if k in ("school_name","school_address","school_phone","school_email","receipt_footer","notice_footer","bus_annual_months","q1_due_date","q2_due_date","q3_due_date","reminder_lead_days","manager_waiver_cap")}
    await db.settings.update_one({"id": SETTINGS_ID}, {"$set": allowed})
    await audit(user, "update", "settings", SETTINGS_ID, allowed)
    return await get_settings_doc()

# ---------------- Users (admin) ----------------
@api.get("/users")
async def list_users(user = Depends(require_roles("administrator"))):
    users = await db.users.find({}, {"password_hash":0, "_id":0}).to_list(500)
    return users

@api.post("/users")
async def create_user(body: UserCreate, user = Depends(require_roles("administrator"))):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already exists")
    uid = gen_id()
    doc = {
        "id": uid, "email": body.email.lower(), "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role, "department_id": body.department_id,
        "active": True, "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    await audit(user, "create", "user", uid, {"email": body.email, "role": body.role})
    return clean(doc)

@api.patch("/users/{uid}")
async def update_user(uid: str, body: Dict[str, Any], user = Depends(require_roles("administrator"))):
    upd = {k: v for k, v in body.items() if k in ("name","role","department_id","active")}
    if "password" in body and body["password"]:
        upd["password_hash"] = hash_password(body["password"])
    await db.users.update_one({"id": uid}, {"$set": upd})
    await audit(user, "update", "user", uid, upd)
    return {"ok": True}

# ---------------- Departments ----------------
@api.get("/departments")
async def list_departments(user = Depends(get_current_user)):
    return await db.departments.find({}, {"_id":0}).to_list(100)

@api.post("/departments")
async def create_department(body: DepartmentIn, user = Depends(require_roles("administrator"))):
    did = gen_id()
    doc = {"id": did, **body.model_dump(), "created_at": now_iso()}
    await db.departments.insert_one(doc)
    await audit(user, "create", "department", did, body.model_dump())
    return {k:v for k,v in doc.items() if k != "_id"}

# ---------------- Classes ----------------
@api.get("/classes")
async def list_classes(department_id: Optional[str] = None, user = Depends(get_current_user)):
    q = {"department_id": department_id} if department_id else {}
    return await db.classes.find(q, {"_id":0}).to_list(500)

@api.post("/classes")
async def create_class(body: ClassIn, user = Depends(require_roles("administrator","manager"))):
    cid = gen_id()
    doc = {"id": cid, **body.model_dump(), "created_at": now_iso()}
    await db.classes.insert_one(doc)
    await audit(user, "create", "class", cid, body.model_dump())
    return {k:v for k,v in doc.items() if k != "_id"}

# ---------------- Fee Heads ----------------
@api.get("/fee-heads")
async def list_fee_heads(user = Depends(get_current_user)):
    return await db.fee_heads.find({}, {"_id":0}).to_list(200)

@api.post("/fee-heads")
async def create_fee_head(body: FeeHeadIn, user = Depends(require_roles("administrator","manager"))):
    fid = gen_id()
    doc = {"id": fid, **body.model_dump(), "created_at": now_iso()}
    await db.fee_heads.insert_one(doc)
    await audit(user, "create", "fee_head", fid, body.model_dump())
    return {k:v for k,v in doc.items() if k != "_id"}

# ---------------- Fee Structures ----------------
@api.get("/fee-structures")
async def list_fee_structures(department_id: Optional[str] = None, class_id: Optional[str] = None, user = Depends(get_current_user)):
    q = {}
    if department_id: q["department_id"] = department_id
    if class_id: q["class_id"] = class_id
    return await db.fee_structures.find(q, {"_id":0}).to_list(500)

@api.post("/fee-structures")
async def create_fee_structure(body: FeeStructureIn, user = Depends(require_roles("administrator","manager","accountant"))):
    fid = gen_id()
    total = sum(float(i.get("amount", 0)) for i in body.items)
    doc = {"id": fid, **body.model_dump(), "total": total, "created_at": now_iso()}
    await db.fee_structures.insert_one(doc)
    await audit(user, "create", "fee_structure", fid, {"total": total})
    return {k:v for k,v in doc.items() if k != "_id"}

@api.post("/fee-structures/{fid}/duplicate")
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

# ---------------- Students ----------------
@api.get("/students")
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
    docs = await db.students.find(query, {"_id":0}).limit(limit).to_list(limit)
    return docs

@api.get("/students/{sid}")
async def get_student(sid: str, user = Depends(get_current_user)):
    s = await db.students.find_one({"id": sid}, {"_id":0})
    if not s: raise HTTPException(404, "Student not found")
    return s

@api.get("/students/{sid}/ledger")
async def student_ledger(sid: str, user = Depends(get_current_user)):
    s = await db.students.find_one({"id": sid}, {"_id":0})
    if not s: raise HTTPException(404, "Not found")
    receipts = await db.receipts.find({"student_id": sid, "status":{"$ne":"cancelled"}}, {"_id":0}).sort("created_at", -1).to_list(500)
    adjustments = await db.adjustments.find({"student_id": sid, "status":"approved"}, {"_id":0}).to_list(200)
    fs = None
    if s.get("fee_structure_id"):
        fs = await db.fee_structures.find_one({"id": s["fee_structure_id"]}, {"_id":0})
    total_paid = sum(r.get("total", 0) for r in receipts if r.get("receipt_type") != "refund" and r.get("receipt_type") != "debit_voucher")
    total_refunded = sum(r.get("total", 0) for r in receipts if r.get("receipt_type") == "refund")
    total_adjusted = sum(a.get("amount", 0) for a in adjustments)
    payable = (fs.get("total") if fs else 0) - total_paid - total_adjusted + total_refunded
    return {
        "student": s, "fee_structure": fs, "receipts": receipts, "adjustments": adjustments,
        "total_paid": total_paid, "total_refunded": total_refunded,
        "total_adjusted": total_adjusted, "outstanding": max(0, payable),
    }

@api.post("/students")
async def create_student(body: StudentIn, user = Depends(require_roles("administrator","manager","accountant","cashier"))):
    existing = await db.students.find_one({"admission_no": body.admission_no})
    if existing:
        raise HTTPException(400, "Admission number already exists")
    sid = gen_id()
    doc = {"id": sid, **body.model_dump(), "status":"active", "created_at": now_iso()}
    await db.students.insert_one(doc)
    await audit(user, "create", "student", sid, {"admission_no": body.admission_no})
    return {k:v for k,v in doc.items() if k != "_id"}

@api.post("/students/bulk-import")
async def bulk_import_students(body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    """Body: {rows: [ {admission_no, name, department_code, class_name, guardian_name, guardian_mobile, ...} ], batch_id?: str}"""
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

@api.post("/students/bulk-delete")
async def bulk_delete_students(body: Dict[str, Any], user = Depends(require_roles("administrator","manager"))):
    """Undo Last Import: delete students by ids OR by batch_id. Skips any student who has receipts."""
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
    # Filter out students with receipts
    with_receipts = await db.receipts.distinct("student_id", {"student_id": {"$in": [s["id"] for s in stus]}})
    protected_ids = set(with_receipts)
    deletable = [s["id"] for s in stus if s["id"] not in protected_ids]
    result = await db.students.delete_many({"id": {"$in": deletable}}) if deletable else None
    if batch_id:
        await db.import_batches.update_one({"id": batch_id}, {"$set": {"undone_at": now_iso(), "undone_by": user["name"], "undone_deleted": len(deletable), "undone_protected": len(protected_ids)}})
    await audit(user, "bulk_delete", "student", batch_id or "", {"deleted": len(deletable), "protected": len(protected_ids)})
    return {"deleted": len(deletable), "protected_with_receipts": len(protected_ids), "batch_id": batch_id}

@api.post("/fee-structures/bulk-import")
async def bulk_import_fee_structures(body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    """Body: {rows: [{department_code, class_name, academic_year, fee_head_name, amount}], batch_id?}
    Rows for the same (dept, class, year) are grouped into a single fee_structure. Existing structures are updated (heads merged)."""
    rows = body.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise HTTPException(400, "rows must be a non-empty array")
    batch_id = body.get("batch_id") or gen_id()
    depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(100)}
    classes = await db.classes.find({}, {"_id":0}).to_list(500)
    # Group rows by (dept_code, class_name, academic_year)
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
            # Merge: append heads that don't exist by name, replace amount for those that do
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

@api.post("/fee-structures/bulk-delete")
async def bulk_delete_fee_structures(body: Dict[str, Any], user = Depends(require_roles("administrator","manager"))):
    """Undo Last Fee-Structure Import: delete structures created by a batch, skipping any referenced by active students."""
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

@api.get("/imports/latest")
async def latest_import_batch(kind: Literal["students","fee_structures"], user = Depends(get_current_user)):
    """Return the most recent import batch of the requested kind that hasn't been undone."""
    doc = await db.import_batches.find_one({"type": kind, "undone_at": {"$exists": False}}, {"_id":0}, sort=[("created_at", -1)])
    return doc or {}

@api.get("/imports/history")
async def imports_history(
    kind: Optional[Literal["students","fee_structures"]] = None,
    limit: int = 100,
    user = Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if kind: q["type"] = kind
    return await db.import_batches.find(q, {"_id":0}).sort("created_at", -1).limit(limit).to_list(limit)

@api.get("/students/{sid}/siblings")
async def student_siblings(sid: str, user = Depends(get_current_user)):
    """Return other active students sharing the same guardian_mobile."""
    s = await db.students.find_one({"id": sid}, {"_id":0})
    if not s: raise HTTPException(404, "Not found")
    gm = (s.get("guardian_mobile") or "").strip()
    if not gm: return {"siblings": []}
    others = await db.students.find(
        {"guardian_mobile": gm, "status": "active", "id": {"$ne": sid}},
        {"_id":0}
    ).to_list(20)
    return {"siblings": others}

@api.post("/students/bulk-reassign")
async def bulk_reassign_students(body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    """Body: {student_ids: [], to_class_id, to_fee_structure_id?}"""
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

@api.patch("/students/{sid}")
async def update_student(sid: str, body: Dict[str,Any], user = Depends(require_roles("administrator","manager","accountant"))):
    upd = {k:v for k,v in body.items() if k in ("name","class_id","section","guardian_name","guardian_mobile","address","fee_structure_id","bus_route","status")}
    await db.students.update_one({"id": sid}, {"$set": upd})
    await audit(user, "update", "student", sid, upd)
    return {"ok": True}

# ---------------- Receipts ----------------
async def next_receipt_number(dept_code: str, academic_year: str) -> str:
    key = f"{dept_code}-{academic_year}"
    doc = await db.counters.find_one_and_update(
        {"key": key}, {"$inc": {"seq": 1}}, upsert=True, return_document=True,
    )
    if not doc:
        doc = await db.counters.find_one({"key": key})
    seq = doc.get("seq", 1) if doc else 1
    return f"{dept_code}-{academic_year.split('-')[0]}-{seq:06d}"

async def next_receipt_number_by_prefix(prefix: str, academic_year: str) -> str:
    """Prefix-based receipt numbering. Used when a receipt-type overrides the department code."""
    key = f"RT-{prefix}-{academic_year}"
    doc = await db.counters.find_one_and_update(
        {"key": key}, {"$inc": {"seq": 1}}, upsert=True, return_document=True,
    )
    seq = doc.get("seq", 1) if doc else 1
    return f"{prefix}-{academic_year.split('-')[0]}-{seq:06d}"

# ---------------- Administrator PIN gate (sensitive actions) ----------------
async def require_admin_pin(x_admin_pin: Optional[str] = Header(None), user = Depends(require_roles("administrator"))):
    if not x_admin_pin:
        raise HTTPException(401, "Administrator PIN required")
    current = await db.users.find_one({"id": user["id"]})
    if not current.get("pin_hash"):
        raise HTTPException(400, "Set your Administrator PIN in My Profile first.")
    if not verify_password(x_admin_pin, current["pin_hash"]):
        await audit(user, "admin_pin_fail", "auth", user["id"], {"event": "invalid_pin"})
        raise HTTPException(403, "Invalid administrator PIN")
    return user

async def require_admin_dual(
    x_admin_pin: Optional[str] = Header(None),
    x_admin_password: Optional[str] = Header(None),
    user = Depends(require_roles("administrator")),
):
    if not x_admin_pin or not x_admin_password:
        raise HTTPException(401, "Administrator PIN and password required for this action")
    current = await db.users.find_one({"id": user["id"]})
    if not current.get("pin_hash") or not verify_password(x_admin_pin, current["pin_hash"]):
        await audit(user, "admin_dual_fail", "auth", user["id"], {"event": "invalid_pin"})
        raise HTTPException(403, "Invalid administrator PIN")
    if not verify_password(x_admin_password, current["password_hash"]):
        await audit(user, "admin_dual_fail", "auth", user["id"], {"event": "invalid_password"})
        raise HTTPException(403, "Invalid administrator password")
    return user

@api.post("/auth/admin-pin/verify")
async def verify_admin_pin(body: Dict[str, Any], user = Depends(require_roles("administrator"))):
    """Frontend-friendly probe — verifies PIN before opening a sensitive UI."""
    pin = body.get("pin","")
    current = await db.users.find_one({"id": user["id"]})
    if not current.get("pin_hash"):
        raise HTTPException(400, "Administrator PIN not set. Please set it in My Profile.")
    ok = verify_password(pin, current["pin_hash"])
    await audit(user, "admin_pin_verify", "auth", user["id"], {"ok": ok})
    if not ok:
        raise HTTPException(403, "Invalid administrator PIN")
    return {"ok": True}

@api.get("/version")
async def app_version():
    return {
        "app_version": "1.0.0",
        "database_version": "1",
        "receipt_template_version": "1.0",
        "app_template_version": "1.0",
        "build_date": "2026-02-04",
        "developer": "Emergent Labs",
        "server_time": now_iso(),
    }

# ---------------- Configuration Export / Import ----------------
CONFIG_COLLECTIONS = [
    "receipt_types", "departments", "classes", "fee_heads", "fee_structures",
    "settings", "bus_routes",
]

BACKUP_DIR = Path("/app/backups")

async def _create_backup_zip(kind: str, actor_name: str) -> Dict[str, Any]:
    """Dumps every collection as JSON into a ZIP, records metadata, verifies integrity."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    bid = gen_id()
    fname = f"balaji-{kind}-{ts}-v1.0.0.zip"
    path = BACKUP_DIR / fname
    all_colls = list(set(CONFIG_COLLECTIONS + ["users","receipts","students","adjustments","extensions","reminders","import_batches","audit","counters"]))
    manifest = {"id": bid, "kind": kind, "created_at": now_iso(), "created_by": actor_name, "app_version":"1.0.0", "database_version":"1", "collections": []}
    import hashlib
    hasher = hashlib.sha256()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for coll in sorted(all_colls):
            rows = await db[coll].find({}, {"_id":0}).to_list(200000)
            payload = _json.dumps(rows, default=str)
            zf.writestr(f"{coll}.json", payload)
            manifest["collections"].append({"name": coll, "count": len(rows), "bytes": len(payload)})
            hasher.update(payload.encode())
        zf.writestr("manifest.json", _json.dumps(manifest, indent=2, default=str))
    # Verify by re-opening
    with zipfile.ZipFile(path, "r") as zf:
        bad = zf.testzip()
        if bad: raise RuntimeError(f"Backup verification failed at {bad}")
    size = path.stat().st_size
    manifest["size"] = size
    manifest["filename"] = fname
    manifest["path"] = str(path)
    manifest["checksum_sha256"] = hasher.hexdigest()
    await db.backups.insert_one(manifest.copy())
    return manifest

@api.post("/config/backup")
async def create_manual_backup(user = Depends(require_admin_pin)):
    m = await _create_backup_zip("manual", user["name"])
    await audit(user, "backup_create", "system", m["id"], {"kind": m["kind"], "size": m["size"]})
    return {k:v for k,v in m.items() if k != "_id"}

@api.get("/config/backups")
async def list_backups(limit: int = 50, user = Depends(require_roles("administrator"))):
    return await db.backups.find({}, {"_id":0}).sort("created_at", -1).limit(limit).to_list(limit)

@api.get("/config/backups/{bid}/download")
async def download_backup(bid: str, user = Depends(require_admin_pin)):
    doc = await db.backups.find_one({"id": bid}, {"_id":0})
    if not doc: raise HTTPException(404, "Backup not found")
    p = Path(doc["path"])
    if not p.exists(): raise HTTPException(410, "Backup file missing on disk")
    await audit(user, "backup_download", "system", bid, {"filename": doc["filename"]})
    return StreamingResponse(open(p, "rb"), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{doc["filename"]}"'})

@api.get("/config/export")
async def export_config(user = Depends(require_admin_pin)):
    """Export school configuration as a ZIP (JSON per collection). Passwords & PINs are stripped from users."""
    buf = io.BytesIO()
    manifest = {"exported_at": now_iso(), "exported_by": user["name"], "app_version": "1.0.0", "collections": []}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for coll in CONFIG_COLLECTIONS:
            rows = await db[coll].find({}, {"_id":0}).to_list(20000)
            zf.writestr(f"{coll}.json", _json.dumps(rows, indent=2, default=str))
            manifest["collections"].append({"name": coll, "count": len(rows)})
        # Users: strip password_hash and pin_hash for portability
        users = await db.users.find({}, {"_id":0, "password_hash":0, "pin_hash":0}).to_list(500)
        zf.writestr("users.json", _json.dumps(users, indent=2, default=str))
        manifest["collections"].append({"name": "users", "count": len(users), "notes": "password/pin stripped"})
        zf.writestr("manifest.json", _json.dumps(manifest, indent=2))
        readme = ("# Balaji Fee Software — Configuration Export\n\n"
                  f"Exported: {manifest['exported_at']}\nBy: {manifest['exported_by']}\n\n"
                  "Import this ZIP into another school PC via Administration → Config Import.\n"
                  "Users are exported WITHOUT passwords/PINs — you must reset them after import.\n")
        zf.writestr("README.md", readme)
    buf.seek(0)
    await audit(user, "config_export", "system", "", {"collections": [c["name"] for c in manifest["collections"]]})
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="balaji-config-{date.today().isoformat()}.zip"'}
    )

@api.post("/config/import")
async def import_config(
    replace: bool = False,
    file: UploadFile = File(...),
    user = Depends(require_admin_dual),
):
    """Restore collections from a config ZIP. `replace=false` upserts by id; `replace=true` drops+inserts each collection."""
    content = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(content), "r")
    except zipfile.BadZipFile:
        raise HTTPException(400, "Not a valid ZIP")
    names = set(zf.namelist())
    if "manifest.json" not in names:
        raise HTTPException(400, "manifest.json missing — this is not a Balaji config ZIP")
    manifest = _json.loads(zf.read("manifest.json").decode())
    # SAFETY: Auto-backup before REPLACE-mode import
    pre_backup = None
    if replace:
        try:
            pre_backup = await _create_backup_zip("pre-import", user["name"])
            await audit(user, "backup_auto", "system", pre_backup["id"], {"reason": "pre_import_replace", "size": pre_backup["size"]})
        except Exception as e:
            raise HTTPException(500, f"Pre-import backup failed — refusing to proceed: {e}")
    summary: Dict[str, Any] = {"imported": {}, "pre_backup": pre_backup}
    for coll in CONFIG_COLLECTIONS + ["users"]:
        fn = f"{coll}.json"
        if fn not in names: continue
        rows = _json.loads(zf.read(fn).decode() or "[]")
        if replace:
            await db[coll].delete_many({})
        added = updated = 0
        for r in rows:
            if not isinstance(r, dict) or not r.get("id"):
                continue
            if coll == "users":
                # never overwrite existing user credentials
                if await db.users.find_one({"id": r["id"]}): 
                    continue
                r["password_hash"] = hash_password(gen_id()[:12])  # random temp password
                r["pin_hash"] = None
                await db.users.insert_one(r); added += 1; continue
            existing = await db[coll].find_one({"id": r["id"]})
            if existing:
                await db[coll].update_one({"id": r["id"]}, {"$set": r}); updated += 1
            else:
                await db[coll].insert_one(r); added += 1
        summary["imported"][coll] = {"added": added, "updated": updated, "total_in_file": len(rows)}
    await audit(user, "config_import", "system", "", {"replace": replace, "summary": summary, "manifest": manifest})
    return {"ok": True, "replace_mode": replace, "manifest": manifest, "summary": summary}


# ---------------- Receipt Types (DB-backed) ----------------
DEFAULT_RECEIPT_TYPES = [
    {"code":"EP",     "name":"Balaji Convent English Primary School",                 "department_name":"English Primary Section",              "category":"school", "description":"Fees for Class 1–4 (English medium)",              "icon":"GraduationCap",   "display_order":10, "tabs":["school","installment","misc"]},
    {"code":"MP",     "name":"Balaji Convent Marathi Primary School",                 "department_name":"Marathi Primary Section",              "category":"school", "description":"Fees for इयत्ता १–४ (मराठी माध्यम)",             "icon":"BookOpen",        "display_order":20, "tabs":["school","installment","misc"]},
    {"code":"EMP",    "name":"Balaji Convent English & Marathi Primary School",       "department_name":"English + Marathi Primary (Combined)", "category":"school", "description":"Combined receipt when a family pays for both mediums", "icon":"GraduationCap", "display_order":30, "tabs":["school","installment","misc"]},
    {"code":"SEC",    "name":"Balaji Convent Secondary School (Self Financing)",     "department_name":"Secondary Section",                    "category":"school", "description":"Class 5–10 self-financing",                         "icon":"Award",           "display_order":40, "tabs":["school","installment","misc"]},
    {"code":"JC",     "name":"Balaji Convent Junior College",                          "department_name":"Junior College",                       "category":"school", "description":"XI–XII, all standard streams",                       "icon":"GraduationCap",   "display_order":50, "tabs":["school","installment","misc"]},
    {"code":"JCACS",  "name":"Balaji Convent JC (Arts, Commerce, Science & Bifocal)","department_name":"Junior College — ACS/Bifocal",         "category":"school", "description":"XI–XII with bifocal & specialised streams",         "icon":"Award",           "display_order":60, "tabs":["school","installment","misc"]},
    {"code":"BUS",    "name":"Balaji Convent Bus Receipt",                             "department_name":"School Bus Transport",                 "category":"bus",    "description":"Monthly / termly bus route fees",                    "icon":"Bus",             "display_order":70, "tabs":["school"]},
    {"code":"EMJC",   "name":"Balaji Convent English, Marathi & Junior College",     "department_name":"Combined EM + MP + JC",                "category":"school", "description":"Consolidated receipt across all three sections",     "icon":"ClipboardList",   "display_order":80, "tabs":["school","installment","misc"]},
    {"code":"DV",     "name":"Debit Voucher",                                          "department_name":"Finance / Petty Cash",                 "category":"finance","description":"For expenses, refunds, vendor payments",             "icon":"Wallet",          "display_order":90, "tabs":["school"]},
]

async def _seed_receipt_types_if_empty():
    n = await db.receipt_types.count_documents({})
    if n > 0: return
    depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(50)}
    now = now_iso()
    for t in DEFAULT_RECEIPT_TYPES:
        dept = depts.get(t["code"])  # link when code matches an existing dept
        await db.receipt_types.insert_one({
            "id": gen_id(), **t,
            "department_id": dept["id"] if dept else None,
            "enabled": True, "archived": False,
            "default_payment_modes": ["cash","upi","card"],
            "print_template": "a4-navy", "report_category": t["category"],
            "created_at": now, "updated_at": now,
        })

@api.get("/receipt-types")
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
    rows = await db.receipt_types.find(q, {"_id":0}).sort("display_order", 1).to_list(200)
    return rows

@api.get("/receipt-types/{rtid}")
async def get_receipt_type(rtid: str, user = Depends(get_current_user)):
    doc = await db.receipt_types.find_one({"id": rtid}, {"_id":0})
    if not doc: raise HTTPException(404, "Not found")
    return doc

@api.post("/receipt-types")
async def create_receipt_type(body: ReceiptTypeIn, user = Depends(require_admin_pin)):
    if await db.receipt_types.find_one({"code": body.code.upper()}):
        raise HTTPException(400, f"Receipt type with prefix {body.code} already exists")
    rid = gen_id()
    doc = {"id": rid, **body.model_dump(), "code": body.code.upper(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.receipt_types.insert_one(doc)
    await audit(user, "create", "receipt_type", rid, {"code": doc["code"], "name": doc["name"]})
    return {k:v for k,v in doc.items() if k != "_id"}

@api.patch("/receipt-types/{rtid}")
async def update_receipt_type(rtid: str, body: Dict[str, Any], user = Depends(require_admin_pin)):
    existing = await db.receipt_types.find_one({"id": rtid})
    if not existing: raise HTTPException(404, "Not found")
    allowed = {"name","department_name","department_id","category","description","icon","display_order","enabled","tabs","default_payment_modes","print_template","report_category","notes","archived",
               "paper_size","orientation","header_text","footer_text","watermark_text","watermark_enabled","barcode_enabled","qr_enabled","signature_area_enabled","computer_generated_note",
               "starting_number","current_number","auto_reset_yearly","fields"}
    upd = {k: v for k, v in body.items() if k in allowed}
    # Special: changing prefix code is sensitive — audit-log heavy but allow admin
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

@api.delete("/receipt-types/{rtid}")
async def delete_receipt_type(rtid: str, user = Depends(require_admin_pin)):
    doc = await db.receipt_types.find_one({"id": rtid})
    if not doc: raise HTTPException(404, "Not found")
    used = await db.receipts.count_documents({"receipt_type_id": rtid})
    if used > 0:
        raise HTTPException(409, {"message": f"This receipt type has {used} existing transactions. Disable or archive it instead.", "used_count": used, "can_archive": True})
    await db.receipt_types.delete_one({"id": rtid})
    await audit(user, "delete", "receipt_type", rtid, {"code": doc.get("code"), "name": doc.get("name")})
    return {"deleted": True}

@api.post("/receipt-types/{rtid}/archive")
async def archive_receipt_type(rtid: str, user = Depends(require_admin_pin)):
    doc = await db.receipt_types.find_one({"id": rtid})
    if not doc: raise HTTPException(404, "Not found")
    await db.receipt_types.update_one({"id": rtid}, {"$set": {"archived": True, "enabled": False, "updated_at": now_iso()}})
    await audit(user, "archive", "receipt_type", rtid, {"code": doc.get("code")})
    return {"archived": True}

@api.post("/receipt-types/{rtid}/reset-sequence")
async def reset_receipt_type_sequence(rtid: str, body: Dict[str, Any], user = Depends(require_admin_dual)):
    """Manual Sequence Reset — DUAL-AUTH required (PIN + password).
    Body: {new_number: int, reason: str}
    Refuses if any receipt already exists at or above the new_number for this prefix + academic year."""
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
    # Safety: check no existing receipt with number >= new_number
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
    # Counter uses seq value that will be POST-INCREMENTED — so next issued will be (seq+1). We store new_number - 1.
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

@api.post("/receipt-types/reseed-defaults")
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

async def next_voucher_number(academic_year: str) -> str:
    key = f"VCH-{academic_year}"
    doc = await db.counters.find_one_and_update(
        {"key": key}, {"$inc": {"seq": 1}}, upsert=True, return_document=True,
    )
    seq = doc.get("seq", 1) if doc else 1
    return f"V-{academic_year.split('-')[0]}-{seq:06d}"

def amount_in_words_inr(n: float) -> str:
    n = int(round(n))
    if n == 0: return "Zero Rupees Only"
    ones = ["","One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"]
    tens = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"]
    def two(x):
        if x < 20: return ones[x]
        return tens[x//10] + (" " + ones[x%10] if x%10 else "")
    def three(x):
        h, r = divmod(x, 100)
        s = (ones[h] + " Hundred" + (" " + two(r) if r else "")) if h else two(r)
        return s
    parts = []
    crore = n // 10000000; n %= 10000000
    lakh  = n // 100000;   n %= 100000
    thou  = n // 1000;     n %= 1000
    rest  = n
    if crore: parts.append(three(crore) + " Crore")
    if lakh:  parts.append(two(lakh) + " Lakh")
    if thou:  parts.append(two(thou) + " Thousand")
    if rest:  parts.append(three(rest))
    return " ".join(parts) + " Rupees Only"

@api.post("/receipts")
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

@api.get("/receipts")
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

@api.get("/receipts/{rid}")
async def get_receipt(rid: str, user = Depends(get_current_user)):
    r = await db.receipts.find_one({"id": rid}, {"_id":0})
    if not r: raise HTTPException(404, "Not found")
    return r

@api.post("/receipts/{rid}/reprint")
async def reprint_receipt(rid: str, user = Depends(get_current_user)):
    r = await db.receipts.find_one({"id": rid})
    if not r: raise HTTPException(404, "Not found")
    await db.receipts.update_one({"id": rid}, {"$inc": {"reprint_count": 1}, "$set":{"last_reprint_at": now_iso(), "last_reprint_by": user["name"]}})
    await audit(user, "reprint", "receipt", rid, {"number": r["number"]})
    return {"ok": True}

@api.post("/receipts/{rid}/cancel")
async def cancel_receipt(rid: str, body: Dict[str, str], user = Depends(require_roles("administrator","manager"))):
    reason = body.get("reason","").strip()
    if not reason: raise HTTPException(400, "Reason required")
    r = await db.receipts.find_one({"id": rid})
    if not r: raise HTTPException(404, "Not found")
    await db.receipts.update_one({"id": rid}, {"$set":{"status":"cancelled","cancel_reason": reason,"cancelled_at": now_iso(),"cancelled_by": user["name"]}})
    await audit(user, "cancel", "receipt", rid, {"reason": reason})
    return {"ok": True}

# ---------------- Adjustments ----------------
@api.post("/adjustments")
async def create_adjustment(body: AdjustmentIn, user = Depends(require_roles("administrator","manager","accountant","cashier"))):
    aid = gen_id()
    doc = {"id": aid, **body.model_dump(), "status":"pending", "requested_by": user["id"], "requested_by_name": user["name"], "created_at": now_iso()}
    await db.adjustments.insert_one(doc)
    await audit(user, "create", "adjustment", aid, {"amount": body.amount, "type": body.adjustment_type})
    return {k:v for k,v in doc.items() if k != "_id"}

@api.get("/adjustments")
async def list_adjustments(status: Optional[str] = None, user = Depends(get_current_user)):
    q = {"status": status} if status else {}
    return await db.adjustments.find(q, {"_id":0}).sort("created_at", -1).to_list(500)

@api.post("/adjustments/{aid}/approve")
async def approve_adjustment(aid: str, user = Depends(require_roles("administrator","manager"))):
    adj = await db.adjustments.find_one({"id": aid})
    if not adj: raise HTTPException(404, "Not found")
    # Waiver cap from settings (default ₹5,000)
    settings = await get_settings_doc()
    cap = float(settings.get("manager_waiver_cap", 5000) or 5000)
    if user["role"] == "manager" and float(adj.get("amount", 0)) > cap:
        raise HTTPException(403, f"Adjustments over ₹{int(cap):,} require administrator approval")
    await db.adjustments.update_one({"id": aid}, {"$set":{"status":"approved","approved_by": user["id"],"approved_by_name": user["name"],"approved_at": now_iso()}})
    await audit(user, "approve", "adjustment", aid, {"amount": adj.get("amount")})
    return {"ok": True}

@api.get("/public/student-lookup/{admission_no}")
async def public_student_lookup(admission_no: str):
    """View-only ledger for a student — used by Fee Notice QR. Includes siblings under same guardian_mobile."""
    s = await db.students.find_one({"admission_no": admission_no}, {"_id": 0})
    if not s: raise HTTPException(404, "Student not found")
    guardian_mobile = s.get("guardian_mobile")
    # Find siblings sharing the same guardian_mobile (if provided)
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
        paid = sum(x.get("total", 0) for x in receipts if x.get("receipt_type") not in ("refund", "debit_voucher"))
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

@api.post("/adjustments/{aid}/reject")
async def reject_adjustment(aid: str, body: Dict[str,str], user = Depends(require_roles("administrator","manager"))):
    await db.adjustments.update_one({"id": aid}, {"$set":{"status":"rejected","reject_reason": body.get("reason",""),"approved_by_name": user["name"],"approved_at": now_iso()}})
    await audit(user, "reject", "adjustment", aid)
    return {"ok": True}

# ---------------- Extensions ----------------
@api.post("/extensions")
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

@api.get("/extensions")
async def list_extensions(status: Optional[str] = None, student_id: Optional[str] = None, user = Depends(get_current_user)):
    q = {}
    if status: q["status"] = status
    if student_id: q["student_id"] = student_id
    return await db.extensions.find(q, {"_id":0}).sort("created_at", -1).to_list(500)

@api.post("/extensions/{eid}/approve")
async def approve_extension(eid: str, user = Depends(require_roles("administrator","manager"))):
    ext = await db.extensions.find_one({"id": eid})
    if not ext: raise HTTPException(404, "Not found")
    await db.extensions.update_one({"id": eid}, {"$set":{"status":"approved","approved_by_name": user["name"],"approved_at": now_iso()}})
    # Materialize reminders for each installment
    for idx, inst in enumerate(ext.get("installments", [])):
        await db.reminders.insert_one({
            "id": gen_id(), "extension_id": eid, "student_id": ext["student_id"],
            "installment_index": idx, "installment_name": inst.get("name") or f"Installment {idx+1}",
            "amount": float(inst.get("amount",0)), "due_date": inst.get("due_date"),
            "status": "pending", "created_at": now_iso(),
        })
    await audit(user, "approve", "extension", eid)
    return {"ok": True}

@api.post("/extensions/{eid}/reject")
async def reject_extension(eid: str, body: Dict[str,str], user = Depends(require_roles("administrator","manager"))):
    await db.extensions.update_one({"id": eid}, {"$set":{"status":"rejected","reject_reason": body.get("reason",""),"approved_by_name": user["name"],"approved_at": now_iso()}})
    await audit(user, "reject", "extension", eid)
    return {"ok": True}

# ---------------- Reminders ----------------
@api.get("/reminders")
async def list_reminders(status: str = "pending", user = Depends(get_current_user)):
    reminders = await db.reminders.find({"status": status}, {"_id":0}).to_list(1000)
    # enrich with student info
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

@api.post("/reminders/followup")
async def add_followup(body: ReminderFollowupIn, user = Depends(get_current_user)):
    r = await db.reminders.find_one({"id": body.reminder_id})
    if not r: raise HTTPException(404, "Not found")
    followup = {"id": gen_id(), "remark_type": body.remark_type, "details": body.details, "by": user["name"], "at": now_iso()}
    await db.reminders.update_one({"id": body.reminder_id}, {"$push":{"followups": followup}, "$set":{"last_followup_at": now_iso()}})
    if body.remark_type == "payment_received":
        await db.reminders.update_one({"id": body.reminder_id}, {"$set":{"status":"paid"}})
    await audit(user, "followup", "reminder", body.reminder_id, {"type": body.remark_type})
    return {"ok": True}

# ---------------- Dashboard / Reports ----------------
@api.get("/dashboard")
async def dashboard(user = Depends(get_current_user)):
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    receipts_today_cursor = db.receipts.find({"created_at":{"$gte": today}, "status":{"$ne":"cancelled"}}, {"_id":0})
    receipts_today = await receipts_today_cursor.to_list(2000)
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

@api.get("/reports/collection")
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
    by_mode: Dict[str,float] = {}
    by_type: Dict[str,float] = {}
    for r in rows:
        if r.get("receipt_type") in ("refund","debit_voucher"): continue
        by_mode[r.get("payment_mode","-")] = by_mode.get(r.get("payment_mode","-"),0) + r.get("total",0)
        by_type[r.get("receipt_type","-")] = by_type.get(r.get("receipt_type","-"),0) + r.get("total",0)
    return {"rows": rows, "gross_collection": total, "refunds": refund, "vouchers": vouchers,
            "net": total - refund - vouchers, "by_mode": by_mode, "by_type": by_type, "count": len(rows)}

@api.get("/reports/audit")
async def audit_report(limit: int = 500, user = Depends(require_roles("administrator","manager","accountant"))):
    return await db.audit_log.find({}, {"_id":0}).sort("timestamp",-1).limit(limit).to_list(limit)

@api.get("/reports/cancellations")
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

@api.get("/reports/concessions")
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
    # Enrich with student
    sids = list({r["student_id"] for r in rows if r.get("student_id")})
    students = {s["id"]: s for s in await db.students.find({"id":{"$in": sids}}, {"_id":0}).to_list(len(sids) or 1)}
    if department_id:
        rows = [r for r in rows if students.get(r.get("student_id"), {}).get("department_id") == department_id]
    for r in rows:
        r["student"] = students.get(r.get("student_id"))
    total = sum(r.get("amount", 0) for r in rows)
    by_type: Dict[str, float] = {}
    by_month: Dict[str, float] = {}
    for r in rows:
        t = r.get("adjustment_type","-")
        by_type[t] = by_type.get(t, 0) + r.get("amount", 0)
        m = (r.get("approved_at") or "")[:7]
        by_month[m] = by_month.get(m, 0) + r.get("amount", 0)
    return {"rows": rows, "count": len(rows), "total": total, "by_type": by_type, "by_month": by_month}

# ---------------- Student Promotion ----------------
@api.post("/students/promote")
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
        upd["fee_structure_id"] = None  # clear so office reassigns
    for s in students:
        await db.students.update_one({"id": s["id"]}, {"$set": upd, "$push": {"promotion_history": {"from_class_id": body.from_class_id, "to_class_id": body.to_class_id, "at": now_iso(), "by": user["name"], "academic_year": body.new_academic_year}}})
    await audit(user, "promote", "class", body.to_class_id, {"count": len(students), "from": from_cls["name"], "to": to_cls["name"]})
    return {"promoted": len(students), "from_class": from_cls["name"], "to_class": to_cls["name"]}

@api.post("/fee-structures/rollover")
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
    # Also bump departments' current academic_year to the new one
    await db.departments.update_many({"academic_year": body.from_academic_year}, {"$set": {"academic_year": body.to_academic_year}})
    await audit(user, "rollover", "fee_structure", "", {"from": body.from_academic_year, "to": body.to_academic_year, "created": created})
    return {"created": created, "from": body.from_academic_year, "to": body.to_academic_year}

@api.post("/fee-structures/seed-2026")
async def seed_2026_fee_structures(user = Depends(require_roles("administrator","manager"))):
    """Auto-load the 29 class fee structures from /app/memory/fee_structure_2026.json"""
    import json as _json
    rows: List[dict] = []
    try:
        with open("/app/memory/fee_structure_2026.json", "r") as f:
            rows = _json.load(f)
    except Exception as e:
        raise HTTPException(500, f"Cannot read seed file: {e}")

    # Ensure fee heads exist
    fee_head_names = ["Admission Fee", "Continuation Fee", "Tuition Q1", "Tuition Q2", "Tuition Q3", "Term Fees", "Tuition Fee", "Practical Fee"]
    fh_by_name: Dict[str, dict] = {fh["name"]: fh for fh in await db.fee_heads.find({}, {"_id":0}).to_list(200)}
    for nm in fee_head_names:
        if nm not in fh_by_name:
            code = nm.replace(" ","_").upper()[:8]
            fh = {"id": gen_id(), "name": nm, "code": code, "category": "school", "created_at": now_iso()}
            await db.fee_heads.insert_one(fh); fh_by_name[nm] = fh

    depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(50)}

    def pick_dept(class_name: str, medium: str) -> Optional[dict]:
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
        # Ensure class exists (unique by dept + name + medium)
        cls = await db.classes.find_one({"department_id": d["id"], "name": cname, "medium": medium}, {"_id":0})
        if not cls:
            cls = {"id": gen_id(), "department_id": d["id"], "name": cname, "medium": medium, "created_at": now_iso()}
            await db.classes.insert_one(cls); created_classes += 1
        # Skip if a structure already exists
        existing_fs = await db.fee_structures.find_one({"class_id": cls["id"], "academic_year": ay})
        if existing_fs:
            skipped += 1; continue
        items = []
        total = 0
        for k, v in fees.items():
            if not isinstance(v, (int, float)) or v <= 0: continue
            if k == "Total" or k == "Total Fees": continue
            fh = fh_by_name.get(k) or fh_by_name.get(k.replace(" ", ""))
            if not fh:
                # Create ad-hoc fee head
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

# ---------------- Bus Routes ----------------
@api.get("/bus-routes")
async def list_bus_routes(user = Depends(get_current_user)):
    return await db.bus_routes.find({}, {"_id":0}).sort("name", 1).to_list(200)

@api.post("/bus-routes")
async def create_bus_route(body: BusRouteIn, user = Depends(require_roles("administrator","manager","accountant"))):
    if await db.bus_routes.find_one({"code": body.code}):
        raise HTTPException(400, "Route code already exists")
    rid = gen_id()
    doc = {"id": rid, **body.model_dump(), "created_at": now_iso()}
    await db.bus_routes.insert_one(doc)
    await audit(user, "create", "bus_route", rid, {"code": body.code})
    return {k:v for k,v in doc.items() if k != "_id"}

@api.patch("/bus-routes/{rid}")
async def update_bus_route(rid: str, body: Dict[str, Any], user = Depends(require_roles("administrator","manager","accountant"))):
    allowed = {k: v for k, v in body.items() if k in ("name","driver_name","driver_mobile","vehicle_no","monthly_fee","stops","active")}
    await db.bus_routes.update_one({"id": rid}, {"$set": allowed})
    await audit(user, "update", "bus_route", rid, allowed)
    return {"ok": True}

@api.get("/bus-routes/{rid}/roster")
async def bus_route_roster(rid: str, month: Optional[str] = None, user = Depends(get_current_user)):
    route = await db.bus_routes.find_one({"id": rid}, {"_id":0})
    if not route: raise HTTPException(404, "Route not found")
    students = await db.students.find({"bus_route": route["code"], "status":"active"}, {"_id":0}).to_list(2000)
    m = month or date.today().isoformat()[:7]  # YYYY-MM
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

# ---------------- Fee Notices (Outstanding) ----------------
@api.get("/notices/outstanding")
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
    # Bus routes map by code (students carry bus_route = route.code)
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
        # Bus fee: if student has bus_route, add route monthly_fee x bus_months
        bus_route = route_map.get(s.get("bus_route")) if s.get("bus_route") else None
        bus_fee_annual = float(bus_route.get("monthly_fee", 0)) * bus_months if bus_route else 0
        total_fee = academic_fee + bus_fee_annual
        paid = paid_by.get(s["id"], 0)
        refund = refund_by.get(s["id"], 0)
        adjusted = adj_by.get(s["id"], 0)
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

# ---------------- Seed ----------------
async def seed_data():
    await db.users.create_index("email", unique=True)
    await db.students.create_index("admission_no", unique=True)
    await db.receipts.create_index("number", unique=True)
    await db.counters.create_index("key", unique=True)

    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": gen_id(), "email": admin_email, "password_hash": hash_password(admin_pw),
            "name": os.environ.get("ADMIN_NAME","Administrator"), "role": "administrator",
            "active": True, "created_at": now_iso(),
        })
    else:
        if not verify_password(admin_pw, existing["password_hash"]):
            await db.users.update_one({"email": admin_email}, {"$set":{"password_hash": hash_password(admin_pw)}})

    # Seed staff demo users (only if not exist)
    demo_users = [
        ("cashier@balajiconvent.in","cashier123","Ravi Cashier","cashier"),
        ("accountant@balajiconvent.in","account123","Sunita Accountant","accountant"),
        ("manager@balajiconvent.in","manager123","Anil Manager","manager"),
    ]
    # Migrate any legacy .local demo emails to the new valid domain
    for old_em, new_em in [
        ("cashier@balaji.local","cashier@balajiconvent.in"),
        ("accountant@balaji.local","accountant@balajiconvent.in"),
        ("manager@balaji.local","manager@balajiconvent.in"),
    ]:
        legacy = await db.users.find_one({"email": old_em})
        if legacy:
            if await db.users.find_one({"email": new_em}):
                await db.users.delete_one({"email": old_em})
            else:
                await db.users.update_one({"email": old_em}, {"$set": {"email": new_em}})
    for em, pw, nm, rl in demo_users:
        if not await db.users.find_one({"email": em}):
            await db.users.insert_one({"id": gen_id(),"email": em,"password_hash": hash_password(pw),"name": nm,"role": rl,"active": True,"created_at": now_iso()})

    if await db.departments.count_documents({}) == 0:
        depts = [
            {"name":"English Primary","code":"EP","header_line1":"BALAJI CONVENT","header_line2":"ENGLISH PRIMARY SCHOOL"},
            {"name":"Marathi Primary","code":"MP","header_line1":"BALAJI CONVENT","header_line2":"MARATHI PRIMARY SCHOOL"},
            {"name":"Secondary","code":"SEC","header_line1":"BALAJI CONVENT SECONDARY SCHOOL","header_line2":"SELF FINANCING"},
            {"name":"Junior College","code":"JC","header_line1":"BALAJI CONVENT JR. COLLEGE","header_line2":"ARTS, COMMERCE, SCIENCE & BI-FOCAL"},
        ]
        for d in depts:
            await db.departments.insert_one({"id": gen_id(), **d, "academic_year":"2026-27", "created_at": now_iso()})
    else:
        # Migration: add header_line1/2 defaults if missing
        header_defaults = {
            "EP": ("BALAJI CONVENT", "ENGLISH PRIMARY SCHOOL"),
            "MP": ("BALAJI CONVENT", "MARATHI PRIMARY SCHOOL"),
            "SEC": ("BALAJI CONVENT SECONDARY SCHOOL", "SELF FINANCING"),
            "JC": ("BALAJI CONVENT JR. COLLEGE", "ARTS, COMMERCE, SCIENCE & BI-FOCAL"),
        }
        for code, (h1, h2) in header_defaults.items():
            await db.departments.update_one(
                {"code": code, "$or": [{"header_line1": {"$exists": False}}, {"header_line1": None}, {"header_line1": ""}]},
                {"$set": {"header_line1": h1, "header_line2": h2}},
            )

    if await db.fee_heads.count_documents({}) == 0:
        heads = [
            ("Tuition Fee","TUIT","school"),
            ("Exam Fee","EXAM","school"),
            ("Activity Fee","ACT","school"),
            ("Library Fee","LIB","school"),
            ("Admission Fee","ADM","admission"),
            ("Registration Fee","REG","admission"),
            ("Bus Fee","BUS","bus"),
            ("Uniform","UNI","misc"),
            ("Books","BOOK","misc"),
            ("Donation","DON","general"),
        ]
        for nm, cd, cat in heads:
            await db.fee_heads.insert_one({"id": gen_id(),"name": nm,"code": cd,"category": cat,"created_at": now_iso()})

    if await db.classes.count_documents({}) == 0:
        depts = await db.departments.find({}, {"_id":0}).to_list(100)
        by_code = {d["code"]: d for d in depts}
        specs = {
            "EP": ["Nursery","LKG","UKG","Class 1","Class 2","Class 3","Class 4","Class 5"],
            "MP": ["Class 1","Class 2","Class 3","Class 4","Class 5"],
            "SEC": ["Class 6","Class 7","Class 8","Class 9","Class 10"],
            "JC": ["Class 11 - Science","Class 11 - Commerce","Class 12 - Science","Class 12 - Commerce"],
        }
        for code, classes in specs.items():
            d = by_code.get(code)
            if not d: continue
            for nm in classes:
                await db.classes.insert_one({"id": gen_id(),"department_id": d["id"],"name": nm,"created_at": now_iso()})

    # Sample students
    if await db.students.count_documents({}) == 0:
        classes = await db.classes.find({}, {"_id":0}).to_list(500)
        samples = [
            ("BC-EP-001","Aarav Sharma","EP","Class 3","Rajesh Sharma","9876500001"),
            ("BC-EP-002","Ishita Patil","EP","Class 5","Suresh Patil","9876500002"),
            ("BC-MP-001","Rohan Deshmukh","MP","Class 4","Prakash Deshmukh","9876500003"),
            ("BC-SEC-001","Priya Verma","SEC","Class 9","Manoj Verma","9876500004"),
            ("BC-SEC-002","Karan Joshi","SEC","Class 10","Nitin Joshi","9876500005"),
            ("BC-JC-001","Anjali Kulkarni","JC","Class 12 - Science","Vinod Kulkarni","9876500006"),
        ]
        depts = {d["code"]: d for d in await db.departments.find({}, {"_id":0}).to_list(100)}
        for adm, name, dcode, cname, gname, gmob in samples:
            d = depts[dcode]
            cls = next((c for c in classes if c["department_id"]==d["id"] and c["name"]==cname), None)
            if not cls: continue
            await db.students.insert_one({
                "id": gen_id(),"admission_no": adm,"name": name,
                "department_id": d["id"], "class_id": cls["id"],
                "guardian_name": gname, "guardian_mobile": gmob, "status":"active",
                "created_at": now_iso(),
            })

@app.on_event("startup")
async def on_startup():
    await seed_data()

# ---------------- Cron: Quarterly Reminders ----------------
async def _generate_quarterly_reminders() -> Dict[str, int]:
    """For each active student with a fee structure containing Tuition Q1/Q2/Q3 that isn't paid,
    create a pending reminder if we're within reminder_lead_days of the quarter's due date."""
    settings = await get_settings_doc()
    lead = int(settings.get("reminder_lead_days", 7) or 7)
    quarters = [
        ("Q1", settings.get("q1_due_date")),
        ("Q2", settings.get("q2_due_date")),
        ("Q3", settings.get("q3_due_date")),
    ]
    today = date.today()
    quarters = [(q, d) for q, d in quarters if d]
    if not quarters: return {"created": 0, "skipped": 0}

    students = await db.students.find({"status": "active", "fee_structure_id": {"$ne": None}}, {"_id": 0}).to_list(10000)
    if not students: return {"created": 0, "skipped": 0}
    fs_ids = list({s.get("fee_structure_id") for s in students if s.get("fee_structure_id")})
    fs_map = {f["id"]: f for f in await db.fee_structures.find({"id": {"$in": fs_ids}}, {"_id": 0}).to_list(500)}
    # Existing paid quarter map: student_id -> set of paid quarters
    sids = [s["id"] for s in students]
    receipts = await db.receipts.find({"student_id": {"$in": sids}, "status": {"$ne": "cancelled"}, "receipt_type": {"$in": ["school", "admission"]}}, {"_id": 0}).to_list(20000)
    paid_q: Dict[str, set] = {}
    for r in receipts:
        for line in r.get("lines", []):
            nm = (line.get("fee_head_name") or "").lower()
            for tag in ("q1", "q2", "q3"):
                if tag in nm:
                    paid_q.setdefault(r["student_id"], set()).add(tag.upper())
    created, skipped = 0, 0
    for s in students:
        fs = fs_map.get(s["fee_structure_id"])
        if not fs: continue
        for q_label, q_due in quarters:
            try:
                due = datetime.strptime(q_due, "%Y-%m-%d").date()
            except Exception:
                continue
            # Only within lead window (either today ≤ due OR overdue up to 60 days)
            days_to = (due - today).days
            if days_to > lead: continue
            if days_to < -60: continue
            # Skip if paid
            if q_label in paid_q.get(s["id"], set()): continue
            # Compute amount from fee structure
            amt = 0
            for it in fs.get("items", []):
                nm = (it.get("fee_head_name") or "").lower()
                if q_label.lower() in nm: amt += float(it.get("amount", 0))
            if amt <= 0: continue
            # Idempotency
            key = f"tuition-{q_label}-{q_due}"
            exists = await db.reminders.find_one({"student_id": s["id"], "key": key})
            if exists:
                skipped += 1; continue
            await db.reminders.insert_one({
                "id": gen_id(), "key": key, "student_id": s["id"],
                "installment_name": f"Tuition {q_label}", "amount": amt,
                "due_date": q_due, "status": "pending",
                "auto_generated": True, "created_at": now_iso(),
            })
            created += 1
    return {"created": created, "skipped": skipped}

@api.post("/cron/quarterly-reminders")
async def cron_quarterly_reminders(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing auth")
    import hmac
    expected = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not expected or not hmac.compare_digest(auth[7:], expected):
        raise HTTPException(401, "Invalid cron secret")
    # Ack fast + run in background
    import asyncio
    asyncio.create_task(_generate_quarterly_reminders())
    return {"accepted": True}

@api.post("/reminders/generate-quarterly")
async def manual_generate_quarterly(user = Depends(require_roles("administrator","manager","accountant"))):
    """Manual trigger for admin — generates reminders synchronously and returns the count."""
    result = await _generate_quarterly_reminders()
    await audit(user, "generate_quarterly_reminders", "reminder", "", result)
    return result

# ---------------- Public Scan-to-Lookup (no auth) ----------------
@api.get("/public/lookup/{number}")
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
            # Ledger summary (no cashier / auditor info)
            receipts = await db.receipts.find({"student_id": s["id"], "status": {"$ne": "cancelled"}},
                                              {"_id": 0, "cashier_id": 0}).sort("created_at", -1).to_list(200)
            fs = None
            if s.get("fee_structure_id"):
                fs = await db.fee_structures.find_one({"id": s["fee_structure_id"]}, {"_id": 0})
            paid = sum(x.get("total", 0) for x in receipts if x.get("receipt_type") not in ("refund", "debit_voucher"))
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

# ---------------- Fee Defaulters Report ----------------
@api.get("/reports/defaulters")
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
    # Paid amount per (student_id, quarter)
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

@api.get("/reports/day-end")
async def day_end_report(
    date: Optional[str] = None,
    cashier_id: Optional[str] = None,
    user = Depends(get_current_user),
):
    """One-tap cashier day-end summary. date = YYYY-MM-DD (defaults to today, IST-agnostic UTC).
    If cashier_id omitted → current user for cashier role; admins/managers see all cashiers grouped."""
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
            if rt == "refund" or rt == "debit_voucher":
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
        # single cashier report
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
        # group by cashier
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
        payload.update(agg_of(receipts))  # grand totals
    return payload

@app.on_event("shutdown")
async def on_shutdown():
    client.close()

app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS','*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
