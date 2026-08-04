# Running Balaji Convent Fee Software on Your School PC (Offline LAN)

This guide gets the app running on your **Main Server PC** at school, so client PCs on the LAN can use it in a browser — no internet needed.

---

## 1. Machines you need

| Machine | Purpose | Minimum spec |
|---|---|---|
| **Main Server PC** | Runs MongoDB + backend + serves frontend | Windows 10/11 or Ubuntu 22.04, 16 GB RAM, SSD, wired LAN, UPS |
| **Client PCs** (cashier counters, accountant desk, principal) | Just open Chrome/Edge | Anything with a modern browser + wired LAN |
| **Gigabit LAN switch** | Connects them all | Any managed/unmanaged Gigabit switch |

Give the Main Server PC a **static IP** on your school LAN, e.g. `192.168.1.10`.

---

## 2. One-time install on the Main Server PC

### A. Install prerequisites (do this once)
- **Python 3.11+**  → https://www.python.org/downloads/ (tick "Add to PATH")
- **Node.js 20+ LTS + Yarn**  → https://nodejs.org/en/download , then `npm install -g yarn`
- **MongoDB Community 7.x**  → https://www.mongodb.com/try/download/community (install as a Windows service, default port 27017)
- **Git** (optional, for updates)  → https://git-scm.com/downloads

### B. Get the code
Download this project from Emergent (top-right "Save to GitHub" or "Download Zip"). Extract to `C:\balaji-fee\` (Windows) or `/opt/balaji-fee/` (Ubuntu).

### C. Backend setup (one time)
Open a terminal in the project folder:
```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux:    source .venv/bin/activate
pip install -r requirements.txt
```

Edit `backend/.env`:
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="balaji_fee_db"
CORS_ORIGINS="http://192.168.1.10,http://192.168.1.10:3000"
JWT_SECRET="<paste 64 random hex chars — same value forever, keep secret>"
ADMIN_EMAIL="neulkarprathamesh@gmail.com"
ADMIN_PASSWORD="Balaji@2026"
ADMIN_NAME="Prathamesh Neulkar"
```
Replace `192.168.1.10` with your server's actual LAN IP.

### D. Frontend setup (one time)
```bash
cd ../frontend
yarn install
```
Create `frontend/.env`:
```env
REACT_APP_BACKEND_URL=http://192.168.1.10:8001
WDS_SOCKET_PORT=0
```
Then build the static bundle:
```bash
yarn build
```
The `build/` folder now contains the whole frontend as static files.

---

## 3. Run the services (every school day)

### Backend
From `backend/` with the venv activated:
```bash
uvicorn server:app --host 0.0.0.0 --port 8001
```
Leave this terminal open (or install it as a Windows service using **NSSM** so it auto-starts on boot).

### Frontend
Simplest option — serve the static build with any small web server:
```bash
cd frontend
npx serve -s build -l 3000
```
Or install **nginx** and point its root to `frontend/build`.

---

## 4. Access from client PCs

On any client PC on the school LAN, open Chrome/Edge:
```
http://192.168.1.10:3000
```
Log in with `neulkarprathamesh@gmail.com` / `Balaji@2026`. That's it — cashiers can start issuing receipts.

**Tip**: Pin the URL as a bookmark or install as a PWA (Chrome → "Install App").

---

## 5. Backups (very important)

Run daily via Task Scheduler (Windows) or cron (Linux):
```bash
mongodump --db=balaji_fee_db --out="D:\backups\balaji-%DATE%"
```
Rotate the backup drive weekly. Test a restore quarterly.

---

## 6. Common issues

| Symptom | Fix |
|---|---|
| Client says "Cannot reach server" | Server firewall is blocking port 8001/3000 → open both in Windows Firewall |
| Login fails with 401 | Password in `.env` changed but backend not restarted → restart uvicorn |
| Receipts renumber from 1 | Wrong `DB_NAME` in `.env` → check it matches |
| Slow after a year | Run `mongo` shell: `db.receipts.createIndex({created_at: -1})` |

---

## 7. Updating the software

When you get a new version from Emergent:
1. Stop the backend + frontend.
2. Overwrite the folder (keep your `.env` files).
3. Rerun `pip install -r requirements.txt` and `yarn install && yarn build`.
4. Start services again — MongoDB data is untouched.

---

## Need help?
Reach out on Emergent chat. The full source is yours — you can hire any Python/React freelancer to modify it later.
