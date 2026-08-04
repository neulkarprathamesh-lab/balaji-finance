# Balaji Convent Fee Software — Release Notes

## Version 1.0.0 — Production Ready (Feb 2026)

**Status**: PRODUCTION READY — passed all internal verification, 47/47 automated tests green.

### Highlights
- **Complete Fee Management**: 41 fee structures across English Medium, Semi Medium (Marathi) and Junior College with per-installment tuition + admission + continuation + term + practical fees.
- **Automatic Fee Assignment**: import a student's Medium + Class + Stream (JC) and the system picks the correct fee structure automatically. Rejects mis-tagged rows (Class 5 English tagged as Semi, JC without Stream, etc.).
- **Bus Stop Master**: 61 stops with fares from ₹850 – ₹1,400. Admin CRUD, deactivate, and stop-to-route grouping.
- **9 Receipt Types**: EP, MP, EMP, SEC, JC, JCACS, BUS, EMJC, DV — each with configurable prefix, layout, fields, watermark, QR, barcode.
- **Business Rules Enforced**: Admission Fee one-time per student per year; Continuation Fee no partial payment; role-gated refunds and vouchers.
- **Admin PIN Dual-Auth** on sensitive actions (config import, sequence reset, backup download).
- **Config Export/Import** as ZIP with automatic pre-import backup.
- **Backup Rotation** — auto keeps last 30 backups.
- **System Diagnostics** — 6 server-side + 5 browser-side checks, sidebar red-badge alert when any fails.
- **Scheduled 8 AM Snapshot** — daily automated diagnostics with dashboard banner if overnight failure.
- **First-Run Onboarding** popover for the very first admin sign-in.
- **Kiosk QR** lookups + fee slips for parents (no auth required).
- **Complete Offline-LAN** — zero CDN dependency on daily flows.
- **Distribution ZIP** — one-click Windows installer with auto JWT generation + preflight check.
- **Full Ownership** — no license locks, no telemetry, no kill switches.

### Architecture
- Backend: FastAPI monolith split into 8 domain routers under `/app/backend/routers/` + shared `core.py`.
- Frontend: React 19 with route-level lazy loading and role-based nav filter.
- Data: MongoDB 7 with 17+ collections. Indexed on email, admission_no, receipt number, counter key.
- Auth: JWT with 12-hour access + optional Administrator PIN as second factor.
- Offline PWA-ready.

### Verification (v1.0.0)
- **Backend**: 47/47 pytest passing (`backend_test.py`, `test_stabilization.py`, `test_undefined_var_fixes.py`).
- **Frontend**: 23/23 authenticated routes render clean, all RBAC gates verified for 4 roles.
- **Kiosk / public**: `/parent/:adm`, `/parent/:adm/slip`, `/lookup/:number` all render without auth.
- **Offline assets**: `/school-logo.jpeg`, `/login-bg.png`, `/manifest.json` return 200.
- **Business rules**: admission-fee one-time and continuation-fee no-partial confirmed via live receipt tests.

### Known Limitations
- Windows-only distribution ZIP (Linux/macOS require manual install using the source code).
- Bus stop names transliterated to English (schools comfortable with Devanagari can edit inline via Bus Stop Master).

### Support
- Admin → System Diagnostics returns a shareable health report.
- Admin → Delivery Center exposes every deliverable for offline archival.
