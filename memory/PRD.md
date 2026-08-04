# Balaji Convent Fee Software — PRD

## Original Problem Statement
User: "this what i think creating accountant software for my school"
Uploaded a 3-volume SRS (Vol 1 System Design, Vol 2 Functional Modules, Vol 3 Technical Spec) for Balaji Convent & Junior College, Butibori, Nagpur. Offline LAN-based fee & financial management system, 4 departments, 9 receipt types, role-based access, centralized receipt numbering, audit trail.

## User Choices (verbatim)
- Scope: **Everything** — all 9 receipt types, vouchers, refunds, bulk ops
- Auth: **JWT username+password with RBAC**
- Preseed 4 departments (English Primary, Marathi Primary, Secondary, Junior College): **yes**
- Currency & format: **INR with prefix like EP-2026-000001** — yes
- Deployment: **Strictly offline LAN-based** — build browser app hosted locally on Main Server PC, accessed via school LAN

## Personas
1. **Cashier** — collects fees, issues receipts, records reminder follow-ups, cannot approve
2. **Accountant** — reviews collections, reconciles reports, defines fee structures
3. **Manager** — approves adjustments, extensions, refunds, cancellations
4. **Administrator** — full control: users, departments, prefixes, audit, high-risk actions

## Architecture
- **Backend**: FastAPI (single-file `server.py`), MongoDB (motor), JWT via httpOnly cookie + Bearer token, bcrypt password hashing, atomic receipt numbering via `counters` collection with `$inc` upsert.
- **Frontend**: React 19 + React Router 7 + TailwindCSS + shadcn/ui + Sonner toasts + lucide-react icons. Typography: Work Sans (headings) + IBM Plex Sans (body/tabular figures). Design archetype: Swiss high-contrast, flat surfaces, dense tables (Tally-like).
- **RBAC** enforced both at API level (require_roles dep) AND at UI level (sidebar nav filter + Protected route wrapper).

