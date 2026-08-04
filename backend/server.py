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
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

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
    allowed = {k: v for k, v in body.items() if k in ("school_name","school_address","school_phone","school_email","receipt_footer","notice_footer","bus_annual_months")}
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
    """Body: {rows: [ {admission_no, name, department_code, class_name, guardian_name, guardian_mobile, ...} ]}"""
    rows = body.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise HTTPException(400, "rows must be a non-empty array")
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
            })
            created += 1
        except Exception as e:
            errors.append({"row": idx+1, "error": str(e)})
    await audit(user, "bulk_import", "student", "", {"created": created, "skipped": skipped, "errors": len(errors)})
    return {"created": created, "skipped": skipped, "errors": errors, "total": len(rows)}

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
    await db.adjustments.update_one({"id": aid}, {"$set":{"status":"approved","approved_by": user["id"],"approved_by_name": user["name"],"approved_at": now_iso()}})
    await audit(user, "approve", "adjustment", aid)
    return {"ok": True}

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
        "receipts_today_count": len([r for r in receipts_today if r.get("receipt_type") not in ("refund","debit_voucher")]),
        "pending_approvals": pending_adj + pending_ext,
        "pending_adjustments": pending_adj, "pending_extensions": pending_ext,
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
