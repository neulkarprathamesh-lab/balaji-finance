# Balaji Convent Fee Software — Self‑Host on School LAN

> **Golden rule** — the software may be online, but the **master database lives on your school's Main PC**. Every student, receipt, ledger and audit entry stays inside your school building. Other computers connect to the Main PC over your school LAN. The internet is used only for optional extras (SMS, email, off‑site backup, updates). If the internet goes down mid‑day, cashiers continue collecting fees without noticing.

---

## 1. Network topology

```
                        ┌────────────────────────────────────────┐
                        │        SCHOOL MAIN PC (server)         │
                        │   Static IP: 192.168.1.10              │
                        │                                        │
                        │   ┌────────────────────────────────┐   │
                        │   │  MongoDB  (bind: 0.0.0.0)      │   │
                        │   │  balaji_fee_db  ← THE DATABASE │   │
                        │   └────────────────────────────────┘   │
                        │   ┌────────────────────────────────┐   │
                        │   │  Backend (FastAPI / uvicorn)   │   │
                        │   │  0.0.0.0:8001                  │   │
                        │   └────────────────────────────────┘   │
                        │   ┌────────────────────────────────┐   │
                        │   │  Frontend (nginx static)       │   │
                        │   │  0.0.0.0:3000  (or :80)        │   │
                        │   └────────────────────────────────┘   │
                        │   ┌────────────────────────────────┐   │
                        │   │  Backups → external USB drive  │   │
                        │   └────────────────────────────────┘   │
                        └────────────┬───────────────────────────┘
                                     │  Gigabit LAN switch
             ┌───────────────────────┼────────────────────────┐
             │                       │                        │
   Cashier Counter 1        Cashier Counter 2         Accountant / Principal
   (browser only)           (browser only)            (browser only)
   http://192.168.1.10:3000                            http://192.168.1.10:3000
```

**What must NOT go over the internet during daily work:** logins, receipts, ledgers, adjustments, extensions, reminders, kiosk lookups, day‑end reports. All of it stays inside your building.

---

## 2. Hardware you need

| Machine | Purpose | Recommended |
|---|---|---|
| **Main PC (server)** | Runs MongoDB + backend + serves the frontend | Windows 10/11 or Ubuntu 22.04, 16 GB RAM, 500 GB SSD, wired LAN, UPS |
| **Client PCs** (cashier, accountant, principal) | Just open Chrome or Edge | Any modern PC on the same LAN |
| **Gigabit switch + wired cables** | Reliable LAN | Any managed / unmanaged Gigabit switch. Wi‑Fi works but wired is safer for cashiers. |
| **External USB drive** | Daily backup rotation | 2× 500 GB drives (rotate weekly) |
| **UPS** | Prevents data corruption if power blinks | 1 kVA line‑interactive is enough |

Give the Main PC a **static LAN IP**. Example throughout this guide: `192.168.1.10`. Replace with your actual IP.

---

## 3. One‑time install on the Main PC

### 3.1 Install prerequisites

- **Python 3.11+** — https://www.python.org/downloads/ (tick "Add to PATH")
- **Node.js 20 LTS + Yarn** — https://nodejs.org/en/download , then `npm install -g yarn`
- **MongoDB Community 7.x** — https://www.mongodb.com/try/download/community (install as a service)
- **nginx** (optional, for serving the frontend) — Windows build at http://nginx.org/en/download.html, or `sudo apt install nginx` on Ubuntu

### 3.2 Give the Main PC a static IP

- **Windows** → Control Panel → Network → Change adapter settings → Ethernet Properties → IPv4 → set `192.168.1.10 / 255.255.255.0`, Gateway `192.168.1.1`
- **Ubuntu** → edit `/etc/netplan/*.yaml`, set the static address, run `sudo netplan apply`

Verify from another LAN PC: `ping 192.168.1.10`.

### 3.3 Bind MongoDB to the LAN (so client PCs can *reach* it, but only from LAN)

By default MongoDB listens only on `127.0.0.1`. Because backend + Mongo both sit on the **same Main PC** we do **not** need to open Mongo to the LAN — the backend talks to Mongo over `localhost` and the LAN only talks to the backend on port 8001. Keep the default: `bindIp: 127.0.0.1`.

> If a second PC ever needs direct MongoDB access (e.g. reporting workstation running Mongo Compass), set `bindIp: 127.0.0.1,192.168.1.10` in `mongod.cfg` and enable Windows auth. Do **not** bind to `0.0.0.0`.

### 3.4 Open the school firewall

Open only the ports the LAN needs:

- **Windows Firewall** → Advanced Settings → Inbound Rules → New Rule → Port → TCP → **8001, 3000** → Allow → apply to *Domain, Private* (not Public).
- **Ubuntu (ufw)**: `sudo ufw allow from 192.168.0.0/16 to any port 8001 && sudo ufw allow from 192.168.0.0/16 to any port 3000`

Do **not** open these ports to the internet router / public interface.

### 3.5 Get the code

Download from Emergent (top‑right → "Save to GitHub" or "Download Zip"). Extract to `C:\balaji-fee\` (Windows) or `/opt/balaji-fee/` (Ubuntu).

### 3.6 Backend setup

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux:    source .venv/bin/activate
pip install -r requirements.txt
```

