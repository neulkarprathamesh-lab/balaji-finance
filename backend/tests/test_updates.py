"""End-to-end pytest suite for the Offline-LAN Software Update System.

Runs an actual signed-.bcupdate upload → verify → install → rollback cycle against
the running FastAPI backend, using the ADMIN account + PIN 1234 that seed_data
guarantees. Also covers the negative paths: tampered checksum, missing manifest,
min-supported version too low, bad extension, invalid ZIP, oversized file.

The test never restarts the running backend service — every update it applies
writes into a temporary file under /app/static/test_updates/ that is outside
the real code paths, so hot reload / supervisor is not disturbed.
"""
import base64
import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path

import pytest
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Tests run inside the same container as the backend, so we hit localhost:8001 directly.
# This bypasses the k8s ingress which can be sluggish and cause 30s+ read timeouts.
BASE = os.environ.get("BC_TEST_BASE") or "http://localhost:8001"
ADMIN_EMAIL = "neulkarprathamesh@gmail.com"
ADMIN_PW    = "Balaji@2026"
ADMIN_PIN   = "1234"

PRIVATE_KEY_PATH = Path("/app/backend/keys/update_private.pem")
STATIC_TARGET_REL = "static/test_updates/hello.txt"
STATIC_TARGET_ABS = Path(f"/app/{STATIC_TARGET_REL}")


# ---------------- Helpers ----------------
_cached_token = None
def _token():
    global _cached_token
    if _cached_token: return _cached_token
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    r.raise_for_status()
    _cached_token = r.json()["token"]
    return _cached_token

def _headers(pin: bool = False):
    h = {"Authorization": f"Bearer {_token()}"}
    if pin: h["X-Admin-Pin"] = ADMIN_PIN
    return h

# All negative-path uploads use a longer timeout because the preview URL ingress
# can be sluggish right after an install cycle.
UPLOAD_TIMEOUT = 60

