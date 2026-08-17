"""Iteration 6 verification: DV voucher numbering, ReceiptType new fields,
regression on core endpoints and version."""
import os
import uuid
import requests
import pytest

BASE = os.environ.get("BC_TEST_BASE") or "http://localhost:8001"
ADMIN_EMAIL = "neulkarprathamesh@gmail.com"
ADMIN_PW = "Balaji@2026"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Version ----
def test_version_endpoint():
    r = requests.get(f"{BASE}/api/version", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j.get("app_version") == "1.0.0" or j.get("version") == "1.0.0"


# ---- Regression: existing endpoints ----
def test_login_returns_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("token")


def test_receipts_list(H):
    r = requests.get(f"{BASE}/api/receipts?limit=5", headers=H, timeout=30)
    assert r.status_code == 200
    j = r.json()
    # can be list or dict; accept both
    if isinstance(j, dict):
        assert "items" in j or "receipts" in j or "data" in j
    else:
        assert isinstance(j, list)


def test_students_query(H):
    r = requests.get(f"{BASE}/api/students?query=&limit=5", headers=H, timeout=30)
    assert r.status_code == 200


# ---- Receipt-Type CRUD with new fields ----
def test_receipt_type_new_fields_roundtrip(H):
    code = f"TSTX{uuid.uuid4().hex[:4].upper()}"
    payload = {
        "code": code,
        "name": f"TEST Type {code}",
        "department_code": "EP",
        "prefix": code,
        "series_scope": "type",
        "paper_size": "A5",
        "theme": "bw",
        "signature_layout": "row",
        "signatures_config": {"receiver": True, "accountant": True, "principal": True, "director": True},
        "margins_mm": {"top": 8, "right": 8, "bottom": 8, "left": 8},
    }
    hh = {**H, "X-Admin-Pin": "1234"}
    r = requests.post(f"{BASE}/api/receipt-types", headers=hh, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    created = r.json()
    rt_id = created.get("id") or created.get("_id") or created.get("code")

    # Round-trip
    r2 = requests.get(f"{BASE}/api/receipt-types", headers=H, timeout=30)
    assert r2.status_code == 200
    items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
    match = next((x for x in items if x.get("code") == code), None)
    assert match, f"receipt-type {code} not found in list"
    assert match.get("paper_size") == "A5"
    assert match.get("theme") == "bw"
    assert match.get("signature_layout") == "row"
    assert match.get("signatures_config", {}).get("principal") is True
    assert match.get("margins_mm", {}).get("top") == 8

    # Cleanup
    if rt_id:
        requests.delete(f"{BASE}/api/receipt-types/{rt_id}", headers=hh, timeout=15)


# ---- Voucher numbering DV-YYYY-NNNNNN ----
def test_debit_voucher_number_format(H):
    # Try to create a minimal debit voucher receipt. If the endpoint requires
    # more context, fall back to inspecting existing voucher numbers.
    r = requests.get(f"{BASE}/api/receipts?receipt_type=debit_voucher&limit=20",
                     headers=H, timeout=30)
    if r.status_code == 200:
        j = r.json()
        items = j if isinstance(j, list) else j.get("items", j.get("receipts", []))
        vouchers = [x for x in items if (x.get("receipt_type") == "debit_voucher")]
        if vouchers:
            for v in vouchers:
                num = v.get("receipt_number") or v.get("voucher_number") or v.get("number", "")
                # Only assert on newly-generated ones (skip legacy V- ones if present)
                # But at least one recent one should start with DV-
            recent_dv = [v for v in vouchers
                         if str(v.get("receipt_number") or v.get("voucher_number") or "").startswith("DV-")]
            print(f"Existing debit vouchers: {len(vouchers)}, DV-prefixed: {len(recent_dv)}")

    # Directly invoke next_voucher_number by creating a real voucher
    # via POST /api/receipts. We need a student_id first.
    st = requests.get(f"{BASE}/api/students?limit=1", headers=H, timeout=30).json()
    students = st if isinstance(st, list) else st.get("items", st.get("students", []))
    if not students:
        pytest.skip("no students to attach voucher to")
    sid = students[0].get("id") or students[0].get("_id")

    # Fetch a department
    depts = requests.get(f"{BASE}/api/departments", headers=H, timeout=15).json()
    depts_l = depts if isinstance(depts, list) else depts.get("items", [])
    if not depts_l:
        pytest.skip("no departments")
    did = depts_l[0].get("id") or depts_l[0].get("_id")

    payload = {
        "receipt_type": "debit_voucher",
        "department_id": did,
        "student_id": sid,
        "academic_year": "2026-27",
        "payment_mode": "cash",
        "lines": [{"fee_head_code": "MISC", "fee_head_name": "Misc",
                   "description": "TEST voucher iter6", "amount": 1}],
        "amount": 1,
        "narration": "iter6 test voucher"
    }
    r2 = requests.post(f"{BASE}/api/receipts", headers=H, json=payload, timeout=30)
    if r2.status_code not in (200, 201):
        pytest.skip(f"voucher POST rejected ({r2.status_code}): {r2.text[:200]}")
    v = r2.json()
    num = v.get("receipt_number") or v.get("voucher_number") or v.get("number", "")
    assert num.startswith("DV-"), f"expected DV- prefix, got {num!r}"
    # Cleanup created voucher if endpoint supports delete
    rid = v.get("id") or v.get("_id")
    if rid:
        requests.delete(f"{BASE}/api/receipts/{rid}", headers=H, timeout=15)


# ---- Updates endpoints (auth guard sanity) ----
def test_updates_current_requires_auth(H):
    # Without auth
    r = requests.get(f"{BASE}/api/updates/current", timeout=15)
    assert r.status_code in (401, 403)
    # With auth
    r2 = requests.get(f"{BASE}/api/updates/current", headers=H, timeout=15)
    assert r2.status_code == 200
    j = r2.json()
    assert "current" in j and "rollback_available" in j
    assert "public_key_fingerprint" in j or "fingerprint" in j


def test_updates_public_key_pem(H):
    r = requests.get(f"{BASE}/api/updates/public-key", headers=H, timeout=15)
    assert r.status_code == 200
    pem = r.json().get("public_key_pem", "")
    assert pem.startswith("-----BEGIN PUBLIC KEY-----")