Create / edit `backend/.env`:
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="balaji_fee_db"
CORS_ORIGINS="http://192.168.1.10,http://192.168.1.10:3000,http://192.168.1.10:80"
JWT_SECRET="<paste 64 random hex chars — keep secret, never change>"
ADMIN_EMAIL="neulkarprathamesh@gmail.com"
ADMIN_PASSWORD="Balaji@2026"
ADMIN_NAME="Prathamesh Neulkar"
```

Change `192.168.1.10` to your Main PC's actual LAN IP.

### 3.7 Frontend build

Create `frontend/.env`:
```env
REACT_APP_BACKEND_URL=http://192.168.1.10:8001
WDS_SOCKET_PORT=0
```

Then:
```bash
cd frontend
yarn install
yarn build
```

The `frontend/build/` folder now contains the whole app as static files. **All logos and images are bundled locally** (`school-logo.jpeg`, `login-bg.png`) — no CDN is needed during daily use.

---

## 4. Run the services every school day

### 4.1 Backend (as a Windows service so it auto‑starts on boot)

Install NSSM once (https://nssm.cc/download), then:
```cmd
nssm install BalajiFeeBackend
```
- Application → `C:\balaji-fee\backend\.venv\Scripts\python.exe`
- Arguments → `-m uvicorn server:app --host 0.0.0.0 --port 8001`
- Startup directory → `C:\balaji-fee\backend`
- I/O redirect Stdout → `C:\balaji-fee\logs\backend.log`
- Startup type → Automatic

On Ubuntu, use `systemd` — a sample unit file is in `deploy/balaji-backend.service` (or copy the pattern from any FastAPI systemd tutorial).

### 4.2 Frontend (nginx serves the built folder)

Windows `nginx.conf` snippet:
```nginx
server {
  listen 3000;
  server_name  _;
  root  C:/balaji-fee/frontend/build;
  index index.html;
  location / {
    try_files $uri $uri/ /index.html;
  }
}
```
Set nginx to **Automatic** in Services (Windows) so it starts on boot.

### 4.3 Verify from any client PC on the LAN

```
http://192.168.1.10:3000
```
You should see the login screen. Log in with the admin credentials. Cashiers can start collecting fees immediately.

**Tip** — on each client PC, install the URL as a PWA (Chrome → ⋮ → *Install app*). Cashiers then get a one‑click desktop icon.

---

## 5. Backups (do this before anything else fails)

### 5.1 Daily automatic dump

**Windows (Task Scheduler, runs every night at 20:00):**
```cmd
"C:\Program Files\MongoDB\Server\7.0\bin\mongodump.exe" --db=balaji_fee_db --out="D:\backups\balaji-%date:~10,4%-%date:~4,2%-%date:~7,2%"
```

**Ubuntu (cron @ 20:00):**
```cron
0 20 * * *  mongodump --db=balaji_fee_db --out=/mnt/backups/balaji-$(date +\%Y-\%m-\%d)
```

### 5.2 Weekly rotation

Keep **two** external USB drives. Rotate them Monday morning — one plugged into the Main PC, the other at the principal's cupboard. Test a full restore once a quarter:

```bash
mongorestore --drop --db=balaji_fee_db D:\backups\balaji-2026-08-01\balaji_fee_db
```

### 5.3 Off‑site backup (optional, requires internet)

Once a week, copy the latest dump folder to Google Drive / OneDrive / an SFTP server. This is the **only** time the software needs the internet in the entire monthly cycle. If it fails, daily work is untouched.

---

## 6. What runs over the internet (all optional)

| Feature | Internet required? | If internet fails |
|---|---|---|
| Login, receipts, ledgers, kiosk lookup, day‑end | **No** | Fully working |
| SMS reminders (Twilio / MSG91) | Optional | Reminders queue up locally; sent when internet returns |
| Email fee notices | Optional | Notices queue up; sent when internet returns |
| Off‑site backup upload | Optional | Skipped that day |
| Software updates | Optional | You can wait days/weeks |

The app never *requires* an internet connection to issue a receipt or run day‑end.

---

## 7. Security hardening (10 minutes)

- Change the default admin password after first login (top‑right → My Profile → Change Password).
- Set `JWT_SECRET` in `backend/.env` to a random 64‑char hex string and never share it.
- Keep MongoDB on `bindIp: 127.0.0.1` (already default).
- Don't open port 8001 or 27017 on the internet‑facing router.
- Enable Windows / Ubuntu login passwords on the Main PC itself.
- Give each cashier their own login in **Administration → Users** — never share the admin account.

---

## 8. Common issues

| Symptom | Fix |
|---|---|
| Client PC says "Cannot reach server" | Windows Firewall is blocking → open ports 8001 and 3000 for the Private/Domain profiles |
| Login works from Main PC but not from cashier PC | `CORS_ORIGINS` in `backend/.env` is missing the LAN IP → add and restart backend |
| Logo shows a broken image | Old build served without `school-logo.jpeg` in `public/` → rebuild with `yarn build` |
| Fonts look plain (system font) | Google Fonts didn't load because internet is offline → cosmetic only; the app still works |
| Receipts renumber from 1 | Wrong `DB_NAME` in `.env` → check it matches |
| Slow after a year of data | On the Main PC run: `mongo balaji_fee_db --eval "db.receipts.createIndex({created_at:-1})"` |
| Fixed the .env but nothing changed | Restart the backend service (NSSM: Services → BalajiFeeBackend → Restart) |

---

## 9. Updating the software

1. Stop the backend service (Services → BalajiFeeBackend → Stop).
2. Overwrite the folder — **do not delete** your `.env` files or `mongod` data.
3. Rerun `pip install -r requirements.txt` and `yarn install && yarn build`.
4. Start the service again. MongoDB data is untouched.

---

## 10. Need help?

Reach out on Emergent chat. The full source is yours — you (or any Python/React freelancer) can modify it later.