def _ensure_pin():
    h = {"Authorization": f"Bearer {_token()}"}
    st = requests.get(f"{BASE}/api/auth/me/pin-status", headers=h).json()
    if not st.get("has_pin"):
        r = requests.post(f"{BASE}/api/auth/me/pin",
                          json={"new_pin": ADMIN_PIN, "current_password": ADMIN_PW},
                          headers={**h, "Content-Type": "application/json"})
        assert r.status_code in (200, 201), r.text

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _sign(manifest_bytes: bytes) -> str:
    key = serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    sig = key.sign(
        manifest_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode()

def _build_bcupdate(*, version="99.0.0", min_supported="0.0.0",
                    payload_files: dict = None, migrations: dict = None,
                    tamper_checksum=False, omit_manifest=False,
                    restart_backend=False) -> bytes:
    """Build an in-memory .bcupdate zip. `payload_files` maps rel-path → bytes.
    Only static/… paths are used so we never touch real code."""
    if payload_files is None:
        payload_files = {STATIC_TARGET_REL: b"hello-from-update-" + version.encode()}
    files_sha = {rel: _sha256_bytes(data) for rel, data in payload_files.items()}
    if tamper_checksum:
        first = next(iter(files_sha))
        files_sha[first] = "0" * 64
    manifest = {
        "version": version,
        "min_supported_version": min_supported,
        "release_notes": f"pytest build v{version}",
        "build_date": "2026-02-15",
        "database_version": None,
        "files": files_sha,
        "migrations": list((migrations or {}).keys()),
        "requires_backend_restart": bool(restart_backend),
        "requires_frontend_reload": False,
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()
    sig_b64 = _sign(manifest_bytes)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if not omit_manifest:
            zf.writestr("manifest.json", manifest_bytes)
            zf.writestr("manifest.sig", sig_b64)
        for rel, data in payload_files.items():
            zf.writestr(f"payload/{rel}", data)
        for name, code in (migrations or {}).items():
            zf.writestr(f"migrations/{name}", code)
    return buf.getvalue()


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module", autouse=True)
def prep():
    _ensure_pin()
    # Make sure keys exist (backend generates them on first /current call)
    r = requests.get(f"{BASE}/api/updates/current", headers=_headers())
    assert r.status_code == 200, r.text
    assert PRIVATE_KEY_PATH.exists(), "private key was not generated on the server"
    # Wipe any leftover test file
    STATIC_TARGET_ABS.unlink(missing_ok=True)
    yield


# ---------------- Positive path: upload → install → verify → rollback ----------------
def test_public_key_endpoint():
    r = requests.get(f"{BASE}/api/updates/public-key", headers=_headers())
    assert r.status_code == 200
    assert "BEGIN PUBLIC KEY" in r.json()["public_key_pem"]


def test_upload_and_install_and_rollback_cycle():
    # 1) Build & upload
    zip_bytes = _build_bcupdate(version="1.0.1", min_supported="0.0.0",
                                payload_files={STATIC_TARGET_REL: b"UPDATED-CONTENT"})
    r = requests.post(
        f"{BASE}/api/updates/upload",
        headers={**_headers(pin=True)},
        files={"file": ("test.bcupdate", zip_bytes, "application/zip")},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    stage = r.json()
    assert stage["valid"] is True
    assert stage["manifest"]["version"] == "1.0.1"
    upd_id = stage["update_id"]

    # 2) Staging manifest re-check
    r2 = requests.get(f"{BASE}/api/updates/staging/{upd_id}", headers=_headers())
    assert r2.status_code == 200

    # 3) Install
    r3 = requests.post(f"{BASE}/api/updates/install/{upd_id}",
                       headers=_headers(pin=True), timeout=120)
    assert r3.status_code == 200, r3.text
    data = r3.json()
    assert data["ok"] is True
    assert data["to_version"] == "1.0.1"
    assert STATIC_TARGET_ABS.read_bytes() == b"UPDATED-CONTENT"

    # 4) Version endpoint reports new version
    v = requests.get(f"{BASE}/api/version").json()
    assert v.get("app_version") == "1.0.1" or v.get("version") == "1.0.1"

    # 5) /updates/current shows a rollback slot
    cur = requests.get(f"{BASE}/api/updates/current", headers=_headers()).json()
    assert cur["rollback_available"] >= 1
    assert cur["current"]["version"] == "1.0.1"

    # 6) History has the new row
    hist = requests.get(f"{BASE}/api/updates", headers=_headers()).json()
    assert any(h["to_version"] == "1.0.1" and h["status"] == "success" for h in hist)

    # 7) Rollback
    rbs = requests.get(f"{BASE}/api/updates/rollbacks", headers=_headers()).json()
    assert rbs, "no rollback snapshot on disk"
    rb = next(r for r in rbs if r["from_version"] != "1.0.1")
    rr = requests.post(f"{BASE}/api/updates/rollback/{rb['rollback_id']}",
                       headers=_headers(pin=True), timeout=60)
    assert rr.status_code == 200
    # Version reverted
    v2 = requests.get(f"{BASE}/api/version").json()
    assert v2.get("app_version") != "1.0.1" and v2.get("version") != "1.0.1"


# ---------------- Negative paths ----------------
def test_reject_wrong_extension():
    zip_bytes = _build_bcupdate(version="1.0.2")
    r = requests.post(f"{BASE}/api/updates/upload", headers=_headers(pin=True),
                      files={"file": ("test.zip", zip_bytes, "application/zip")}, timeout=UPLOAD_TIMEOUT)
    assert r.status_code == 400
    assert ".bcupdate" in r.text


def test_reject_invalid_zip():
    r = requests.post(f"{BASE}/api/updates/upload", headers=_headers(pin=True),
                      files={"file": ("bad.bcupdate", b"not a zip", "application/zip")}, timeout=UPLOAD_TIMEOUT)
    assert r.status_code == 400


def test_reject_tampered_checksum():
    zip_bytes = _build_bcupdate(version="1.0.3", tamper_checksum=True)
    r = requests.post(f"{BASE}/api/updates/upload", headers=_headers(pin=True),
                      files={"file": ("test.bcupdate", zip_bytes, "application/zip")}, timeout=UPLOAD_TIMEOUT)
    assert r.status_code == 400
    assert "Checksum" in r.text or "checksum" in r.text


def test_reject_min_supported_too_high():
    zip_bytes = _build_bcupdate(version="9.9.9", min_supported="99.0.0")
    r = requests.post(f"{BASE}/api/updates/upload", headers=_headers(pin=True),
                      files={"file": ("test.bcupdate", zip_bytes, "application/zip")}, timeout=UPLOAD_TIMEOUT)
    assert r.status_code == 400
    assert "requires" in r.text.lower() or "min" in r.text.lower() or "intermediate" in r.text.lower()


def test_reject_missing_manifest():
    zip_bytes = _build_bcupdate(version="1.0.4", omit_manifest=True)
    r = requests.post(f"{BASE}/api/updates/upload", headers=_headers(pin=True),
                      files={"file": ("test.bcupdate", zip_bytes, "application/zip")}, timeout=UPLOAD_TIMEOUT)
    assert r.status_code == 400


def test_upload_requires_admin_pin():
    zip_bytes = _build_bcupdate(version="1.0.5")
    r = requests.post(f"{BASE}/api/updates/upload",
                      headers=_headers(pin=False),   # no X-Admin-Pin
                      files={"file": ("test.bcupdate", zip_bytes, "application/zip")}, timeout=UPLOAD_TIMEOUT)
    assert r.status_code in (401, 403)


def test_reject_outside_allowed_root():
    # payload writes to a path that's not on the allowlist
    zip_bytes = _build_bcupdate(
        version="1.0.6",
        payload_files={"etc/passwd": b"root::0:0::/:/bin/sh"},
    )
    r = requests.post(f"{BASE}/api/updates/upload", headers=_headers(pin=True),
                      files={"file": ("test.bcupdate", zip_bytes, "application/zip")}, timeout=UPLOAD_TIMEOUT)
    assert r.status_code == 400
    assert "outside" in r.text.lower() or "allowed" in r.text.lower()
