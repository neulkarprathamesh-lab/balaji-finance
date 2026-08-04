"""Backend RBAC & feature tests for Balaji Convent Fee Software."""
import os
import pytest
import requests
from datetime import date, timedelta

BASE = os.environ.get('REACT_APP_BACKEND_URL', 'https://finance-hub-school.preview.emergentagent.com').rstrip('/')

CREDS = {
    "admin":      ("neulkarprathamesh@gmail.com", "Balaji@2026"),
    "cashier":    ("cashier@balajiconvent.in", "cashier123"),
    "accountant": ("accountant@balajiconvent.in", "account123"),
    "manager":    ("manager@balajiconvent.in", "manager123"),
}

TOKENS = {}


def _login(role):
    if role in TOKENS:
        return TOKENS[role]
    em, pw = CREDS[role]
    r = requests.post(f"{BASE}/api/auth/login", json={"email": em, "password": pw}, timeout=15)
    assert r.status_code == 200, f"{role} login failed: {r.status_code} {r.text}"
    tok = r.json()["token"]
    TOKENS[role] = tok
    return tok


def H(role):
    return {"Authorization": f"Bearer {_login(role)}", "Content-Type": "application/json"}


# ---------- 1. Auth ----------
@pytest.mark.parametrize("role", ["admin", "cashier", "accountant", "manager"])
def test_login(role):
    tok = _login(role)
    r = requests.get(f"{BASE}/api/auth/me", headers=H(role))
    assert r.status_code == 200
    data = r.json()
    expected_role = "administrator" if role == "admin" else role
    assert data["role"] == expected_role
    assert isinstance(tok, str) and len(tok) > 10


# ---------- helpers ----------
def _get_dept():
    r = requests.get(f"{BASE}/api/departments", headers=H("admin"))
    assert r.status_code == 200
    depts = r.json()
    return next(d for d in depts if d["code"] == "EP")


def _get_student():
    r = requests.get(f"{BASE}/api/students", headers=H("admin"))
    assert r.status_code == 200
    return r.json()[0]


# ---------- 2. Cashier creates school receipt ----------
def test_cashier_creates_school_receipt():
    dept = _get_dept()
    stu = _get_student()
    body = {
        "receipt_type": "school",
        "department_id": dept["id"],
        "student_id": stu["id"],
        "payment_mode": "cash",
        "lines": [{"fee_head_name": "Tuition Fee", "amount": 1000}],
    }
    r = requests.post(f"{BASE}/api/receipts", json=body, headers=H("cashier"))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["number"].startswith("EP-2026-")
    assert d["total"] == 1000
    assert d["receipt_type"] == "school"


# ---------- 3. Cashier cannot create refund ----------
def test_cashier_cannot_create_refund():
    dept = _get_dept()
    stu = _get_student()
    body = {"receipt_type": "refund", "department_id": dept["id"], "student_id": stu["id"],
            "lines": [{"fee_head_name": "Refund", "amount": 100}]}
    r = requests.post(f"{BASE}/api/receipts", json=body, headers=H("cashier"))
    assert r.status_code == 403


# ---------- 4. Manager can create refund ----------
def test_manager_creates_refund():
    dept = _get_dept()
    stu = _get_student()
    body = {"receipt_type": "refund", "department_id": dept["id"], "student_id": stu["id"],
            "lines": [{"fee_head_name": "Refund", "amount": 50}]}
    r = requests.post(f"{BASE}/api/receipts", json=body, headers=H("manager"))
    assert r.status_code == 200, r.text
    assert r.json()["receipt_type"] == "refund"


# ---------- 5. Debit voucher numbering V-YYYY-NNNNNN ----------
def test_debit_voucher_numbering():
    dept = _get_dept()
    body = {"receipt_type": "debit_voucher", "department_id": dept["id"],
            "payer_name": "Test Vendor",
            "lines": [{"fee_head_name": "Office Supplies", "amount": 500}]}
    r = requests.post(f"{BASE}/api/receipts", json=body, headers=H("manager"))
    assert r.status_code == 200, r.text
    num = r.json()["number"]
    assert num.startswith("V-2026-"), f"got {num}"
    assert len(num.split("-")[-1]) == 6


# ---------- 6. Adjustments RBAC ----------
def test_cashier_creates_adjustment_pending():
    stu = _get_student()
    body = {"student_id": stu["id"], "adjustment_type": "scholarship", "amount": 500, "reason": "Merit"}
    r = requests.post(f"{BASE}/api/adjustments", json=body, headers=H("cashier"))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "pending"
    # cashier cannot approve
    r2 = requests.post(f"{BASE}/api/adjustments/{d['id']}/approve", headers=H("cashier"))
    assert r2.status_code == 403
    # manager approves
    r3 = requests.post(f"{BASE}/api/adjustments/{d['id']}/approve", headers=H("manager"))
    assert r3.status_code == 200
    # verify
    r4 = requests.get(f"{BASE}/api/adjustments", headers=H("manager"))
    found = next((a for a in r4.json() if a["id"] == d["id"]), None)
    assert found and found["status"] == "approved"


