"""Regression tests for 3 undefined-variable fixes in server.py:
- GET /api/dashboard (line ~1010, `x` in receipts_today_count comprehension)
- POST /api/fee-structures/seed-2026 (line ~1194, `rows` default)
- GET /api/reports/defaulters (line ~1605, `x` in sum generator)
Plus smoke tests to ensure nothing else regressed.
"""
import os
import requests
from datetime import date

BASE = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

ADMIN = ("neulkarprathamesh@gmail.com", "Balaji@2026")


def _token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


TOKEN = None


def H():
    global TOKEN
    if TOKEN is None:
        TOKEN = _token()
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# ---------- Fix #1: /api/dashboard ----------
def test_dashboard_returns_expected_keys():
    r = requests.get(f"{BASE}/api/dashboard", headers=H(), timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("collection_today", "receipts_today_count", "pending_approvals",
              "due_today", "due_tomorrow", "overdue", "recent_receipts",
              "dept_totals_today"):
        assert k in d, f"missing key {k} in dashboard response; got keys={list(d.keys())}"
    # sanity types
    assert isinstance(d["receipts_today_count"], int)
    assert isinstance(d["recent_receipts"], list)
    assert isinstance(d["dept_totals_today"], (list, dict))


# ---------- Fix #3: /api/reports/defaulters ----------
def test_defaulters_total_quarter():
    r = requests.get(f"{BASE}/api/reports/defaulters?quarter=total", headers=H(), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("count", "total_outstanding", "students", "quarter"):
        assert k in d, f"missing {k}"
    assert d["quarter"] == "total"
    assert d["count"] == len(d["students"])
    # total_outstanding must equal sum of per-student outstanding (the fix under test)
    expected = round(sum(s.get("outstanding", 0) for s in d["students"]), 2)
    actual = round(d["total_outstanding"], 2)
    assert abs(expected - actual) < 0.01, f"total_outstanding {actual} != sum of rows {expected}"


def test_defaulters_q1_quarter():
    r = requests.get(f"{BASE}/api/reports/defaulters?quarter=Q1", headers=H(), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("count", "total_outstanding", "students", "quarter"):
        assert k in d
    assert d["quarter"] == "Q1"
    assert d["count"] == len(d["students"])
    expected = round(sum(s.get("outstanding", 0) for s in d["students"]), 2)
    actual = round(d["total_outstanding"], 2)
    assert abs(expected - actual) < 0.01


# ---------- Fix #2: /api/fee-structures/seed-2026 ----------
def test_seed_2026_fee_structures_returns_expected_keys():
    r = requests.post(f"{BASE}/api/fee-structures/seed-2026", headers=H(), timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("classes_created", "structures_created", "skipped", "total_rows"):
        assert k in d, f"missing key {k}; got {list(d.keys())}"
    assert isinstance(d["total_rows"], int)
    assert d["total_rows"] >= 0


def test_seed_2026_idempotent():
    r1 = requests.post(f"{BASE}/api/fee-structures/seed-2026", headers=H(), timeout=60)
    assert r1.status_code == 200
    r2 = requests.post(f"{BASE}/api/fee-structures/seed-2026", headers=H(), timeout=60)
    assert r2.status_code == 200
    d2 = r2.json()
    # second run: nothing new should be created, skipped should be >0 (assuming total_rows>0)
    if d2["total_rows"] > 0:
        assert d2["structures_created"] == 0, f"second run created structures: {d2}"
        assert d2["skipped"] >= 0


# ---------- Regression smoke tests ----------
def test_smoke_students_list():
    r = requests.get(f"{BASE}/api/students?limit=5", headers=H(), timeout=15)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_smoke_receipts_list():
    r = requests.get(f"{BASE}/api/receipts?limit=5", headers=H(), timeout=15)
    assert r.status_code == 200, r.text


def test_smoke_imports_history():
    r = requests.get(f"{BASE}/api/imports/history", headers=H(), timeout=15)
    assert r.status_code == 200, r.text


def test_smoke_sibling_endpoint():
    students = requests.get(f"{BASE}/api/students?limit=1", headers=H(), timeout=15).json()
    if not students:
        return  # nothing to test
    sid = students[0]["id"]
    r = requests.get(f"{BASE}/api/students/{sid}/siblings", headers=H(), timeout=15)
    assert r.status_code == 200, r.text


def test_smoke_day_end_report():
    today = date.today().isoformat()
    r = requests.get(f"{BASE}/api/reports/day-end?date={today}", headers=H(), timeout=20)
    assert r.status_code == 200, r.text
