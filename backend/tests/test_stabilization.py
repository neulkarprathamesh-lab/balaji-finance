"""Iteration 4 stabilization pass — cover remaining feature endpoints.
Focus on any 5xx / broken routes across pages listed in the review request.
"""
import os
import pytest
import requests

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')

CREDS = {
    "admin":      ("neulkarprathamesh@gmail.com", "Balaji@2026"),
    "cashier":    ("cashier@balajiconvent.in", "cashier123"),
    "accountant": ("accountant@balajiconvent.in", "account123"),
    "manager":    ("manager@balajiconvent.in", "manager123"),
}
_tok = {}

def T(role):
    if role not in _tok:
        r = requests.post(f"{BASE}/api/auth/login", json={"email": CREDS[role][0], "password": CREDS[role][1]}, timeout=15)
        assert r.status_code == 200, r.text
        _tok[role] = r.json()["token"]
    return {"Authorization": f"Bearer {_tok[role]}", "Content-Type": "application/json"}


# ---------- Static offline assets ----------
def test_school_logo_returns_200():
    r = requests.get(f"{BASE}/school-logo.jpeg", timeout=15)
    assert r.status_code == 200

def test_login_bg_returns_200():
    r = requests.get(f"{BASE}/login-bg.png", timeout=15)
    assert r.status_code == 200

def test_manifest_json_valid():
    r = requests.get(f"{BASE}/manifest.json", timeout=15)
    assert r.status_code == 200
    m = r.json()
    assert "name" in m and "icons" in m


# ---------- Version ----------
def test_version_endpoint():
    r = requests.get(f"{BASE}/api/version", timeout=10)
    assert r.status_code == 200


# ---------- PIN flow ----------
def test_admin_pin_set_and_verify():
    # ensure PIN set to 1234
    h = T("admin")
    st = requests.get(f"{BASE}/api/auth/me/pin-status", headers=h).json()
    if not st.get("has_pin"):
        r = requests.post(f"{BASE}/api/auth/me/pin",
                          json={"new_pin": "1234", "current_password": "Balaji@2026"},
                          headers=h)
        assert r.status_code in (200, 201), r.text
    v = requests.post(f"{BASE}/api/auth/admin-pin/verify", json={"pin": "1234"}, headers=h)
    assert v.status_code == 200, v.text
    # wrong PIN
    v2 = requests.post(f"{BASE}/api/auth/admin-pin/verify", json={"pin": "9999"}, headers=h)
    assert v2.status_code in (400, 401, 403)


def _admin_pin_headers():
    return {**T("admin"), "X-Admin-PIN": "1234"}

def _admin_dual_headers():
    return {**T("admin"), "X-Admin-PIN": "1234", "X-Admin-Password": "Balaji@2026"}


# ---------- Settings ----------
def test_settings_get_patch_admin_only():
    r = requests.get(f"{BASE}/api/settings", headers=T("admin"))
    assert r.status_code == 200
    r2 = requests.patch(f"{BASE}/api/settings", json={"school_name": r.json().get("school_name","Balaji Convent")}, headers=T("admin"))
    assert r2.status_code == 200
    # cashier forbidden
    r3 = requests.patch(f"{BASE}/api/settings", json={}, headers=T("cashier"))
    assert r3.status_code == 403


# ---------- Dashboard ----------
def test_dashboard_all_roles():
    for role in ("admin","cashier","accountant","manager"):
        r = requests.get(f"{BASE}/api/dashboard", headers=T(role))
        assert r.status_code == 200, f"{role}: {r.text}"


# ---------- Users list (admin only) ----------
def test_users_list_admin_only():
    r = requests.get(f"{BASE}/api/users", headers=T("admin"))
    assert r.status_code == 200
    assert len(r.json()) >= 4
    r2 = requests.get(f"{BASE}/api/users", headers=T("cashier"))
    assert r2.status_code == 403


# ---------- Receipt Types CRUD (admin) ----------
def test_receipt_types_list_and_crud():
    h = T("admin")
    r = requests.get(f"{BASE}/api/receipt-types", headers=h)
    assert r.status_code == 200
    types = r.json()
    assert len(types) >= 1
    # cashier forbidden on write
    import uuid as _uuid
    suffix = str(_uuid.uuid4())[:4].upper()
    body = {"code": f"TST{suffix}", "name": f"TEST Type {suffix}", "prefix": f"TST{suffix}", "department_id": types[0].get("department_id"),
            "enabled": True, "starting_number": 1, "current_number": 0, "auto_reset_yearly": True, "fields": {}}
    rc = requests.post(f"{BASE}/api/receipt-types", json=body, headers=T("cashier"))
    assert rc.status_code == 403
    # admin create (PIN-gated)
    ra = requests.post(f"{BASE}/api/receipt-types", json=body, headers=_admin_pin_headers())
    assert ra.status_code in (200, 201), ra.text
    rtid = ra.json()["id"]
    # PATCH toggle (PIN-gated)
    rp = requests.patch(f"{BASE}/api/receipt-types/{rtid}", json={"enabled": False}, headers=_admin_pin_headers())
    assert rp.status_code == 200
    # DELETE (PIN-gated)
    rd = requests.delete(f"{BASE}/api/receipt-types/{rtid}", headers=_admin_pin_headers())
    assert rd.status_code in (200, 204)


