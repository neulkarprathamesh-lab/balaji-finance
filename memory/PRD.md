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
  - Bottom status strip: "Receipt number will be generated centrally"
- Preserved the original comprehensive form (all 9 receipt types including Bus/Voucher/Refund) at `/new-receipt-advanced` via new `NewReceiptAdvanced.js`, reachable via the header link.
- **ImportExcel.js**: uses a client-generated `batch_id` per file so undo is atomic; supports undo for **both** students and fee structures (uses the new `/bulk-delete` endpoints).

### Backlog (updated priorities)
- **P1** — Print A4 receipt to inherit the navy header/branding of the new cashier UI (currently uses the existing A4 layout — good, but could tighten header parity)
- **P1** — "Import History" page listing past batches with counts, user, timestamp, and per-row undo button
- **P2** — Persist an "Amount Paying" preset value from the last unpaid quarter for one-click collect
- **P2** — Attach fee-structure preview (first 3 rows) inside the mapping panel before import