## What's Been Implemented (2026-02-04)
### Backend
- JWT auth with cookie + bearer fallback; brute-force safe (per-request cost)
- Roles: cashier / accountant / manager / administrator
- Startup: admin seeding (from env), demo staff users (@balajiconvent.in), 4 departments (EP/MP/SEC/JC), 10 fee heads, ~22 classes, 6 sample students, unique indexes
- CRUD: Users, Departments, Classes, Fee Heads, Fee Structures, Students (with search)
- **Unified Receipt Engine** for all 9 types: school, admission, bus, misc, department, general_money, refund, debit_voucher, general_collection
- Central atomic numbering: `{DEPT}-{YEAR}-{6digit}` for receipts; `V-{YEAR}-{6digit}` for debit vouchers (separate sequence)
- Amount-in-words INR converter (crore/lakh/thousand)
- Receipt cancel (manager/admin, requires reason) + reprint (tracks count, last reprint by/at)
- Fee Adjustments (create by any, approve by manager/admin)
- Payment Extensions (max 4 installments, total must equal outstanding; approve materializes reminders)
- Reminders with bucketing (overdue/today/tomorrow/future) + follow-up remarks (payment_received flips status to paid)
- Student ledger (fee structure - paid - adjusted + refunded = outstanding)
- Dashboard aggregation (today's collection, pending approvals, due today/tomorrow/overdue, recent receipts, dept totals)
- Reports: collection (by mode, by type, gross/refund/voucher/net), audit log
- Full audit trail on every create/update/approve/reject/cancel/reprint

### Frontend
- Login (dual-panel with classroom backdrop)
- Layout: dark slate sidebar + white top bar + light content area; role-filtered nav
- Dashboard with 6 KPI cards + recent receipts table + dept collection breakdown
- Students list with universal search (admission/name/mobile) + New Student modal + department filter
- Student Detail with ledger + outstanding + receipt history
- Unified New Receipt page: 9-type selector, student search with preselection via `?student=<id>`, line items, live total, print-friendly layout
- Receipt View with print-optimized A4/A5 layout, duplicate/cancelled markers, reprint counter
- Fee Adjustments (list + create + approve/reject) — approve/reject visible only to manager/admin
- Payment Extensions (installment builder with total-must-match validation)
- Reminders board (overdue/today/tomorrow tabs, quick-follow-up dropdown)
- Reports (date range, dept filter, KPI + by-mode/by-type breakdown + rows)
- Fee Structure editor (per dept + class + academic year)
- Administration (user list, create user, audit log)

### Testing
- Iteration 1: admin path 100% (blocked non-admin login due to .local TLD)
- Iteration 2: 14/14 backend pytest passing, all RBAC paths verified, E2E receipt flow verified, sidebar RBAC filtering verified for all 3 roles

## Prioritized Backlog (P0 → P2)
- **P1** — Bulk operations: Excel import for students, bulk promotion (dept/class/section), assign fee structures in bulk
- **P1** — Receipt cancellation register (list of cancelled with reasons)
- **P1** — Student ledger report as printable
- **P2** — Barcode/QR on printed receipts, thermal printer template
- **P2** — Backup/restore UI + retention job runner
- **P2** — Scanned document attachment for extensions (file upload)
- **P2** — Dashboard drill-down click filters, saved report layouts, PDF/Excel export
- **P2** — Refactor server.py into routers/, models/, services/, seed.py (soft quality)
- **P2** — Refund/credit-note separate number series (product decision)

## Deployment Notes (for LAN Self-Host)
- Backend: `pip install -r backend/requirements.txt` on Main Server PC, run with `uvicorn server:app --host 0.0.0.0 --port 8001`.
- Database: local MongoDB (see `backend/.env` MONGO_URL).
- Frontend: `yarn build` produces static bundle; serve via nginx on Main Server PC. Set `REACT_APP_BACKEND_URL` to LAN IP (e.g., `http://192.168.1.10:8001`) before build.
- CORS: switch `CORS_ORIGINS` in `.env` to the LAN hostname/IP.
- Backups: schedule `mongodump` daily to a separate drive.


## 2026-02-04 (Fork resume) — Fixes & New Cashier UI
### Backend
- **Fixed** critical syntax error at server.py:1476 (stray `aid - adjusted + refunded)` + a duplicated defaulters/on_shutdown block appended to the file) that was crashing uvicorn on boot.
- **Added** `POST /api/fee-structures/bulk-import` — groups rows by (dept_code, class_name, academic_year), upserts fee structures, stamps `import_batch_id`, records batch in `import_batches`.
- **Added** `POST /api/fee-structures/bulk-delete` — undo by batch_id, skips structures already referenced by any student.
- **Modified** `POST /api/students/bulk-import` — now stamps `import_batch_id` on each row and records the batch summary; accepts optional `batch_id` in body.
- **Added** `POST /api/students/bulk-delete` — undo by batch_id OR by ids, safely protects students that already have receipts.
- **Added** `GET /api/imports/latest?kind=students|fee_structures` — returns the most recent non-undone batch for the requested kind.

### Frontend
- **Rebuilt `/new-receipt` page** to match the uploaded receipt-manager mock:
  - Navy header with logo, cashier profile, and "Advanced Types" link
  - Receipt-type tabs (Regular Fee / Installment / Other Charges) with sub-labels
  - Debounced student search bar + selected-student card (initials avatar, admission no, class, masked mobile)
  - Live outstanding / parent-will-pay / balance-after summary trio
  - **Amount Paying field** with auto-distribution across pending heads in priority order (Tuition → Transport → Bus → Computer → Activity → Library → others). Cashier can still toggle heads and edit per-line amounts.
  - "Pay Full Outstanding" and "Clear allocation" shortcuts
  - Payment mode selector: **Cash / UPI / Card** only (Bank Transfer removed per user)
  - Amount Received field auto-reflects allocated total
  - Big green "Create & Print Receipt" + secondary "Save & Continue Later"

### 2026-02-04 (continued 2) — Kiosk + Receipts follow-ups
- **Kiosk Sibling Combined**: The public `/parent/:adm` page now leads with a richer Family Ledger card — Total / Paid / Concession / Family Outstanding tiles plus a per-child mini list showing each sibling's initials avatar, name, admission no, class, and Due amount (or a green "✓ Paid up" pill). Parents see the whole family bill in one glance the moment any child's QR is scanned.
- **Receipt Search Chips**: `/receipts` now has quick-view chips at the top — Today, This Week, This Month, Cancelled, Clear. Selecting a chip auto-fills the date range (or filters status). Header dynamically updates to `N receipts · ₹X collected` (cancelled receipts excluded from the collected total).

### 2026-02-04 (continued 3) — Day-End + Kiosk Fee Slip
- **Cashier Day-End Summary** at `/day-end` (all roles):
  - Filters: date (defaults today), cashier dropdown (admin+ only) or auto-scoped for cashier role.
  - Money trio: Collected (Gross) · Refunded/Vouchers · **Net Cash Handover**.
  - Breakdown grids by payment mode (Cash/UPI/Card/Cheque/DD…) and by receipt type (school/admission/bus/refund/misc/general_collection…).
  - Per-cashier table (when "All cashiers" selected) with issued, cancelled, collected, refunded, net.
  - Receipt-by-receipt list for single-cashier drill-down.
  - Handover signature block (Cashier + Authorised By) + Print action.
  - Backend endpoint `GET /api/reports/day-end?date=&cashier_id=`. Cashiers are auto-scoped to their own id.
- **Kiosk Fee Slip** at `/parent/:adm/slip` (public, no auth):
  - A4 sheet with navy header, deterministic Slip ID (e.g. `BC-SLIP-007WQB80`), issue date, academic year.
  - Guardian card + QR code that verifies the family's live ledger.
  - Family Ledger Summary tiles + Children table with per-child row + FAMILY TOTAL navy row.
  - Recent Receipts across the whole family (up to 8 rows), computer-generated notice + school-seal placeholder + Principal signature block.
  - Watermark "BALAJI CONVENT" behind content. Print → Save as PDF via browser.
  - StudentLookup now surfaces a **"Download Family Fee Slip (PDF)"** action button.



### 2026-02-04 (continued 4) — Code-review critical fixes
- Fixed 3 static-analysis "undefined variable" warnings in `server.py`:
  - `dashboard()` line 1010 — `receipts_today_count` list-comprehension var renamed `r`→`x` to remove shadow of outer loop variable.
  - `seed_2026_fee_structures()` line 1194 — `rows: List[dict] = []` default added before the try/except so `len(rows)` is safe on any code path.
  - `defaulters_report()` line 1605 — generator expression var renamed `r`→`x` in `sum(x["outstanding"] for x in rows)` to remove shadow.
- Verified by testing_agent with 10/10 pytest passing in `/app/backend/tests/test_undefined_var_fixes.py`; all 3 endpoints return 200 with correct schemas + smoke tests on `/students`, `/receipts`, `/imports/history`, `/students/{id}/siblings`, `/reports/day-end` pass.
- The complexity-refactor "Important" section (bulk_import_fee_structures, outstanding_notices, seed_data, etc.) was intentionally NOT applied — that work touches ~5 hot code paths and would introduce regression risk on the many features just approved (Day-End, Fee Slip, Sibling Split, Import History). Keeping as a P2 backlog item to be scheduled once the feature set stabilises.

  - Bottom status strip: "Receipt number will be generated centrally"
- Preserved the original comprehensive form (all 9 receipt types including Bus/Voucher/Refund) at `/new-receipt-advanced` via new `NewReceiptAdvanced.js`, reachable via the header link.

### 2026-02-04 (continued 5) — True offline LAN readiness
- Downloaded the school logo and login backdrop to `frontend/public/school-logo.jpeg` and `frontend/public/login-bg.png` (previously served from an Emergent CDN URL).
- Replaced every CDN URL in the frontend (11 files: Layout, Login, NewReceipt, ReceiptView, DayEnd, FeeSlip, StudentLookup, KioskPoster, FeeBrochure, FeeNotices, Lookup) with local paths `/school-logo.jpeg` and `/login-bg.png`. Verified via HEAD 200 + on-page screenshot.
- Daily receipt work is now truly internet-independent — Google Fonts import remains but fails silently to system fonts if offline, and the PostHog / emergent-main scripts in index.html are async and non-blocking. The cashier flow (login → search student → allocate → print receipt → day-end) runs entirely from the Main PC via LAN.
- Rewrote `/app/SELF_HOST_GUIDE.md` with the full LAN architecture:
  - Network topology diagram (Main PC = single MongoDB + backend + frontend; client PCs are browsers only)
  - Static IP setup on Windows / Ubuntu
  - Firewall rules limited to private LAN (ports 8001, 3000) — never public
  - MongoDB kept on `bindIp: 127.0.0.1` because backend + Mongo co-locate on the Main PC
  - NSSM / systemd service setup for auto-start on boot
  - Nginx config for static frontend
  - Daily `mongodump` with rotating dual USB drives + quarterly restore drill
  - Explicit "what runs over internet" table — every internet feature (SMS, email, off-site backup, updates) marked optional with graceful-degradation notes.

- **ImportExcel.js**: uses a client-generated `batch_id` per file so undo is atomic; supports undo for **both** students and fee structures (uses the new `/bulk-delete` endpoints).

### 2026-02-04 (continued) — Follow-ups shipped
- **A4 Print Parity**: FeeReceipt now opens with a navy brand band that mirrors the cashier UI header ("Balaji Convent · School Receipt Manager / OFFICIAL FEE RECEIPT" + receipt no + date on the right).

### 2026-02-04 (continued 6) — Complete self-host distribution package
- Built `BalajiConventFeeSoftware-v1.0.zip` (1.6 MB, 168 files) — one-click download from **Administration → Install Package** tab.
- Package contents:
  - `START_HERE.md` — install order + golden rules
  - `01-install-main-server/` — Windows one-click `install-main-server.bat` (winget-installs MongoDB, Python, Node, NSSM, Yarn, then copies source + creates .env + builds frontend) + `register-services.bat` (NSSM auto-start on boot)
  - `02-install-client-pc/` — `install-client-pc.bat` — creates Chrome/Edge PWA shortcut pointing at the Main PC's LAN IP (no software install)
  - `03-source-code/` — full backend + frontend source (`.venv`, `node_modules`, `build`, `.env` excluded; `.env.example` templates included)
  - `04-database/README.md` — Mongo collections, seeding, indexes, manual queries
  - `05-services/` — `nginx.conf`, `balaji-backend.service`, `balaji-frontend.service` (systemd) + README
  - `06-excel-templates/` — `students-template.csv`, `fee-structures-template.csv` + usage README
  - `07-user-manuals/` — Cashier / Accountant / Manager / Administrator (4 role-specific plain-English guides)
  - `08-lan-installation/README.md` — the SELF_HOST_GUIDE with topology diagram, static IP, firewall, MongoDB LAN binding
  - `09-printer-setup/README.md` — A4 laser, colour, and thermal 80mm setups + common issues
  - `10-backup-restore/README.md` — daily `mongodump`, dual-USB rotation, quarterly restore drill, emergency restore steps
  - `11-optional-services/README.md` — Twilio/MSG91 SMS, Resend/SMTP email, off-site backup — all optional and graceful-degrade
  - `12-default-admin/README.md` — day-one checklist, JWT rotation, password recovery via env
- Published at `/downloads/BalajiConventFeeSoftware-v1.0.zip` (verified HTTP 200, 1.64 MB).
- Added an **Install Package** tab in the Administration screen with green download button, contents preview, and install-order callout.

- **Import History** page (`/imports-history`) — lists every batch with When / Kind / Imported By / Created / Updated-Skipped / Errors / Status / one-click Undo per row. Undone batches show a red pill and who undid them.
- **Amount Suggestions**: On student load, `Amount Paying` pre-fills with the top-priority pending head's outstanding, and a "Next Quarter" chip refills it any time.
- **Sibling Split**: When the loaded student has siblings on the same guardian mobile, an amber banner appears ("N sibling(s) on same guardian mobile — <Names>") with an "Include siblings in one payment" toggle. When on, all siblings' pending heads merge into one priority-sorted list, and each row is tagged with the student name. Submit creates **one receipt per student** in a single flow, with a family split preview in the right rail.
- New backend endpoints: `GET /api/students/{id}/siblings`, `GET /api/imports/history`. Both used exclusively by the new UI.
- **P1** — Print A4 receipt to inherit the navy header/branding of the new cashier UI (currently uses the existing A4 layout — good, but could tighten header parity)
- **P1** — "Import History" page listing past batches with counts, user, timestamp, and per-row undo button
- **P2** — Persist an "Amount Paying" preset value from the last unpaid quarter for one-click collect
- **P2** — Attach fee-structure preview (first 3 rows) inside the mapping panel before import