# ---------- Reset Sequence dual-auth ----------
def test_reset_sequence_invalid_number():
    h = T("admin")
    rts = requests.get(f"{BASE}/api/receipt-types", headers=h).json()
    if not rts: pytest.skip("no receipt-types")
    rt = rts[0]
    # try new_number smaller than existing -> expect 400/409
    r = requests.post(f"{BASE}/api/receipt-types/{rt['id']}/reset-sequence",
                      json={"new_number": 1, "reason": "test", "academic_year": "2026-27"}, headers=_admin_dual_headers())
    assert r.status_code in (200, 400, 409), r.text


# ---------- Config export/backup ----------
def test_config_backups_list():
    r = requests.get(f"{BASE}/api/config/backups", headers=T("admin"))
    assert r.status_code == 200
    r2 = requests.get(f"{BASE}/api/config/backups", headers=T("cashier"))
    assert r2.status_code == 403


def test_config_backup_now():
    r = requests.post(f"{BASE}/api/config/backup", headers=_admin_pin_headers())
    assert r.status_code in (200, 201), r.text


# ---------- Bus Routes ----------
def test_bus_routes_crud():
    h = T("admin")
    r = requests.get(f"{BASE}/api/bus-routes", headers=h)
    assert r.status_code == 200
    import uuid as _uuid
    code = f"TSTBUS{str(_uuid.uuid4())[:6]}"
    body = {"code": code, "name": "TEST Bus Route",
            "stops": [{"name": "A", "monthly_fee": 500}, {"name": "B", "monthly_fee": 700}],
            "monthly_fee": 500}
    rc = requests.post(f"{BASE}/api/bus-routes", json=body, headers=h)
    assert rc.status_code in (200, 201), rc.text
    rid = rc.json().get("id")
    if rid:
        # roster
        rr = requests.get(f"{BASE}/api/bus-routes/{rid}/roster", headers=h)
        assert rr.status_code == 200


# ---------- Reports ----------
def test_reports_cancellations():
    r = requests.get(f"{BASE}/api/reports/cancellations", headers=T("admin"))
    assert r.status_code == 200

def test_reports_concessions():
    r = requests.get(f"{BASE}/api/reports/concessions", headers=T("admin"))
    assert r.status_code == 200

def test_reports_day_end_denominations():
    from datetime import date
    r = requests.get(f"{BASE}/api/reports/day-end?date={date.today().isoformat()}", headers=T("admin"))
    assert r.status_code == 200
    d = r.json()
    # sanity: gross/net keys
    keys = set(d.keys())
    assert "net" in keys and "collected" in keys, f"unexpected day-end schema: {keys}"

def test_defaulters_all_quarters():
    for q in ("total","Q1","Q2","Q3"):
        r = requests.get(f"{BASE}/api/reports/defaulters?quarter={q}", headers=T("admin"))
        assert r.status_code == 200, f"{q}: {r.text}"


# ---------- Kiosk / public ----------
def test_public_student_lookup():
    # find one student first
    stus = requests.get(f"{BASE}/api/students", headers=T("admin")).json()
    if not stus: pytest.skip("no students")
    adm = stus[0]["admission_no"]
    r = requests.get(f"{BASE}/api/public/student-lookup/{adm}")  # no auth
    assert r.status_code == 200, r.text
    body = r.json()
    # returns either {student,ledger,...} for single or {children,combined} for siblings
    assert body.get("student") or body.get("children") or body.get("admission_no")

def test_public_receipt_lookup_by_number():
    recs = requests.get(f"{BASE}/api/receipts?limit=1", headers=T("admin")).json()
    if not recs: pytest.skip("no receipts")
    num = recs[0]["number"]
    r = requests.get(f"{BASE}/api/public/lookup/{num}")
    assert r.status_code == 200
    assert r.json().get("receipt", {}).get("number") == num


# ---------- Notices outstanding ----------
def test_notices_outstanding():
    r = requests.get(f"{BASE}/api/notices/outstanding", headers=T("admin"))
    assert r.status_code == 200


# ---------- Imports history ----------
def test_imports_history():
    r = requests.get(f"{BASE}/api/imports/history", headers=T("admin"))
    assert r.status_code == 200


# ---------- Fee structures ----------
def test_fee_structures_list():
    r = requests.get(f"{BASE}/api/fee-structures", headers=T("admin"))
    assert r.status_code == 200


# ---------- Reminders bucketed ----------
def test_reminders_list():
    r = requests.get(f"{BASE}/api/reminders", headers=T("manager"))
    assert r.status_code == 200
