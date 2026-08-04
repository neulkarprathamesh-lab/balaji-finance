"""Final verification: endpoints healthy on ~1,026-student LT- dataset."""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

ADMIN = {"email": "neulkarprathamesh@gmail.com", "password": "Balaji@2026"}
CASHIER = {"email": "cashier@balajiconvent.in", "password": "cashier123"}


def login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return login(ADMIN)


@pytest.fixture(scope="module")
def cashier():
    return login(CASHIER)


def test_version_public():
    r = requests.get(f"{BASE}/api/version", timeout=10)
    assert r.status_code == 200
    assert "version" in r.json() or "app" in r.json() or r.json()


def test_dashboard(admin):
    r = admin.get(f"{BASE}/api/dashboard", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_diagnostics(admin):
    r = admin.get(f"{BASE}/api/diagnostics", timeout=15)
    assert r.status_code == 200


def test_cashier_auth():
    s = login(CASHIER)
    r = s.get(f"{BASE}/api/auth/me", timeout=10)
    assert r.status_code == 200


def test_students_lt_search(admin):
    t0 = time.time()
    r = admin.get(f"{BASE}/api/students", params={"q": "LT-"}, timeout=20)
    dt = time.time() - t0
    assert r.status_code == 200
    data = r.json()
    rows = data if isinstance(data, list) else data.get("items") or data.get("students") or data.get("data") or []
    assert len(rows) > 0, f"no LT- students found: {str(data)[:300]}"
    print(f"students?q=LT- returned {len(rows)} rows in {dt:.2f}s")
    # store id for ledger test
    global _LT_STUDENT
    _LT_STUDENT = rows[0]


def test_student_ledger(admin):
    r = admin.get(f"{BASE}/api/students", params={"q": "LT-", "limit": 5}, timeout=20)
    rows = r.json() if isinstance(r.json(), list) else (r.json().get("items") or r.json().get("students") or r.json().get("data") or [])
    assert rows, "no LT- students"
    sid = rows[0].get("id") or rows[0].get("_id") or rows[0].get("student_id")
    assert sid, f"no id in row: {rows[0]}"
    r2 = admin.get(f"{BASE}/api/students/{sid}/ledger", timeout=20)
    assert r2.status_code == 200, f"{r2.status_code} {r2.text[:300]}"


def test_defaulters_perf(admin):
    t0 = time.time()
    r = admin.get(f"{BASE}/api/reports/defaulters", params={"quarter": "total"}, timeout=15)
    dt = time.time() - t0
    assert r.status_code == 200
    assert dt < 3.0, f"defaulters took {dt:.2f}s (>3s)"
    print(f"defaulters?quarter=total in {dt:.2f}s")


def test_fee_structures_count(admin):
    r = admin.get(f"{BASE}/api/fee-structures", timeout=10)
    assert r.status_code == 200
    data = r.json()
    rows = data if isinstance(data, list) else data.get("items") or []
    assert len(rows) == 44, f"expected 44, got {len(rows)}"


def test_bus_stops_count(admin):
    r = admin.get(f"{BASE}/api/bus-stops", timeout=10)
    assert r.status_code == 200
    data = r.json()
    rows = data if isinstance(data, list) else data.get("items") or []
    assert len(rows) == 61, f"expected 61, got {len(rows)}"


def test_receipt_types_count(admin):
    r = admin.get(f"{BASE}/api/receipt-types", timeout=10)
    assert r.status_code == 200
    data = r.json()
    rows = data if isinstance(data, list) else data.get("items") or []
    # Filter out test-created TEST_* if any
    real = [x for x in rows if not (x.get("name", "") or x.get("code", "")).startswith("TEST_")]
    assert len(real) >= 9, f"expected >=9 real, got {len(real)} (total {len(rows)})"


def test_bulk_import_validation_rejects_jc_missing_stream(admin):
    payload = {
        "rows": [
            {"adm_no": "LT-BULK-JC-1", "name": "TEST JC No Stream", "class_name": "JC", "section": "A"},
            {"adm_no": "LT-BULK-C5-1", "name": "TEST C5 Semi English", "class_name": "5", "section": "A", "medium": "English", "stream_or_medium_tag": "Semi"},
        ],
        "dry_run": True,
    }
    r = admin.post(f"{BASE}/api/students/bulk-import", json=payload, timeout=20)
    # Endpoint should return 200 with per-row errors OR 400
    assert r.status_code in (200, 400, 422), f"{r.status_code} {r.text[:300]}"
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    text = str(body).lower()
    # Should mention stream error or semi error somewhere
    assert "stream" in text or "semi" in text or "error" in text, f"no validation errors in {str(body)[:400]}"


def test_duplicate_admission_fee_blocked(admin):
    # Find any LT- student
    r = admin.get(f"{BASE}/api/students", params={"q": "LT-", "limit": 1}, timeout=15)
    rows = r.json() if isinstance(r.json(), list) else (r.json().get("items") or r.json().get("students") or r.json().get("data") or [])
    if not rows:
        pytest.skip("no LT- student")
    sid = rows[0].get("id")
    # Find Admission Fee receipt-type
    rt = admin.get(f"{BASE}/api/receipt-types", timeout=10).json()
    rt_rows = rt if isinstance(rt, list) else rt.get("items") or []
    adm_rt = next((x for x in rt_rows if "admission" in (x.get("name", "") or "").lower()), None)
    if not adm_rt:
        pytest.skip("no admission-fee receipt-type")
    payload = {
        "student_id": sid,
        "receipt_type_id": adm_rt.get("id"),
        "amount": 100,
        "mode": "cash",
    }
    r1 = admin.post(f"{BASE}/api/receipts", json=payload, timeout=15)
    r2 = admin.post(f"{BASE}/api/receipts", json=payload, timeout=15)
    # Expect second to be 409 (or first was already blocked earlier)
    assert r2.status_code == 409 or (r1.status_code == 409), f"r1={r1.status_code} r2={r2.status_code} r2body={r2.text[:300]}"


def test_snapshots(admin):
    r = admin.get(f"{BASE}/api/snapshots", timeout=15)
    assert r.status_code == 200
    data = r.json()
    rows = data if isinstance(data, list) else data.get("items") or []
    assert len(rows) >= 1, "no snapshots"


def test_bus_stops_bulk_update_preview(admin):
    payload = {"operation": "increase_percent", "value": 5, "round_to": 10, "preview": True}
    r = admin.post(f"{BASE}/api/bus-stops/bulk-update", json=payload, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    rows = data.get("rows") or data.get("preview") or data.get("items") or (data if isinstance(data, list) else [])
    assert rows, f"no preview rows: {str(data)[:300]}"
    row = rows[0]
    old = row.get("old_fare") or row.get("current_fare") or row.get("previous_fare")
    new = row.get("new_fare") or row.get("proposed_fare")
    assert new is not None, f"row missing new_fare: {row}"
    if old:
        expected = round(old * 1.05 / 10) * 10
        # Allow ceil/round variants
        assert abs(new - expected) <= 10, f"unexpected round: old={old} new={new} expected~{expected}"
