# Balaji FeeHub - Product Requirements Document

## Original Problem Statement
Offline, LAN-based comprehensive fee and accounting software for Balaji Convent & Junior College, Butibori, Nagpur. Must be deliverable as two Windows `.exe` installers (Main Server + Client) with zero developer tools, zero internet downloads, and zero manual setup required. Native Windows desktop feel — not a browser shortcut.

## Users / Personas
- **Administrator** — full control, manages users, factory reset
- **Manager** — oversight, reports
- **Accountant** — ledgers, vouchers, reconciliation
- **Cashier** — collect fees, print receipts

## Tech Stack
- Backend: FastAPI + MongoDB
- Frontend: React 19 + shadcn/ui
- Desktop shell: Electron (native Windows app)
- Installer: Inno Setup + PowerShell orchestrator (idempotent, self-healing)
- CI: GitHub Actions (Linux → Windows cross-compile via `windows-latest` runner)

## What's Implemented (as of Feb 2026)

### Core (v1.0)
- Full CRUD: students, departments, classes, fee heads, receipts, users
- Receipt numbering: `{DEPT_CODE}-{YEAR}-{6DIGIT}`
- Role-based access (administrator > manager > accountant > cashier)
- JWT auth via httpOnly cookie + Bearer token (LAN-safe)
- Dashboard summary, backups, factory reset (5-gate wipe, PIN 2580)

### Windows Delivery (this session)
- **Electron desktop app** (`/app/desktop/`) — native Windows shell, no browser dependency
- **Idempotent PowerShell installer** (`/app/installer-sources/scripts/install-main-server.ps1`) — detects/repairs/creates MongoDB, Python, backend service, frontend, Windows services
- **Offline Python wheelhouse** — built on Windows runner (includes `colorama` etc.)
- **Runtime API detection** (`/app/frontend/src/lib/api.js`) — uses `window.location` at runtime, no baked preview URLs
- **CI pipeline guards** — fail build if preview URL detected in bundle
- **Login diagnostics UI** — on-screen JSON showing api_base, endpoint, status, response
- **BalajiFeeHub-Credentials.pdf** — printable Day-1 setup sheet
- **GitHub Actions** (`/app/.github/workflows/build-installers.yml`) — compiles Main Server + Client `.exe` and uploads as `BalajiFeeHub-Installers` artifact
- **Same admin credential everywhere** (Feb 2026) — `admin@balajiconvent.in / ChangeMeOnFirstLogin@2026` now seeded on preview too, so no more "works on my machine" confusion

## Credentials
See `/app/memory/test_credentials.md` for the authoritative list.

## Roadmap

### P0 — Delivery (blocked on user action)
- User clicks **"Save to Github"** → GitHub Actions builds fresh `.exe` with all login fixes → user downloads `BalajiFeeHub-Installers` → installs on Windows → tests end-to-end (login, dashboard, students, receipts, factory reset, logout/re-login)

### P1 — Debit Voucher Module (on hold, per user)
- New ledger collection: `debit_vouchers`
- Voucher number format: `V-{YEAR}-{6DIGIT}`
- A4 computer-generated design matching fee receipts (school header, logo, signature blocks)
- Approval workflow: amounts > ₹10,000 require administrator/manager approval
- Global Person-wise Ledger — track all issuances to a specific "Issued To / Paid To" entity across time
- CSV/PDF export

### P2 — Backlog
- Fee reminder SMS/WhatsApp (needs Twilio integration)
- Multi-year archive & rollover
- Bulk fee structure updates
- Staff attendance module

## Architecture
```
/app/
├── backend/           FastAPI + MongoDB (server.py, core.py, routers/)
├── frontend/          React 19 (src/lib/api.js = runtime URL resolver)
├── desktop/           Electron shell (main.js, preload.js)
├── installer-sources/ Inno Setup .iss + PowerShell scripts
└── .github/workflows/ CI pipeline for Windows .exe compilation
```

## Key Files
- `/app/backend/core.py` — `seed_data()` seeds both prod admin + dev admin + demo staff
- `/app/frontend/src/lib/api.js` — critical runtime API URL resolver
- `/app/installer-sources/scripts/install-main-server.ps1` — 900+ line idempotent installer
- `/app/desktop/main.js` — Electron entry point
- `/app/.github/workflows/build-installers.yml` — CI pipeline