# ---------- 7. Extension: sum must equal outstanding ----------
def test_extension_sum_mismatch_400():
    stu = _get_student()
    body = {"student_id": stu["id"], "outstanding_amount": 1000,
            "installments": [{"amount": 400, "due_date": "2026-02-01"},
                             {"amount": 400, "due_date": "2026-03-01"}]}
    r = requests.post(f"{BASE}/api/extensions", json=body, headers=H("cashier"))
    assert r.status_code == 400


def test_extension_approve_creates_reminders():
    stu = _get_student()
    today = date.today()
    body = {"student_id": stu["id"], "outstanding_amount": 1200,
            "installments": [
                {"amount": 400, "due_date": (today - timedelta(days=2)).isoformat()},  # overdue
                {"amount": 400, "due_date": today.isoformat()},  # today
                {"amount": 400, "due_date": (today + timedelta(days=1)).isoformat()},  # tomorrow
            ]}
    r = requests.post(f"{BASE}/api/extensions", json=body, headers=H("cashier"))
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    # cashier can't approve
    r2 = requests.post(f"{BASE}/api/extensions/{eid}/approve", headers=H("cashier"))
    assert r2.status_code == 403
    # manager approves
    r3 = requests.post(f"{BASE}/api/extensions/{eid}/approve", headers=H("manager"))
    assert r3.status_code == 200
    # reminders materialized
    r4 = requests.get(f"{BASE}/api/reminders?status=pending", headers=H("manager"))
    assert r4.status_code == 200
    rems = [x for x in r4.json() if x.get("extension_id") == eid]
    assert len(rems) == 3
    buckets = {r["bucket"] for r in rems}
    assert "overdue" in buckets and "today" in buckets and "tomorrow" in buckets
    # student enrichment
    assert all(r.get("student") for r in rems)
    # followup payment_received marks paid
    rem_id = rems[0]["id"]
    r5 = requests.post(f"{BASE}/api/reminders/followup",
                       json={"reminder_id": rem_id, "remark_type": "payment_received", "details": "paid"},
                       headers=H("cashier"))
    assert r5.status_code == 200
    r6 = requests.get(f"{BASE}/api/reminders?status=paid", headers=H("cashier"))
    assert any(x["id"] == rem_id for x in r6.json())


# ---------- 8. Receipt cancel & reprint ----------
def test_receipt_cancel_rbac_and_reprint():
    dept = _get_dept()
    stu = _get_student()
    body = {"receipt_type": "school", "department_id": dept["id"], "student_id": stu["id"],
            "lines": [{"fee_head_name": "Exam Fee", "amount": 200}]}
    r = requests.post(f"{BASE}/api/receipts", json=body, headers=H("cashier"))
    assert r.status_code == 200
    rid = r.json()["id"]
    # Cashier cannot cancel
    rc = requests.post(f"{BASE}/api/receipts/{rid}/cancel", json={"reason": "test"}, headers=H("cashier"))
    assert rc.status_code == 403
    # Reprint allowed for any user
    rp = requests.post(f"{BASE}/api/receipts/{rid}/reprint", headers=H("cashier"))
    assert rp.status_code == 200
    rp2 = requests.post(f"{BASE}/api/receipts/{rid}/reprint", headers=H("accountant"))
    assert rp2.status_code == 200
    rget = requests.get(f"{BASE}/api/receipts/{rid}", headers=H("cashier")).json()
    assert rget.get("reprint_count", 0) >= 2
    # Manager can cancel with reason
    rcm = requests.post(f"{BASE}/api/receipts/{rid}/cancel", json={"reason": "duplicate"}, headers=H("manager"))
    assert rcm.status_code == 200
    rget2 = requests.get(f"{BASE}/api/receipts/{rid}", headers=H("manager")).json()
    assert rget2["status"] == "cancelled"


# ---------- 9. Audit report RBAC ----------
def test_audit_report_rbac():
    r = requests.get(f"{BASE}/api/reports/audit", headers=H("cashier"))
    assert r.status_code == 403
    for role in ("accountant", "manager", "admin"):
        rr = requests.get(f"{BASE}/api/reports/audit", headers=H(role))
        assert rr.status_code == 200, f"{role} audit failed: {rr.status_code}"


# ---------- 10. Collection report defaults to today ----------
def test_collection_report_defaults_today():
    r = requests.get(f"{BASE}/api/reports/collection", headers=H("admin"))
    assert r.status_code == 200, r.text
    d = r.json()
    assert "rows" in d and "gross_collection" in d and "net" in d
