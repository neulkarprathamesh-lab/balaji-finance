# Balaji FeeHub - Product Requirements Document

## Original Problem Statement
Offline, LAN-based comprehensive fee and accounting software for Balaji Convent & Junior College, Butibori, Nagpur. Must be deliverable as two Windows `.exe` installers (Main Server + Client) with zero developer tools, zero internet downloads, and zero manual setup required. Native Windows desktop feel — not a browser shortcut. Existing installations must be updateable without redownloading the entire 700 MB installer.

## Users / Personas
- **Administrator** — full control, users, factory reset, updates
- **Manager** — oversight, reports
- **Accountant** — ledgers, vouchers, reconciliation
- **Cashier** — collect fees, print receipts

## Tech Stack
- Backend: FastAPI + MongoDB
- Frontend: React 19 + shadcn/ui
- Desktop shell: Electron 31.7.7 (native Windows app)
- Installer: Inno Setup 6 + PowerShell orchestrator (idempotent, self-healing)
- CI: GitHub Actions (`windows-latest`) → cross-compile Windows `.exe`
- Differential updates: `.bcupdate` ZIP + RSA-PSS-SHA256 signed manifest via GitHub Releases

## What's Implemented (as of Feb 2026)

### Core v1.0
- Full CRUD: students, departments, classes, fee heads, receipts, users
- Receipt numbering: `{DEPT_CODE}-{YEAR}-{6DIGIT}`
- Role-based access (administrator > manager > accountant > cashier)
- JWT via httpOnly cookie + Bearer token
- Dashboard, backups, factory reset (5-gate wipe, PIN 2580)

### Windows Delivery
- **Electron desktop app** (`/app/desktop/`)
- **Idempotent PowerShell installer** (`install-main-server.ps1`)
- **Offline Python wheelhouse** rebuilt natively on Windows CI
- **Runtime API detection** (`api.js`) — no baked preview URLs
- **CI pipeline guards** — fail build if preview URL detected in bundle
- **BalajiFeeHub-Credentials.pdf** — printable Day-1 setup sheet
- Full installer artifact: `BalajiFeeHub-Installers` (Server + Client `.exe`)

### Differential Update System (Feb 2026, NEW)
Reuses the pre-existing hardened `backend/routers/updates.py` `.bcupdate` install engine (RSA signature, per-file SHA-256, path whitelist, DB backup, rollback rotation, auto-rollback on failure). Delivery layer added on top:
- **`/app/VERSION`** — single source of truth; `tools/sync-version.js` propagates to `desktop/package.json`, both `.iss` files, `version.json`, `diagnostics.py`
- **`tools/build-bcupdate.js`** — CI-side generator: diffs current payload vs. previous release manifest, emits signed `.bcupdate` + release manifest + installed manifest
- **`tools/validate-release.js`** — hard gate: fails build if any version/hash/size/signature check fails
- **`desktop/updater/`** — client with proper semver comparison (1.0.10 > 1.0.9), GitHub API polling, SHA-256 verify, path-safety guards
- **`desktop/renderer/update.html`** — UI: current/available versions, changelog, download size badge, admin PIN, progress bar, restart, retry, full-installer fallback
- **Silent 30-second background check** on startup; graceful GitHub-offline
- **`Help → Check for Updates…`** menu item
- **CI workflow**: sync-version → tests → build → payload assembly → build-bcupdate → validate-release (HARD GATE) → upload artifacts → publish GitHub Release *only* on `v*` tag push
- **RELEASE.md**: `git tag v1.0.1 && git push origin v1.0.1`
- **Repo secret required**: `UPDATER_PRIVATE_KEY_PEM` (RSA-PSS-SHA256 sign key). Public key already ships in `backend/keys/update_public.pem`.
- **Verified working**: 19/19 version-compare tests, 26/26 path-safety tests, 18/18 end-to-end differential-build assertions

### Credentials
See `/app/memory/test_credentials.md`. Same admin credential (`admin@balajiconvent.in / ChangeMeOnFirstLogin@2026`) now seeded on both preview and Windows.

## Roadmap

### P0 — Push To GitHub (blocked on user)
- Click "Save to Github" → GitHub Actions builds fresh `.exe` + generates first `.bcupdate`
- Add `UPDATER_PRIVATE_KEY_PEM` repository secret before tagging first release
- Install `Server-Setup.exe` on the school PC → this becomes the baseline version
- Cut `v1.0.1` tag next time you fix or add anything → PC pulls a ~10 MB `.bcupdate` instead of 700 MB

### P1 — Debit Voucher Module (on hold, per user)
- New `debit_vouchers` collection, `V-{YEAR}-{6DIGIT}` numbering
- A4 print design matching fee receipts
- Approval workflow: >₹10,000 requires administrator/manager approval
- Person-wise ledger across time
- CSV/PDF export

### P2 — Backlog
- SMS/WhatsApp fee reminders (needs Twilio)
- Multi-year archive & rollover
- Bulk fee structure updates
- Staff attendance module

## Architecture
```
/app/
├── VERSION                    single source of truth
├── version.json               live/mutable (backend reads at request-time)
├── RELEASE.md                 how to cut a release
├── backend/                   FastAPI + MongoDB + routers/updates.py (install engine)
├── frontend/                  React 19
├── desktop/                   Electron 31.7.7
│   ├── updater/               NEW: client-side updater module
│   ├── renderer/update.html   NEW: update UI
│   └── tests/                 NEW: version-compare + paths + e2e
├── tools/                     NEW: sync-version.js, build-bcupdate.js, validate-release.js
├── installer-sources/         Inno Setup + PowerShell
└── .github/workflows/         CI (extended, backwards-compatible)
```

## Key Files
- `/app/VERSION`
- `/app/tools/sync-version.js`, `build-bcupdate.js`, `validate-release.js`
- `/app/desktop/updater/updater.js`, `version-compare.js`, `paths.js`
- `/app/desktop/renderer/update.html`, `update.js`
- `/app/backend/routers/updates.py` (existing, now `APP_ROOT` env-configurable)
- `/app/.github/workflows/build-installers.yml`
- `/app/memory/DIFFERENTIAL_UPDATE_ARCHITECTURE.md` (full architecture doc)
