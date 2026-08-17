"""Iteration 7 backend tests — production purge preview/reject, deliverables manifest,
rebuild-zip endpoint, and regression checks."""
import os
import pytest
import requests

def _load_frontend_url():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_url()
BASE_URL = BASE_URL.rstrip("/")
ADMIN_EMAIL = "neulkarprathamesh@gmail.com"
ADMIN_PASSWORD = "Balaji@2026"
ADMIN_PIN = "1234"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ============ Purge preview ============
class TestPurgePreview:
    def test_preview_requires_pin(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/production/purge/preview", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 without PIN, got {r.status_code}"

    def test_preview_with_pin(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/production/purge/preview",
                             headers={"X-Admin-Pin": ADMIN_PIN}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("confirm_phrase_required") == "PURGE DEMO DATA"
        assert isinstance(data.get("would_delete"), dict)
        assert isinstance(data.get("would_preserve"), dict)
        # Should include at least these transactional collections
        expected_tx = {"students", "receipts", "audit_log", "updates", "backups",
                       "adjustments", "payment_extensions", "reminders", "notices",
                       "config_snapshots", "diagnostics_snapshots"}
        assert expected_tx.issubset(set(data["would_delete"].keys())), \
            f"Missing collections: {expected_tx - set(data['would_delete'].keys())}"
        # Preserved master collections
        expected_master = {"departments", "classes", "fee_heads", "receipt_types",
                           "users", "settings"}
        assert expected_master.issubset(set(data["would_preserve"].keys()))
        assert "would_reset_counters" in data


# ============ Purge rejection (does NOT delete) ============
class TestPurgeRejection:
    def test_purge_without_pin(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/production/purge",
                              json={"confirm_phrase": "PURGE DEMO DATA"}, timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 without PIN, got {r.status_code}"

    def test_purge_wrong_phrase_does_not_delete(self, auth_session):
        # Snapshot preview
        pre = auth_session.get(f"{BASE_URL}/api/production/purge/preview",
                               headers={"X-Admin-Pin": ADMIN_PIN}, timeout=30).json()
        # Attempt purge with wrong phrase
        r = auth_session.post(f"{BASE_URL}/api/production/purge",
                              headers={"X-Admin-Pin": ADMIN_PIN},
                              json={"confirm_phrase": "wrong phrase"}, timeout=30)
        assert r.status_code == 400, f"expected 400 for wrong phrase, got {r.status_code} {r.text}"
        # Re-check preview counts unchanged
        post = auth_session.get(f"{BASE_URL}/api/production/purge/preview",
                                headers={"X-Admin-Pin": ADMIN_PIN}, timeout=30).json()
        assert pre["would_delete"] == post["would_delete"], \
            f"Counts changed after rejected purge!\nBefore: {pre['would_delete']}\nAfter: {post['would_delete']}"


# ============ Deliverables ============
class TestDeliverables:
    def test_manifest_has_production_release(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/deliverables/manifest", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        sections = data.get("sections", [])
        assert len(sections) == 5, f"expected 5 sections, got {len(sections)}"
        titles = [s["title"] for s in sections]
        assert "Production Release" in titles
        prod = next(s for s in sections if s["title"] == "Production Release")
        first = prod["items"][0]
        assert first.get("available") is True, f"first item not available: {first}"
        assert first.get("download_url") == "/downloads/BalajiFeeHub-v1.0-FINAL.zip", \
            f"got {first.get('download_url')}"

    def test_rebuild_zip_requires_pin(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/deliverables/rebuild-zip", timeout=30)
        assert r.status_code in (401, 403)

    def test_rebuild_zip_with_pin(self, auth_session):
        r = auth_session.post(f"{BASE_URL}/api/deliverables/rebuild-zip",
                              headers={"X-Admin-Pin": ADMIN_PIN}, timeout=240)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("download_url") == "/downloads/BalajiFeeHub-v1.0-FINAL.zip"
        assert isinstance(data.get("size_mb"), (int, float)) and data["size_mb"] > 0
        assert "log_tail" in data


# ============ Regression ============
class TestRegression:
    def test_version(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/version", timeout=15)
        assert r.status_code == 200
        assert "version" in r.json()

    def test_updates_current(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/updates/current", timeout=15)
        assert r.status_code == 200

    def test_updates_public_key(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/updates/public-key", timeout=15)
        assert r.status_code == 200

    def test_receipts_list(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/receipts?limit=3", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # Data should exist (purge not applied)
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        assert isinstance(items, list)

    def test_students_list(self, auth_session):
        r = auth_session.get(f"{BASE_URL}/api/students?query=&limit=3", timeout=30)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        assert isinstance(items, list)
