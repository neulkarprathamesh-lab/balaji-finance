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
### 2026-02-26 Final production pass (this session)
- **Python venv completes the detect/reuse/repair/create pattern**: Stage 7 now runs `python -c "import sys, pip"` against the existing venv; if it fails, the venv is deleted and recreated. Otherwise reused. Matches the pattern already applied to MongoDB, Backend service, Frontend service, and firewall rules.
- **Every required component in the installer now follows Detect -> Reuse-if-correct / Repair-if-drifted / Create-if-missing**, is idempotent (safe to re-run), and reports its action explicitly (`REUSED / REPAIRED / CREATED`) in `C:\balaji-fee\logs\installation-report.txt`.
- **End-to-end acceptance chain** enforced before `INSTALLATION SUCCESSFUL`: MongoDB ping -> `/api/version` -> `/api/auth/me` returns 401/403 -> frontend HTML contains React root/Balaji branding -> `BalajiFeeHub.exe` actually launches and stays alive 12s with a window title matching `*Balaji*` -> all services `AUTO_START`.
- **Nothing left as a "verify only" step**: MongoDB, Python venv, Backend service, Frontend service, Firewall rules, .env files, MongoDB config, Windows services, and the desktop app are all detect+manage, never assume.

### 2026-02-25 Additions — End-to-end user journey verification (this session)
- **Stage 13 extended with real user-journey acceptance tests**. `INSTALLATION SUCCESSFUL` now requires the ENTIRE chain to work end-to-end, not just individual components:
  1. **MongoDB -> DB layer**: `pymongo.ping()` succeeds (auto-repair retry if not).
  2. **Backend auth wiring**: `GET /api/auth/me` returns 401/403 (proves backend + DB layer + JWT middleware are wired correctly). 500 = DB layer broken and installer fails. Unreachable = installer fails.
  3. **Frontend serves the app**: `GET /` HTML is fetched and regex-matched against `Balaji|FeeHub|id="root"` — confirms the prebuilt React bundle is actually being served, not a blank page.
  4. **Desktop application launches**: `Start-Process $DESKTOP\BalajiFeeHub.exe`, sleep 12s, check `HasExited` — if crashed within 12s, fail with the exit code. If still alive, hunt for a window titled `*Balaji*` via `Get-Process | Where MainWindowTitle -match 'Balaji'`. Records `RUNNING (window: 'Balaji FeeHub')` in the report.
  5. **Restart persistence**: `sc.exe qc` on every service, verifies `AUTO_START` in output; auto-repairs any drift via `sc.exe config … start= auto`. The report explicitly says `ALL SERVICES AUTO_START (survives Windows reboot)`.
- **Failure surfaces the exact stage + remediation** — no more generic exit codes. `Die 90 'End-to-end journey verification'` names the failing chain link and points to `installation-report.txt` + `logs\*.err.log`.
- **Component report** now includes `Auth endpoint`, `HTML markup`, `Launch test`, and `Restart persistence` rows.

### 2026-02-24 Additions — Idempotent detect/reuse/repair/create (this session)
- **`Ensure-Service` + `Apply-NssmSpec` helpers**: refactored `Stage-Services` from destructive "remove-and-reinstall" to a real detect→inspect→reuse/repair/create state machine. If service exists AND `Application` + `AppParameters` match expected → `REUSED` (log paths/restart policy refreshed idempotently). If exists but mismatched → `REPAIRED` in place (no remove). If missing → `CREATED`.
- **External MongoDB service reused as-is**: if `Detect-MongoDb` finds an existing MongoDB Windows service (e.g. `MongoDB`), we DO NOT register a duplicate `BalajiFeeHub-Mongo` — instead Backend's `DependOnService` points at the existing service and we set it to `Automatic` + start it. Prevents two `mongod` fighting over port 27017.
- **`$Global:ComponentReport` matrix**: every stage records `Detection`, `Action`, `Port`, `Api` / `DbPing` / `Response` per component. Final report now prints structured `MongoDB / Backend / Frontend / Desktop / LAN` sections explicitly showing `Action taken: REUSED | CREATED | REPAIRED` and functional-test results — matches the user's requested output format exactly.
- **Fully idempotent**: running the installer twice is safe. Second run detects existing MongoDB → reuses. Detects existing services with correct config → reuses. Fixes drift automatically without touching production data.
- **CI overlay** already includes `install-main-server.ps1` (verified) so the CORE.zip's stale scripts get overwritten by the fresh repo version on every build. The Server EXE will always contain the latest `.ps1`.

### 2026-02-23 Additions — Self-diagnosing PowerShell installer (this session)
- **Complete rewrite from batch to PowerShell orchestrator**: `install-main-server.ps1` (587 lines) is now the single source of truth for the Main Server installation. `install-main-server.bat` becomes a 22-line thin wrapper (calls `powershell -NoProfile -ExecutionPolicy Bypass -File install-main-server.ps1`) so the Inno `.iss`, Start Menu Repair shortcut, and legacy docs all keep working unchanged.
- **14 stages, each with structured error handling and unique exit codes** (10-99, never generic 255). Each stage writes to both console (colour-coded) and `C:\balaji-fee\logs\installation-report.txt`.
- **Stage 1 - System check** (11-22): OS + 64-bit + Administrator + disk >= 5 GB + RAM >= 3 GB + LAN gateway + Firewall service (auto-repair) + msiserver + PowerShell 5+ + Python 3.11 x64 + pip.
- **Stage 2 - MongoDB detection (5 strategies)**: (A) Win32_Service PathName scan for any service running mongod.exe, (B) Registry `HKLM:\SOFTWARE\MongoDB\Server\*` in both 64-bit and WoW64 views, (C) recursive scan of `%ProgramFiles%\MongoDB`, `%ProgramFiles(x86)%\MongoDB`, `%ProgramData%\MongoDB`, (D) PATH lookup, (E) bundled fallback. Dedupes by full path, prefers service-installed candidate, extracts version. **This directly fixes the "where mongod fails" real-world regression.**
- **Stage 3 - Port conflict analysis**: 27017 free / held-by-our-Mongo / held-by-unknown-process (STOP + explain). Same for 8001 and 3000, tolerates our own restart.
- **Stage 4 - Existing install detection + auto-backup**: detects `mongodb\data\WiredTiger`, invokes `mongodump.exe` from the detected MongoDB's own bin directory (not PATH-dependent), aborts on backup failure. Copies backend/.env + frontend/.env as .bak.
- **Stages 5-8 - Copy source + venv + offline pip + config**: fresh venv creation with clear error on failure, offline pip install from wheelhouse, hard 13-package import verification, secure random JWT_SECRET generation, existing .env preserved.
- **Stage 9 - MongoDB install/reuse/start**: if detected → reuse (auto-start service if stopped); if missing → recombine split MSI, size-validate (>= 50 MB), silent msiexec (accepts 0 or 3010), re-detect via same 5-strategy scan after install.
- **Stage 10 - Firewall**: creates only 8001 + 3000 rules via `New-NetFirewallRule` (removes any stale ones first); explicitly removes any 27017 rule (Mongo stays 127.0.0.1-only, never LAN-exposed).
- **Stage 11 - Windows services**: NSSM registration with proper metadata: service description, `AppRestartDelay`, `AppExit Default Restart` (auto-restart on failure), `AppThrottle`, log rotation (20 MB), dependency chain Mongo -> Backend -> Frontend, all `SERVICE_AUTO_START` so they survive Windows reboot.
- **Stage 12 - Start with dependency-order verification**: Start-Service each in order, 3s settle, throws if not `Running`.
- **Stage 13 - Real functional verification**: MongoDB ping via pymongo (auto-repair: restart Mongo once), ports LISTENING via Get-NetTCPConnection, HTTP 200 on `/api/version` + `/` via Invoke-WebRequest with retry, desktop EXE existence, LAN IP non-loopback.
- **Stage 14 - Installation report**: colour-coded success summary + full audit trail written to `C:\balaji-fee\logs\installation-report.txt`.
- **GHA workflow overlay** updated to include the new `.ps1` file alongside the batch wrappers.

