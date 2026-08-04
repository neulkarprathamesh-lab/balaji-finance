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