### 2026-02-22 Additions — Stage 3 MongoDB installer rewrite (this session)
- Reproduced on real Windows 11: `... was unexpected at this time` at `[3/14]` MongoDB stage. Root causes: (a) `%ERRORLEVEL%` was parse-time-expanded inside parenthesized `if/else` blocks (so post-msiexec check saw stale value), (b) nested `if not exist (…) else (…)` around a `for /f` on the same line confused cmd's parser.
- Rewrote Stage 3 as linear `GOTO`-labeled blocks with `if errorlevel 1` semantics and `!ERRORLEVEL!` where needed. Zero parenthesized `if (…)` groups in the stage now.
- New sub-stages: 3.1 detect existing mongod (reuse), 3.2 recombine split MSI, 3.3 locate MSI, 3.4 validate MSI size (>= 50 MB, guards against truncated downloads), 3.5 run msiexec (accepts 0 or 3010), 3.6 locate `mongod.exe`. Each failure path has a unique exit code (31/32/33/34/35) and a precise diagnostic message with common-cause hints.
- Existing MongoDB installations are now reused (no double-install). msiexec's "success reboot required" (3010) is treated as success.

### 2026-02-21 Additions — Native Electron desktop shell (this session)
- **Electron desktop application** (`/app/desktop/`) — real `BalajiFeeHub.exe`, not a Chrome-app hack. Single codebase serves both Server and Client PCs:
  - `main.js` auto-detects: probes `127.0.0.1:8001` first (Main Server PC), falls back to saved IP in `%APPDATA%\BalajiFeeHub\config.json`, then a parallel `/24` LAN scan (254 addresses in parallel per subnet). Saves successful IP so the user never re-enters it.
  - `renderer/connect.html` shows a professional connect screen with school branding, live progress line during discovery, and a manual `Main Server IP + Connect` fallback if auto-discovery fails.
  - Application menu: File (Reload / Change Main Server / Exit), View (fullscreen / zoom), Help (About).
  - `did-fail-load` handler shows the connect screen again if the Main Server goes offline mid-session.
  - Single-instance lock so re-launching just focuses the existing window.
  - External links opened via `shell.openExternal` — the app window is a chromeless Windows app, no browser tabs/address bar.
  - Icon = school-logo.ico (auto-generated in CI from the JPEG).
- **electron-builder config**: target `dir` (win-unpacked), asar-packed, x64 only. Output copied by the CI into `payload/04-desktop/` and picked up by both `.iss` installers.
- **Inno Setup rewired**:
  - Server `.iss`: postinstall now launches `{app}\04-desktop\BalajiFeeHub.exe` (no browser). Desktop + Start Menu shortcuts point to the Electron EXE with its embedded icon. Start Menu now has: Balaji FeeHub / Repair / Backup Now / Uninstall.
  - Client `.iss`: full rewrite. Installs Electron unpacked folder to `Program Files\BalajiFeeHub\`, creates Desktop + Start Menu shortcuts to `BalajiFeeHub.exe`, launches on post-install. No Python, no MongoDB, no Node, no Chrome, no WebView2 required on the client.
  - Fixed the Pascal syntax bug (`{ ... %{http_code} ... }` was closing the comment early → "Unknown identifier 'are'"): all Pascal block comments containing curly braces converted to `//` line comments.
- **`install-main-server.bat` step 13 rewritten**: no longer creates Chrome `--app` shortcut. Instead verifies `BalajiFeeHub.exe` exists in the payload; hard-fails install with clear banner if it's missing.
- **`install-client-pc.bat`**: simplified to informational output — Electron handles all discovery/connection now.
- **`backup-now.bat`**: new manual-backup script wired to the Start Menu `Backup Now` entry. Creates timestamped `mongodump` snapshot into `C:\balaji-fee\backups\manual-YYYY-MM-DD_HH-MM-SS\`.
- **GitHub Actions workflow additions**:
  - `actions/setup-node@v4` with Node 20
  - `yarn install --frozen-lockfile` in `/desktop/`
  - Copy generated `school-logo.ico` into `desktop/icon.ico` before build
  - `yarn build` → `desktop/dist/win-unpacked/BalajiFeeHub.exe`
  - Overlay verified output into `payload/04-desktop/` — throws hard if `BalajiFeeHub.exe` is missing
  - Compile-prereq validation now also checks the desktop EXE exists before ISCC runs
- **All previous production-hardening kept**: offline wheelhouse rebuild + verify, existing-install auto-backup, comprehensive post-install verification (service exists → RUNNING → port LISTENING → HTTP 200 → Mongo ping → LAN IP), CI env vars for import test, hard fail on any missing production import.

### Architecture (final)
```
                   INTERNET (download/updates only)
                          |
                      SCHOOL LAN
                          |
                  +-------v-------+
                  |  MAIN SERVER  |   BalajiFeeHub-Server-Setup.exe
                  |               |   . MongoDB (127.0.0.1 only)
                  |  BalajiFeeHub |   . Backend (FastAPI, uvicorn)
                  |     .exe      |   . Frontend (React, port 3000)
                  +-------+-------+   . Electron shell auto-connects local
                          |
             +------------+------------+
             |            |            |
             v            v            v
         PC 01        PC 02        PC 03            BalajiFeeHub-Client-Setup.exe
      BalajiFeeHub  BalajiFeeHub BalajiFeeHub       . Electron shell only
         .exe          .exe         .exe            . Auto-discovers Main Server
                                                    . Saves IP in %APPDATA%
```

### What still needs a real Windows machine (out of Linux CI scope)
- Reboot test: services auto-recover, `BalajiFeeHub.exe` opens without any manual action
- Cross-LAN client test: second PC on same subnet auto-discovers Main Server, saves IP, reconnects on next launch
- Internet-off test: full flow (login → student → receipt → print) works over LAN only

### 2026-02-20 Additions — Production-hardening pass (this session)
- **Offline wheelhouse rebuilt natively on Windows in CI** — GHA workflow now sets up Python 3.11 x64 on `windows-latest`, wipes and re-downloads the wheelhouse from `payload/03-source-code/backend/requirements.txt`. Because it runs on native Windows Python, environment markers (`sys_platform == "win32"`, `python_version == "3.11"`) are evaluated correctly and previously missing transitive deps (`colorama`, `tzdata`, `six`, `certifi`, etc.) are now bundled automatically. Wheelhouse is verified end-to-end by creating a clean venv, running `pip install --no-index --find-links wheels -r requirements.txt`, and importing 13 critical packages. Build fails red if verification fails, so no incomplete bundle can ever ship.
- **install-main-server.bat — comprehensive rewrite** (repo source-of-truth at `installer-sources/scripts/`, overlaid onto CORE.zip in CI):
  - Existing installation detection with automatic pre-repair backup via `mongodump` (falls back to raw file copy). Aborts if backup fails — never touches production data unprotected.
  - Existing `.env` files preserved (never overwritten with template).
  - Hard `INSTALLATION FAILED` banner + non-zero exit on any stage failure: MSI, venv, pip, deps import, service registration.
  - Full post-install verification block (step 12/14) that must all pass before `INSTALLATION SUCCESSFUL`:
    - `sc query` for each of `BalajiFeeHub-Mongo` / `Backend` / `Frontend` (service exists)
    - `sc query STATE = RUNNING` for each service
    - `netstat` LISTENING check for ports 27017, 8001, 3000
    - `curl` HTTP 200 on `/api/version` + frontend `/`
    - Python `pymongo.MongoClient.ping()` (backend → Mongo connectivity)
    - LAN IP is non-loopback (LAN reachability)
  - Auto-start (`sc config … start= auto`) confirmed for all 3 services so they survive Windows reboot.
- **repair-installation.bat — new** (repo overlay): mandatory pre-repair `mongodump` backup, offline wheelhouse re-install if wheels present, dep-import verification, health check, all with hard-fail exit codes. Database is never touched.
- **install-client-pc.bat — chromeless Windows-app mode** (repo overlay): desktop + start-menu shortcuts now launch Chrome/Edge with `--app=URL --new-window` so Balaji FeeHub appears as a native-looking chromeless application window, not a browser tab. Auto-detects Chrome first, falls back to Edge, refuses to install if neither present.
- **Inno Setup `.iss` refactored** to properly capture exit codes: preflight, main install, and health check now orchestrated from `[Code]::CurStepChanged(ssPostInstall)` via `Exec()` + `ResultCode`. Any non-zero exit shows a modal `INSTALLATION FAILED` MessageBox with script name + exit code + likely causes, then `Abort` — the whole install rolls back cleanly instead of silently continuing to a half-installed state.
- **`school-logo.ico` auto-generated** in CI from `school-logo.jpeg` via ImageMagick (`magick.exe`), so the installer keeps the Balaji branding without requiring a hand-authored .ico in the repo.
- **CI path validation step** — `Test-Path` guards on both `.iss` files, generated `.ico`, payload root, client subfolder, and ISCC.exe before compile; fails fast with a precise error if anything is missing.
- **Client + Server `.iss` `Source:` paths corrected** to `payload\BalajiConventFeeSoftware-v1.0\...` so ISCC finds the workflow-extracted CORE.zip payload.
- **Small unrelated fix**: `FeeStructure.js` was missing `Eye` import and `preview`/`setPreview` state — added.

### Files touched this session
- `installer-sources/scripts/install-main-server.bat` — 443 lines, comprehensive rewrite
- `installer-sources/scripts/repair-installation.bat` — 137 lines, new
- `installer-sources/scripts/install-client-pc.bat` — 126 lines, new (--app mode)
- `installer-sources/BalajiFeeHub-Server-Setup.iss` — refactored `[Run]` → `[Code]::CurStepChanged`
- `.github/workflows/build-installers.yml` — added Python setup, overlay step, wheelhouse rebuild, wheelhouse verification, ICO generation, path validation
- `frontend/src/pages/FeeStructure.js` — lint fixes (`Eye`, `preview`, `setPreview`)

### What still needs a real Windows machine (out of Linux CI scope)
- Physical Windows 10/11 reboot test → verify services auto-start and database data persists
- Cross-LAN client test → second PC on the same subnet reaches the server
- Native desktop shell EXE (Electron/PyWebView) — deferred per user directive until server stack is proven stable in real deployment. Interim: Chrome/Edge `--app` mode delivers the chromeless-window experience.

### 2026-02-17 Additions — Session log
- **Production Data Purge System** — new router `/app/backend/routers/production.py` with `GET /api/production/purge/preview` and `POST /api/production/purge` (Admin PIN + phrase "PURGE DEMO DATA"). Wipes 11 transactional collections (students, receipts, adjustments, payment_extensions, reminders, notices, audit_log, config_snapshots, updates, backups, diagnostics_snapshots) and resets all counters; preserves 10 master collections (departments, classes, fee_heads, fee_structures, receipt_types, bus_stops, bus_routes, users, settings, config_defaults). Standalone CLI at `/app/scripts/production_purge.py` for offline use.
- **Fresh Production ZIP builder** — `/app/scripts/build_final_zip.py` produces `/app/dist/BalajiFeeHub-v1.0-FINAL.zip` and publishes a copy to `/app/frontend/public/downloads/BalajiFeeHub-v1.0-FINAL.zip` for in-app admin download. Excludes __pycache__/node_modules/keys/backups/updates. `POST /api/deliverables/rebuild-zip` triggers a fresh rebuild on demand (Admin PIN). **Built: 4.70 MB, 156 files.**
- **Installation Manual generator** — `/app/frontend/src/lib/installationManual.js` uses jsPDF to build a fully-illustrated 10-section PDF: System Requirements → Main Server install → Client PCs → First-time config → Excel import → Daily ops → Software updates → Backup/recovery → Troubleshooting → Appendix. Includes cover page (logo + brand), table of contents with correct page numbers, per-page header/footer, section styling. "Generate & Download Manual" button on Delivery Center.
- **Delivery Center redesigned** — new headline row with Installation Manual card + Purge Demo Data card (with preview panel showing exact row counts per collection). New "Production Release" manifest section links to the freshly-built ZIP + rebuild endpoint. New "Software updates history" line in Version & Audit.
- **Rebranding to "Balaji FeeHub"** (from earlier this session): manifest.json, index.html, Login (new hero + password eye toggle), Layout sidebar.
- **Offline-LAN Software Update System** + **Universal Receipt Template Engine** + **Logo replaced everywhere** + **DV-YYYY-NNNNNN voucher numbering** (from earlier this session). See prior entries below.

### 2026-02-17 Additions
- **Rebranding to "Balaji FeeHub"**: manifest.json (short_name/name/description), index.html title/meta, Login.js (new hero: Balaji FeeHub / Fee Management System / Version 1.0 + full school identity block), Layout.js sidebar branding. All still show the new circular school logo.
- **Password visibility toggle** on the login screen (Eye / EyeOff lucide icons, `data-testid="login-password-toggle"`).
- **Offline-LAN Software Update System** — full feature complete + 9/9 pytest passing. Files: `/app/backend/routers/updates.py`, `/app/scripts/build_bcupdate.py`, `/app/frontend/src/pages/SoftwareUpdates.js`, `/app/backend/tests/test_updates.py`.
- **Universal Receipt Template Engine** — new `/app/frontend/src/components/receipt/` with PaperSizes, ReceiptFrame, ReceiptPrimitives, ReceiptToolbar, receiptExporter (jsPDF + html2canvas + SVG + Email PDF), ReceiptEngine + 4 template bodies (Fee, DebitVoucher, Money, Bus). Two themes (Classic B/W default, Balaji Colored). Default paper A5 portrait. Refactored `ReceiptView.js`.
- **Logo replaced** everywhere (single file overwrite: `/app/frontend/public/school-logo.jpeg`). All 15+ pages reference this path.
- **Voucher numbering**: `V-YYYY-NNNNNN` → `DV-YYYY-NNNNNN`.
- **Dependencies added**: `jspdf@4.2.1`, `html2canvas@1.4.1`.

### 2026-02-17 Testing Outcome
- **Backend**: 17/17 pytest pass (9 test_updates.py + 8 test_iter6_session.py). No critical or minor issues.
- **Frontend**: All required data-testids present. Full E2E Playwright flow through Login → sidebar → Software Updates → Receipt View → paper-size switch (A5→A4 changed frame width 559→793px) → PNG download → More menu → New Receipt page. Zero console errors.
- **DV voucher numbering** verified live: DV-2027-000023 produced this session.
- **Public key fingerprint** shown as 99d275…c02b on the Software Updates page.
- Retest needed: **false**. Main agent can self-test.

### Notes for next session (from testing agent)
- Route is `/new-receipt` (not `/receipts/new`).
- Consider `--reload-exclude tests/*` on the backend supervisor command to avoid uvicorn --reload storms during pytest writes.
- Consider validating at least one signature slot is true on receipt-type saves.

### 2026-02-17 Testing Outcome (iteration_7)
- **Backend**: 12/12 pytest pass (`test_iter7_delivery_purge.py`) + prior 17/17 still green — 29 total tests. No critical/minor issues.
- **Frontend**: All required data-testids present. Purge preview UI flow works with PIN gating. jsPDF Installation Manual download triggers with filename `BalajiFeeHub-Installation-Manual-v1.0.0.pdf`. Zero console errors.
- **Purge execute path** intentionally NOT invoked to preserve seeded data. Wrong-phrase attempt verified idempotent.
- **Retest needed**: false. **Main agent self-test**: not needed.

### 2026-02-17 Public Verification Portal
- **Redesigned `Lookup.js`** — parents scan a receipt QR (points to `/lookup/{number}`) and land on a proof-of-payment page with a big VERIFIED badge (or CANCELLED banner for cancelled receipts), meta strip (receipt no, date, AY, verified-at timestamp), student card, annual ledger, and the full receipt rendered by the universal engine with a public toolbar (Print + PDF + PNG/JPEG/SVG downloads, no admin actions).
- **`ReceiptEngine.js` + `ReceiptToolbar.js`** — accept a new `publicMode` prop that hides Cancel / two-up buttons; controls hidden when `showControls=false` (used by the portal).
- Uses existing `/api/public/lookup/{number}` endpoint (no auth). Guarded route 404 returns a "Receipt Not Verified" screen.

### 2026-02-17 Factory Reset (Administrator-only System Maintenance)
- **New route `/factory-reset`** (admin-only) + sidebar entry (Bomb icon).
- **5-gate security**: role=administrator + `X-Admin-Pin` header + password re-verify + Factory Reset PIN (default `2580`, changeable via `/api/production/factory-reset/change-pin`) + confirmation phrase `DELETE ALL SCHOOL DATA`. Every wrong gate returns the right HTTP status (400/401).
- **Auto-safety**: full DB backup via `_create_backup_zip` runs FIRST; config snapshot runs second. If the backup fails, the reset is aborted before anything is deleted.
- **Deletes**: 13 transactional collections + all non-administrator users + every counter + staged/rollback updates on disk.
- **Preserves**: 10 master collections (settings, departments, classes, fee_heads, fee_structures, receipt_types, bus_stops, bus_routes, config_defaults, license) + administrator account(s) + school logo.
- **Audit**: first row of the fresh DB records the reset event (admin name, timestamps, backup id/file, deleted counts).
- **UI**: 4-stage flow — status card → red Bomb "Begin" → full-screen WARNING with acknowledgement checkbox → password + factory PIN + phrase form → progress spinner → success screen with backup file path + counts + "Go to Dashboard" / "Open Setup Wizard". Change-PIN modal in the top-right card. Every element carries a `data-testid`.
- **Endpoints**:
  - `GET /api/production/factory-reset/status` — counts + `is_default_pin` flag (never leaks the PIN).
  - `POST /api/production/factory-reset/change-pin` — password re-verify then update to a 4-8 digit PIN.
  - `POST /api/production/factory-reset` — executes all 10 steps.

### 2026-02-17 FINAL Production ZIP delivered
- `/app/dist/BalajiConventFeeSoftware_v1.0_FINAL.zip` — **14.16 MB, 192 files across 13 top-level folders** (01-install-main-server, 02-install-client-pc, 03-source-code, 04-database, 05-services, 06-excel-templates, 07-user-manuals, 08-lan-installation, 09-printer-setup, 10-backup-restore, 11-optional-services, 12-default-admin, docs).
- Published to `/downloads/BalajiConventFeeSoftware_v1.0_FINAL.zip` for in-app admin download.
- `03-source-code/` is refreshed on every build (161+ files: backend, frontend/src, frontend/public, scripts/, .env.templates, version.json).
- `docs/` includes `CHANGELOG.md`, `API_DOCUMENTATION.md`, `DATABASE_DOCUMENTATION.md`. `START_HERE.md`, `RELEASE_NOTES.md`, `LICENSE_AND_OWNERSHIP.md`, `FINAL_VERIFICATION.md`, `LOAD_TEST_REPORT.md` at ZIP root.
- Rebuild anytime via Delivery Center → "Rebuild the production ZIP now" (Admin PIN).
- **Download URL** (both localhost and preview): `/downloads/BalajiConventFeeSoftware_v1.0_FINAL.zip`

### 2026-02-19 Truly Self-Contained FINAL Package
- **Bundled inside the ZIP**: MongoDB Community Windows MSI (597 MB) in `05-services/`, NSSM 2.24 (`05-services/nssm.exe`), 48 Windows-specific Python wheels for offline `pip install --no-index --find-links wheels/`, prebuilt React static site in `03-source-code/frontend/build/` — no Node/npm required at install time.
- **`install-main-server.bat` — 14 stages** — silent MongoDB MSI install → venv → OFFLINE pip install from bundled wheels → secure JWT → LAN IP detection → firewall (only 3000+8001) → services registered via bundled NSSM (Mongo→Backend→Frontend dependency chain, all AUTO-start) → HTTP-200 post-install health checks → desktop shortcut.
- **`preflight.bat` — every check now labelled** `[REQUIRED]` (blocks install), `[AUTO-INSTALLED]` (bundled), `[OPTIONAL]` (nice-to-have). BLOCK counter and readable status per row.
- **INSTALLATION_MANUAL.pdf** — 13-section illustrated PDF generated via ReportLab (cover page, per-page header/footer, page numbers). Includes explicit "Not yet tested on clean Windows PC" transparency section.
- **SHA256SUM.txt** — bundled at the ZIP root AND published next to the download.
- **Package audit script** verifies every required file is present in the ZIP; no recursive self-inclusion. All checks pass.
- **Preflight (`preflight.bat`)**: 17 non-destructive checks — Administrator, 64-bit, Windows 10/11 build, 5 GB disk, Python found, Python >=3.11, pip, MongoDB, port 27017/8001/3000 availability, LAN IP detection, Firewall service, curl, PowerShell 5+, NSSM bundled, node informational. Exits non-zero on any fail with the exact remediation.
- **Main installer (`install-main-server.bat`)**: 12 numbered stages — creates `C:\balaji-fee` tree, copies source, creates venv, `pip install` from the cleaned requirements.txt, generates secure JWT via PowerShell, auto-detects LAN IP, writes `backend/.env` + `frontend/.env`, writes `mongod.cfg` (bindIp 127.0.0.1 only — MongoDB never exposed to LAN), opens firewall for 3000+8001 only, registers 3 Windows services (Mongo → Backend → Frontend, in dependency order), starts them, runs post-install HTTP 200 checks, creates desktop shortcut. Reports INSTALLATION SUCCESSFUL / FAILED with the exact reason.
- **Service registration (`register-services.bat`)**: NSSM-first (log rotation, auto-restart, dependency chains); sc.exe fallback if NSSM not bundled. Frontend uses Python's built-in `http.server` — **no Node dependency on the Main Server**.
- **Uninstall / Repair**: `uninstall.bat` stops and removes services (keeps backups + data); `repair-installation.bat` re-copies source and re-installs deps without touching the DB.
- **Client installer (`install-client-pc.bat`)**: 6 stages — detects Chrome/Edge, PowerShell auto-discovery of the Main Server on the LAN (10-second parallel scan of the /24), manual fallback, HTTP 200 verification, confirmation, desktop + Start Menu shortcut, auto-opens the browser. **Zero Python/Node/MongoDB required on clients.**
- **Client `uninstall` + `repair`** provided.
- **requirements.txt** already cleaned (2026-02-17): `emergentintegrations`, `boto3`, `python-jose`, `requests-oauthlib`, `jq`, `black`, `isort`, `flake8`, `mypy` all removed; `openpyxl` added.
- **New FINAL ZIP**: `BalajiConventFeeSoftware_v1.0_FINAL.zip` — 42.45 MB · 196 files · SHA-256 `12b6d077d11b5be274d6549b915195a305df236e5689a17de73cf7f046baa77b`.
- **Honest limitation**: agent runs in a Linux container. Every `.bat` was hand-written to Windows conventions but the mandatory Windows 10 + Windows 11 clean-machine tests must still be executed by the user.
- **Root cause**: `requirements.txt` listed `emergentintegrations==0.2.0` which does not resolve on stock Python 3.11 (Windows pip). Confirmed via grep: **zero imports** in the entire backend — it was legacy.
- **Additional removals** (all unused and known to cause Windows pip issues): `boto3`, `python-jose`, `requests-oauthlib`, `jq`, plus dev-only linters (`black`, `isort`, `flake8`, `mypy`) kept out of the production requirements.
- **Added**: `openpyxl>=3.1.2` (silently needed by pandas Excel round-trip on the imports flow).
- **Verified**: `pip install --dry-run -r requirements.txt` succeeds, backend restarts clean on the new requirements, 17/17 pytest still pass.
- **Rebuilt ZIP**: new file + new SHA-256, published to `/downloads/BalajiConventFeeSoftware_v1.0_FINAL.zip`.

### 2026-02-19 Split delivery for large-file browser downloads
- **`scripts/build_split_zip.py`** — splits the 603 MB monolith into three downloadable pieces:
  1. `BalajiConventFeeSoftware_v1.0_CORE.zip`  — **36.91 MB · 249 files** (code, installers, wheels, docs, prebuilt frontend, NSSM). Small enough for any browser.
  2. `mongodb-windows-x86_64.msi.001` — **300 MB** (first half of MongoDB MSI).
  3. `mongodb-windows-x86_64.msi.002` — **269.35 MB** (second half).
- **`install-main-server.bat`** now detects the two .001/.002 parts under `05-services/` and recombines them with Windows `copy /b .001 + .002 mongodb-windows-x86_64.msi` before running the silent install. If a full MSI is already present it is used as-is (backwards compatible).
- **`/downloads/SPLIT_MANIFEST.json`** and **`/downloads/SHA256SUM.txt`** carry every part's SHA-256 for post-download verification.

## Remaining Production-Release Work (roadmap for next session)
- P0: **Full E2E QA sweep** (testing agent across every module — Login, Dashboard, Students, Fee Collection, Every Receipt Type, Debit Voucher, Adjustments, Extensions, Bus, Reports, Verification, Parent Portal, Backup/Restore, Config Export/Import, Snapshots, Software Updates, Diagnostics, Delivery Center, Audit Logs, Global Search).
- P0: **Debit Voucher deep enhancement** — approval workflow (threshold-based, default ₹10 000, admin-editable), person-wise ledger, dedicated DV Reports page, print_count/printed_by tracking, cheque/DD/UPI fields.
- P0: **Production data purge** — remove all demo/test students, receipts, vouchers, adjustments, reminders, audit entries; keep master (departments, classes, fee heads, receipt types, bus stops, system settings).
- P0: **Global Search unified** — return students + receipts + vouchers in one panel; make "Paid To" a searchable entity.
- P1: **Final production ZIP rebuild** at `/app/dist/BalajiFeeHub-v1.0-FINAL.zip` with new branding + engine + software update system + all installers/utilities.
- P1: **Installation Manual PDF** — 10 sections (Requirements → Main Server install → Client PC install → First-time config → Excel import → Daily ops → Software updates → Backup/recovery → Troubleshooting → Appendix), auto-generated with jsPDF from the codebase.

## Version
- `/app/version.json` — v1.0.0 (2026-02-04)
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

### 2026-02-04 (continued 7) — 4 new features
- **Cash-Denomination Sheet** — In `/day-end`, an inline table lets cashiers enter counts for ₹500/₹200/₹100/₹50/₹20/₹10/₹5/₹2/₹1. Live subtotals + a *Counted Cash* row + a big status card that computes *Expected Cash* (from the Cash mode total) vs *Counted Cash* → shows **Match** (green) or **Excess / Short** (red) with the exact ₹ difference and a "safe to hand over" / "recount before handover" recommendation.

### 2026-02-04 (continued 8) — Receipt Types + Admin PIN + Config Export/Import
- **Receipt Type Selector** (`/new-receipt`): Tile/card grid showing 8 school types + Bus tile with icon, prefix badge, department name and description. Clicking a tile routes to `/new-receipt/entry?type=<id>` (the existing cashier UI, pre-loaded with the type's prefix/department).
- **Receipt Types Management** (`/receipt-types`, admin-only): Full CRUD table — order, prefix, name, department, category, status pill (Active / Disabled / Archived) + Edit / Enable-Disable / Delete actions. Delete is protected: if the type has existing receipts, backend returns 409 with `can_archive: true` and the UI offers **Archive instead**. Every mutation opens the AdminPinPrompt.
- **Finance page** (`/finance`): Standalone Debit Voucher entry — payee, department, purpose, multi-line items with live total, payment mode + reference, remarks. Manager/Admin/Accountant only. Uses `DV-2026-000XXX` numbering via `next_receipt_number_by_prefix`.
- **Admin PIN system** — Reusable `<AdminPinPrompt/>` modal supports single-PIN (`mode: 'pin'`) and **dual auth** (`mode: 'dual'`, requires PIN + admin password). Backend deps `require_admin_pin` and `require_admin_dual` read PIN/password from `X-Admin-PIN` / `X-Admin-Password` headers. New probe `POST /api/auth/admin-pin/verify` lets the UI validate before opening a sensitive action. Existing PIN infrastructure on `users.pin_hash` is reused.
- **Config Export / Import** (`/config-io`):
  - Export → `GET /api/config/export` streams a ZIP with `receipt_types.json, departments.json, classes.json, fee_heads.json, fee_structures.json, settings.json, bus_routes.json, users.json (no passwords/PINs), manifest.json, README.md`. Requires admin PIN.
  - Import → `POST /api/config/import` accepts a ZIP + `?replace=true|false`. Merge mode upserts by id; replace mode drops the collection then inserts. Requires **dual authorisation** (PIN + password). Users are only added if absent, with a random temp password and null PIN (must be reset by admin after import). Returns per-collection added / updated counts.
- **Version info** — New `GET /api/version` returns `app_version, database_version, receipt_template_version, app_template_version, build_date, developer, server_time`. Rendered as a dark strip at the top of Config I/O.
- Backend converted these sensitive endpoints to `require_admin_pin`: `POST/PATCH/DELETE /receipt-types`, `POST /receipt-types/{id}/archive`, `POST /receipt-types/reseed-defaults`, `GET /config/export`. `POST /config/import` uses `require_admin_dual`. All failures are logged to the audit collection with the actor id + event tag.

- **PWA Manifest** — Proper `public/manifest.json` (name, icons, theme_color `#0f172a`, standalone display). `index.html` now links `manifest.json` + `icon` + `apple-touch-icon` + a real page title "Balaji Convent Fee Software". Client PCs that Chrome/Edge → *Install app* now get a real desktop icon with the school logo.
- **Setup Wizard** at `/setup-wizard` (admin-only nav item) — 8-step checklist (change admin password, school info, staff logins, static IP, seed fees, backups, client-PC shortcut, first receipt) with progress bar, LocalStorage persistence, and one-click CTA to the relevant page.
- **Signed Update Feed** — `public/downloads/version.json` is fetched on every layout mount. If `version !== CURRENT_VERSION` (constant `1.0.0` in Layout.js), an amber banner appears for administrators with the version, release date, notes, a **Download** button and a **Dismiss** action (dismissal stored in LocalStorage per-version so it reappears on the next release).


### 2026-02-04 (continued 9) — Backup + Receipt-Type full editor
**One-click Backup Before Update**
- New `_create_backup_zip()` helper dumps every collection to a ZIP under `/app/backups/`, computes a SHA-256 checksum, verifies via `ZipFile.testzip()`, and records `id/filename/size/collections/checksum/kind/created_at/created_by` in a `backups` collection.
- **Auto-backup**: `POST /api/config/import?replace=true` now creates a `pre-import` backup BEFORE touching any collection. If the backup fails the import is refused (500).
- Manual endpoint `POST /api/config/backup` (PIN-gated) — returns the manifest.
- Listing `GET /api/config/backups` and streaming download `GET /api/config/backups/{id}/download` (PIN-gated).
- Frontend: new **Database Backups** panel on `/config-io` with **Backup Now (PIN)** button, table (Created / Kind pill / Filename / Size / Collections / By / Download). Import-summary card also shows the auto-backup filename + size + first 16 chars of the SHA-256.
- Verified: manual backup created a 14.9 KB ZIP covering 16 collections with a valid sha256 checksum, file present at `/app/backups/balaji-manual-2026-08-04_134803-v1.0.0.zip`.

**Phase 2 close-out — full Receipt Type editor**
- Backend `ReceiptTypeIn` extended with: `paper_size (A4/A5/Thermal80)`, `orientation (portrait/landscape)`, `header_text`, `footer_text`, `watermark_text`, `watermark_enabled`, `barcode_enabled`, `qr_enabled`, `signature_area_enabled`, `computer_generated_note`, `starting_number`, `current_number`, `auto_reset_yearly`, and a `fields` dict with 16 per-type toggles (Admission-No, Roll-No, Parent Name, Mobile, Class, Division, Department, Academic Year, Session, Fee Head, Amount in Words, Payment Mode, Transaction ID, Cashier Name, Authorized By, Remarks).
- Frontend edit modal now has 4 tabs: **General / Printing / Numbering / Fields**. Every save requires the Admin PIN. Manual reset of the current sequence flagged as Phase 3 (dual-auth required).
- Verified: PATCH to `EP` — paper=A4/landscape, watermark on "OFFICIAL", `fields.authorized_by=true` — all persisted correctly.

- **Amount Suggestions**: On student load, `Amount Paying` pre-fills with the top-priority pending head's outstanding, and a "Next Quarter" chip refills it any time.
- **Sibling Split**: When the loaded student has siblings on the same guardian mobile, an amber banner appears ("N sibling(s) on same guardian mobile — <Names>") with an "Include siblings in one payment" toggle. When on, all siblings' pending heads merge into one priority-sorted list, and each row is tagged with the student name. Submit creates **one receipt per student** in a single flow, with a family split preview in the right rail.
- New backend endpoints: `GET /api/students/{id}/siblings`, `GET /api/imports/history`. Both used exclusively by the new UI.
- **P1** — Print A4 receipt to inherit the navy header/branding of the new cashier UI (currently uses the existing A4 layout — good, but could tighten header parity)
- **P1** — "Import History" page listing past batches with counts, user, timestamp, and per-row undo button

### 2026-02-04 (continued 10) — Print Template Renderer wired
- `ReceiptView.js` now dynamically loads the matching receipt-type via `useReceiptType()` (by `receipt_type_id`, else by number prefix e.g. `EP-2026-000003` → `EP` type) and applies every configured toggle to the printed A4:
  - **Paper size + orientation** — `@media print { @page { size: A4|A5|Thermal80 portrait|landscape; margin: 8mm; } }` scoped per receipt so preview = PDF export = physical print (WYSIWYG).
  - **Header / footer text** — extra lines rendered above the header block and below the footer.
  - **Watermark** — faint diagonal overlay text (configurable text like `ORIGINAL` / `DUPLICATE`), shown at 0.06 opacity so it doesn't compete with the receipt content.
  - **QR / Barcode** — QR toggle hides the corner QR; barcode toggle renders a stylized CODE128-look strip with the receipt number below.
  - **Signature area** — hides the entire NOTES + RECEIVED BY + AUTHORIZED BY row when disabled.
  - **Computer-generated note** — configurable text swapped into the first bullet of the NOTES list.
  - **All 16 field toggles** (Admission-No, Roll-No, Parent Name, Mobile, Class, Division, Session, Department, Academic Year, Fee Head, Amount-in-Words, Payment Mode, Transaction ID, Cashier Name, Authorized By, Remarks) — each row / block is conditionally rendered.
  - **Dynamic school + department names** — pulled from the receipt-type record so admins can rename EP → "Balaji Convent English Primary School" or add a new type entirely without code changes.
- Verified end-to-end: PATCH to EP receipt-type turning off QR + on Barcode + hiding Transaction ID + on Authorized-By + custom footer text → reloaded a real EP receipt → all four changes visible on the printed page (screenshot captured; console-log spot-checks confirm each toggle applied).
- The same renderer engine is reused across every school-category receipt type — future types added by admins inherit the toggle system with zero code changes.

## 2026-02-04 (continued 23) — Zero-Edit Client Installer + Scanner Backlog Note
- **Client installer auto-discovery**: `install-client-pc.bat` rewritten so nothing needs to be edited before running. Uses PowerShell 7's parallel foreach to sweep the LAN's own /24 subnet (from `Get-NetIPConfiguration`), hits `http://<candidate>:8001/api/version` with a 1-second timeout, and picks the first machine that responds. Presents "Found Main Server at 192.168.1.X — use this server? [Y/n]". Falls back to a manual IP prompt that verifies `/api/version` before accepting the address. Also saves the chosen IP to `%USERPROFILE%\.balaji-fee-server.txt` for reference on re-runs.
- Creates desktop AND Start-menu shortcuts pointing at `http://<MainIP>:3000`.
- **Scanner integration** noted as intentionally deferred (owner-confirmed non-blocker). Current flow (Windows scanner → PDF → Upload via app) works today; a Twain/WIA one-click scan would require a native helper and is on the backlog for a future release.
- FINAL ZIP rebuilt; SHA-256 updated.


- **Load test**: seeded 1,026 test students (`LT-*` prefix) on top of the real config data, then ran a 30-second, 8-worker mixed-workload test on the LAN-equivalent endpoint (localhost:8001). Result: **121 req/s sustained, 0 errors, p95 < 165 ms on every hot endpoint** (defaulters 165ms, dashboard 133ms, students search 67ms, bus-stops 63ms, fee-structures 66ms, receipt-types 81ms).
- WAN run through the Cloudflare-fronted preview URL was also clean (224 req in 30s, sporadic edge resets only).
- New harness at `/app/backend/tests/load/loadtest.py` — bundled into the FINAL ZIP under `03-source-code/backend/tests/load/`. School can re-run with `python loadtest.py --load-only`.
- **`LOAD_TEST_REPORT.md`** and **`FINAL_VERIFICATION.md`** shipped to `/app/dist/BalajiConventFeeSoftware-v1.0/` and mirrored to `/app/frontend/public/downloads/` for direct download.
- **testing_agent iteration_5**: 60/60 tests passing (added new `test_load_verify.py` with 14 smoke tests covering every endpoint on the final checklist), zero critical/minor issues, defaulters report completed well under 3 s on the 1,026-student dataset. Cleaned leftover "TSTX" receipt type flagged by the tester.
- FINAL ZIP rebuilt with load-test harness inside; SHA-256 recomputed and included in FINAL_VERIFICATION.md.

## Version 1.0 — READY FOR PRODUCTION
Load-tested. Verified by an independent testing agent. Full ownership package delivered.


### Bulk Bus Fare Update
- New `POST /api/bus-stops/bulk-update` (admin/manager) with 4 operations: `increase_percent`, `decrease_percent`, `increase_fixed`, `decrease_fixed`. Optional `stop_ids[]` scope, `round_to` (₹1/10/50/100), `preview` toggle, `effective_date`, `reason`.
- **Preview mode** returns every touched stop with `current_fare`, `new_fare`, `delta`, `students_affected`, plus totals.
- **Apply mode** writes the new fares, stamps `last_fare_change_at` / `last_fare_change_by`, and records a rich audit entry (operation, value, students affected, reason).
- **Frontend**: new "Bulk Fare Update" button on the Bus Stop Master toolbar opens a modal with the 4 operations as chips, value + rounding + effective-date + reason inputs, a Preview button, and a scrollable delta table. Confirm & Apply requires explicit acknowledgement.

### Configuration Snapshots
- New router `routers/snapshots.py` with a new `config_snapshots` collection that stores the full config as embedded JSON per academic year.
- Endpoints: `GET /snapshots` (list), `POST /snapshots` (create, PIN-gated), `GET /snapshots/{sid}`, `GET /snapshots/{sid}/export` (ZIP with per-collection JSON + manifest, PIN-gated), `GET /snapshots/{a}/compare/{b}` (per-collection added/removed/changed counts + top 20 changed rows), `POST /snapshots/{sid}/restore` (DUAL-AUTH), `DELETE /snapshots/{sid}`.
- Restore replaces every configuration collection (`settings`, `departments`, `classes`, `fee_heads`, `fee_structures`, `receipt_types`, `bus_routes`, `bus_stops`) — historical students, receipts, adjustments, extensions are untouched.
- **Frontend**: new page `/config-snapshots` (admin + manager) with a Snapshots table (Year, Label, Records, Created), a "New Snapshot" modal, Export / Restore / Delete per row, and a Compare section that picks two snapshots and prints a per-collection diff table.
- Nav entry: sidebar → **Config Snapshots** (below Settings, above Delivery Center).

### Verified end-to-end
- Bulk fare preview: 61 stops → `current_total=₹68,450` → `new_total=₹75,400` at +10% rounded to ₹10 (sample: stop 1 Butibori-Rukmani Township ₹850 → ₹940).
- Snapshot create: archived 9 receipt types · 4 depts · 87 classes · 21 fee heads · 44 fee structures + settings + bus routes + bus stops in one go.
- 47/47 pytest passing.
- Distribution ZIP rebuilt at `/app/dist/BalajiConventFeeSoftware-v1.0-FINAL.zip` (1.7 MB compressed, complete source).


Per owner request, the software will no longer expose its own source code / installer ZIP from inside the running app (security + simplicity). The Delivery Center is now trimmed to daily-ops artefacts only:
- **In-app Delivery Center** (Administrator → Delivery Center) now shows 4 sections:
  - Database Package (latest backup + trigger new backup)
  - Configuration Export (school settings / departments / classes / fee structures / receipt types / bus routes)
  - Documentation (License & Ownership + Release Notes v1.0)
  - Version & Audit (`/api/version`, `/api/diagnostics`)
- **Removed** from the in-app manifest and the router: `Complete Project Source` section, `Deployment Package` section, `/api/deliverables/receipt-types-json`, `/api/deliverables/full-project-metadata`. `/downloads/BalajiConventFeeSoftware-v1.0.zip` is no longer served from the live app.
- **New one-shot offline archive**: `/app/dist/BalajiConventFeeSoftware-v1.0-FINAL.zip` — the complete owner-portable project package (frontend, backend, docs, installers, assets, license & release notes). This is the ZIP the school stores on the Main Server + an external hard drive.
- **Verified**: manifest returns exactly 4 sections; `/downloads/*.zip` now 404s (no longer inside the app); 47/47 pytest still passing; final offline ZIP built.


- **New page** `/delivery-center` (Administrator only, sidebar → Delivery Center) — a single hub that lists every deliverable in categorised cards: Complete Project Source, Deployment Package, Database Package (latest backup + trigger new), Configuration Export, Receipt Templates (all 9 as JSON), Documentation (License + Release Notes + Self-Host Guide), Version & Audit. Each row shows size, last-modified date, and a Download button. PIN-gated endpoints prompt the admin at click time.
- **New router** `/app/backend/routers/deliverables.py` with:
  - `GET /api/deliverables/manifest` — the aggregator that drives the UI.
  - `GET /api/deliverables/license` — streams the signed LICENSE_AND_OWNERSHIP.md.
  - `GET /api/deliverables/release-notes` — streams RELEASE_NOTES_v1.0.md.
  - `GET /api/deliverables/receipt-types-json` — every receipt-type record in one JSON.
  - `GET /api/deliverables/full-project-metadata` — routers, collections, env-vars, build commands (for developer onboarding).
- **Ownership document** (`LICENSE_AND_OWNERSHIP.md`) shipped in the dist ZIP and downloadable individually — declares Balaji Convent as sole owner, explicitly states no license locks / no telemetry / no kill switches / no obfuscation, and lists the freedoms guaranteed (maintain, modify, enhance, rebuild, third-party dev, internal distribution).
- **Release Notes v1.0** (`RELEASE_NOTES_v1.0.md`) — highlights, architecture, verification results (47/47 tests, 23/23 routes), known limitations, support pointers.
- **Both files** also copied to `/app/frontend/public/downloads/` so they're publicly linkable, and packaged into the fresh dist ZIP (15 MB, published to `/downloads/BalajiConventFeeSoftware-v1.0.zip`).
- **Verified**: `/api/deliverables/manifest` returns 7 sections with app_version=1.0.0, license endpoint streams the MD file (HTTP 200), receipt-types JSON returns all 9 types. 47/47 pytest passing.

## Version 1.0 — Production Ready
Every agreed feature is implemented, every menu / button works, all backend tests are green, and the software has been declared owner-portable via the on-page License & Ownership section.


- **Bus Stop Manager UI** (`/bus-stops`, admin/manager/accountant): full CRUD for stops. Add via modal (auto-locks stop_no on edit), inline Edit, Deactivate/Activate toggle, and Delete (admin-only, refuses if any student is still assigned). Live search on number or name. Header shows totals + average monthly fare.
- **Backend endpoints** added: `POST /api/bus-stops`, `PATCH /api/bus-stops/{id}`, `DELETE /api/bus-stops/{id}` — all fully role-gated and audited. Delete rejects with a friendly 409 when the stop still has students assigned.
- **Student Detail Bus Card**: `/students/:id` now shows a dedicated Bus Pickup card next to the Fee Structure card — stop number, name and monthly fare, or a "Not on the school bus" hint. `GET /students/{sid}/ledger` now denormalises the current `monthly_fee` from the bus-stops master so the card always reflects the latest fare, even if the school updated it.
- **Receipt Print refresh**: `ReceiptView.js` now renders a "BUS STOP" row inside the DETAILS block whenever the student is on a route (shows `#no · stop_name`). Also added a Stream row for JC students. Falls back to the receipt's rich student_snapshot so old receipts keep working.
- **Fee Structure Preview → Publish**: added a Preview button next to Save that opens a modal showing the class + department, the three key totals (Admission, Continuation, Grand Total) and every line item. "Publish Structure →" is the only way to save from the preview, giving admins a last look before overwriting the previous year's numbers.
- **Verified**: bus-stops CRUD roundtrip (create → patch fee to ₹1,450 + deactivate → delete). Playwright confirms the /bus-stops page renders with all 61 stops, the "New Stop" modal opens on click, Edit buttons render on every row. 47/47 pytest still passing. Distribution ZIP rebuilt.


- **Bus Stop master list**: seeded 61 stops from the school's `BUS Fees stucture 2016-17 to ...` PDF into a new `bus_stops` MongoDB collection. Each row has `stop_no`, `stop_name` (transliterated to English so receipts stay ASCII-safe), `monthly_fee`, `academic_year`, `active`. Fees range ₹850 (Butibori main-town stops) to ₹1,400 (Asola Sawangi / Chimnajhari).
- **New endpoints**:
  - `GET /api/bus-stops` — master list, sorted by stop number
  - `POST /api/bus-stops/seed-2026?replace=true` — admin-only re-seed from `/app/memory/bus_stops_2026.json`
- **Student model** gains `bus_stop_no` (int) + `bus_stop_name` (denormalised for receipts). Bulk-import validates the stop number against the master and auto-fills the name.
- **Receipt snapshot** now carries `bus_stop_no` + `bus_stop_name` so the printed receipt can display the pickup stop next to Medium / Class / Stream.
- **Excel Template with real data-validation dropdowns**: installed `exceljs` and rewrote the Students template writer to produce a real `.xlsx` with:
  - A hidden `Lookups` sheet holding the 3 media, 5 streams, yes/no, and all 61 bus stops.
  - Named ranges (`MediaList`, `StreamList`, `FYList`, `BusStopList`).
  - Cell-level `dataValidation` bound to rows 2 → 5000 for the Medium, Stream, first_year_in_college and bus_stop_no columns — so Excel shows real dropdown arrows and rejects free-text with a friendly error title.
  - Header row styled (bold, blue background, frozen), and cell-comments explain "MANDATORY" / "leave blank if not on bus".
- **Verified end-to-end**:
  - Bus stops seeded (61 rows), API returns full list.
  - Bulk-import a student with `bus_stop_no: 27` → snapshot correctly stored as `Mohgaon`.
  - 47/47 pytest passing.
- Distribution ZIP rebuilt.


- **Rewrote** `fee_structure_2026.json` (41 rows) with the exact numbers from the school's 2026-27 PDF, using a new schema:
  - `medium` (English Medium / Semi Medium (Marathi) / Junior College), `class_name`, `stream`
  - `admission_fee`, `continuation_fee`, `term_fee`, `practical_fee`, `tuition_total`, `tuition_installments[]` (with due dates: 2026-08-01, 2026-10-01, 2027-01-01)
  - `applies_to`: "all" | "new_only" | "returning_only" — enables JC 12th to auto-pick the right variant for direct-admission vs continuing students.
- **New helpers in `core.py`**:
  - `MEDIUM_ALIASES` + `canonical_medium()` — case-insensitive matcher (English/Eng/EM → "English Medium", Semi/SM/Marathi → "Semi Medium (Marathi)", JC/College → "Junior College")
  - `canonical_stream()` — Arts/Commerce/Science/Electronics/Fisheries with common typo tolerance
  - `normalize_class_name()` — 5th → Class 5, KG I → K.G. I, etc.
  - `resolve_fee_structure(medium, class_name, stream, first_year_in_college, academic_year)` — the deterministic mapping used by both import and future admission flows.
- **Rewrote** `POST /fee-structures/seed-2026?replace=true` to consume the new schema and stamp every structure with `medium`, `class_name`, `stream`, `admission_fee`, `continuation_fee`, `tuition_installments`, `applies_to`, `active` on top of the existing `items[]`/`total` fields. New helper endpoint `GET /fee-structures/resolve` for other callers.
- **Rewrote** `POST /students/bulk-import`:
  - **Medium is mandatory**; JC rows require Stream; non-JC rows can't carry Stream.
  - Rejects Class 5 English tagged as Semi (medium/class alignment check).
  - Rejects Class 11/12 tagged as English/Semi (JC only).
  - Rejects unknown medium/class values with plain-English messages.
  - Auto-picks department (EP / SEC / MP / JC), auto-creates the class row if missing (respecting medium+stream), auto-resolves the fee structure (honouring `first_year_in_college` for the JC 12th "new admission" variant), and stores `fee_structure_id`, `medium`, `stream`, `section`, `roll_no`, `father_name`, `mother_name`, `first_year_in_college` on the student.
- **Excel template refreshed** (frontend `ImportExcel.js`): required = admission_no · name · medium · class_name; optional = stream · section · roll_no · father_name · mother_name · guardian_mobile · academic_year · first_year_in_college · address. 4 example rows cover English Medium, Semi Medium (Marathi), JC Class 11 (Science, first_year=yes), JC Class 12 (Commerce, first_year=no).
- **Receipt rules enforced** (`POST /receipts`):
  - **Admission Fee is one-time only** per student per academic year — a second receipt with a line named "Admission Fee" returns `409` with `"Admission Fee for {student} was already collected on receipt {number} — it cannot be charged again."`
  - **Continuation Fee must be paid in full** — if the amount doesn't match `fee_structure.continuation_fee`, returns `400 "Continuation Fee must be paid in full (₹X). Partial payments are not allowed."`
  - **Rich student snapshot** now stamped on every receipt (admission_no, name, father/mother names, mobile, class name, section, roll_no, medium, stream, academic year, resolved fee-structure name) so receipts self-describe forever, even if the student record is edited later.
- **Fee Structure UI**: existing structures list now shows Medium · Class · Stream with badges for `NEW ADMISSION` (amber) and `RETURNING` (blue), plus a breakdown of Admission / Continuation / Tuition amounts per row. Seed button switched to `replace=true`.
- **Verified end-to-end**:
  - Seed loaded 41 structures cleanly.
  - Resolver returns correct row for English/Class 5 (adm 9000, cont 5000, tuition 9000), JC/Class 12/Arts/new (adm 1000, tuition 2000), JC/Class 12/Arts/returning (adm 0, tuition 1500).
  - Bulk import of 5 mixed rows: 3 accepted, 2 rejected with the exact right error messages (Class 11 English → blocked, JC without stream → blocked). Case-insensitive medium fuzzy match confirmed ("Semi" → canonical), class-name normalisation confirmed ("5th Std" → "Class 5").
  - Admission Fee receipt succeeded first time, blocked with a clear message on the second attempt.
  - 47/47 pytest passing.
- Distribution ZIP rebuilt at 9.7 MB.


- **Scheduled 8 AM Diagnostics**: `routers/diagnostics.py` now exposes `daily_diagnostics_scheduler()` — an asyncio task launched from `server.py`'s startup event. It records an initial snapshot on boot, then sleeps until 08:00 server-local every day and takes another snapshot (`source="scheduler"`), retaining the most-recent 60 snapshots in a new `diagnostic_reports` collection. No new dependency (uses stdlib asyncio + datetime).
- **New endpoints**:
  - `GET /api/diagnostics/latest` — returns the most recent snapshot (used by the dashboard banner)
  - `POST /api/diagnostics/run-now` — admin/manager can trigger a snapshot immediately
  - `GET /api/onboarding/status` — `{first_run, completed_at, dismissed_at}` driven by `settings.onboarded_at` / `settings.onboarding_dismissed_at`
  - `POST /api/onboarding/complete` and `POST /api/onboarding/skip`
- **Dashboard banner**: If the latest snapshot is < 30 hours old AND `overall_ok === false`, a rose-red banner appears at the top with the list of failing checks and an "Open Diagnostics →" button (`data-testid="overnight-diag-banner"`).
- **First-Run Onboarding**: `OnboardingPopover.jsx` — modal shown only when `user.role === 'administrator'` AND `settings.onboarded_at` is null AND localStorage hasn't marked it seen. Beautiful gradient header, 5-step preview, "Take me to Setup Wizard" (calls `/api/onboarding/complete` then navigates to `/setup-wizard`) or "I'll do this later" (calls `/api/onboarding/skip`). Persists per-install via the settings collection so it doesn't reappear on any other browser.
- **Verified**: 47/47 pytest passing; endpoint responses OK; Playwright confirms popover appears on first admin login, dismisses on Skip, and does NOT reappear after page reload. Distribution ZIP rebuilt (8.1 MB).


- **Auto Notify on Fail**: `Layout.js` now polls `GET /api/diagnostics` on mount and every 5 minutes; whenever ≥1 server-side check fails, a pulsing red badge with the failure count appears on the "System Diagnostics" sidebar row (`data-testid="nav-diagnostics-badge"`). If the endpoint itself is unreachable, the badge still lights up (Main Server issue). No polling in the login screen.
- **Auto Backup Rotation**: `core.py` now defines `BACKUP_RETENTION = 30` and a new `_rotate_backups()` coroutine that runs immediately after every successful `_create_backup_zip(...)`. Backups beyond the newest 30 are dropped from both the `backups` collection and the disk. Rotated filenames are returned in the manifest (`rotated_out`) and logged in the audit trail.
- **Verified**:
  - Rotation seeded 35 total backups → after rotation exactly 30 remain (`PASS: rotation enforces BACKUP_RETENTION=30`).
  - 47/47 pytest passing on the new code.
  - Playwright confirms the nav item still reads "System Diagnostics" and the badge stays hidden while every check is green.
- Distribution ZIP rebuilt at 6.4 MB.


- **Added** `GET /api/diagnostics` in a new `routers/diagnostics.py` (63 lines) — runs six server-side checks and returns a structured report:
  1. Database connection (Mongo ping + latency)
  2. Database version (MongoDB build info + schema version + collection count)
  3. Software version (app + build date)
  4. Backup folder access (writability probe + latest backup)
  5. Storage space (disk_usage with < 2 GB warning)
  6. Seed data (users/students/receipts/receipt-types counts)
- **Added** `/diagnostics` page (`pages/Diagnostics.js`) — client runs five additional probes in the browser and merges results:
  1. Main Server connection (latency to `/api/version`)
  2. LAN connectivity (`navigator.onLine` + network type)
  3. Printer availability (window.print API + Test Print button)
  4. Scanner / Camera availability (`enumerateDevices` — for kiosk QR scanning)
  5. Browser compatibility (Chrome/Edge recommended)
- **UI**: green/amber/red overall banner, split into "This PC (browser)" and "Main Server" cards, every row shows plain-English message ("Cannot connect to Main Server", "No camera detected", "Backup folder not writable", etc.), Test Print + Re-run All Checks buttons, printable for support hand-off.
- **Nav**: "System Diagnostics" (Stethoscope icon) added between Settings and Administration; visible to every role so any staff member can run the check.
- **Registered** in `server.py` router list; distribution ZIP rebuilt (4.8 MB) with the new files and re-published at `/downloads/BalajiConventFeeSoftware-v1.0.zip`.
- **Verified**: endpoint returns overall_ok=true with 6/6 server checks passing; frontend Playwright smoke test confirms all 7 rows render and the green banner shows.


- **Refactored** `server.py` from a 2095-line monolith into a **49-line bootstrap** + `core.py` (595 lines: DB, models, deps, PIN gates, numbering, seed, quarterly reminders) + 6 domain routers under `/app/backend/routers/`:
  - `auth.py` (157 lines) — auth/login/logout/me, PIN endpoints, users CRUD, settings, /api/version
  - `catalog.py` (289 lines) — departments, classes, fee heads, fee structures + bulk import/delete, promotion, rollover, seed-2026, imports history
  - `students.py` (163 lines) — students CRUD, ledger, siblings, bulk import/delete/reassign
  - `receipts.py` (327 lines) — receipt-types CRUD + sequence reset + reseed, receipts CRUD + cancel/reprint, adjustments, extensions, reminders
  - `reports.py` (432 lines) — dashboard, all reports, bus routes, outstanding notices, quarterly cron, public kiosk lookups
  - `config_io.py` (108 lines) — config export/import, database backups (PIN-gated / dual-auth)
- All endpoints still under the `/api` prefix. **Zero client changes required.**
- **Verified**: 47/47 pytest passing on the new structure, 14/14 authenticated endpoints returning 200 on the smoke sweep.
- **Fresh Install Verification** — since running Windows here isn't possible, we did the strongest equivalent:
  - Rebuilt the distribution ZIP with the new `core.py` + `routers/` tree, `.env.example` files restored for both backend and frontend, and no build artefacts leaked (no `.venv`, `node_modules`, `build`, `__pycache__`).
  - **Verified pip install parity**: fresh Linux venv → `pip install -r requirements.txt` clean → `from server import app` reports 88 routes registered.
  - **Verified yarn build parity**: `yarn build` on the current source completes clean and produces `build/index.html`.
  - **Hardened `install-main-server.bat`**: auto-generates a 64-char JWT_SECRET via PowerShell instead of leaving the placeholder; explicit error trap on `pip install` and `yarn build`; calls a new `preflight.bat` at the end.
  - **Added `01-install-main-server/preflight.bat`**: checks .venv present, backend `.env` present, `frontend/build/index.html` exists, MongoDB Windows service registered, and `from server import app` succeeds — printing a clear PASS / FAIL summary. Can be re-run any time.
  - New ZIP published at `/downloads/BalajiConventFeeSoftware-v1.0.zip` (3.2 MB, 186 files) — verified downloadable end-to-end from the preview URL.

## Publish Status
- **Backend**: 100% — 47 pytest passing on the split codebase, 88 routes registered.
- **Frontend**: 100% — `yarn build` clean, all authenticated routes render.
- **Offline LAN**: verified — no CDN dependencies.
- **Distribution ZIP**: v1.0 fresh build, includes preflight self-check + auto JWT generation.

