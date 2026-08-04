"""Load test — seeds ~3,000 students then hammers the hot endpoints from 8 concurrent workers
to simulate 2–5 cashiers + accountant + admin + client PCs on the LAN."""
import os, sys, time, json, random, statistics, threading, queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

API = os.environ["API"]
ADMIN_EMAIL = "neulkarprathamesh@gmail.com"
ADMIN_PWD   = "Balaji@2026"
CASHIER_EMAIL = "cashier@balajiconvent.in"
CASHIER_PWD   = "cashier123"

def login(email, pwd):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]

def seed_students(admin_token, target=3000, batch_size=200):
    print(f"[seed] target={target}, batch={batch_size}")
    existing = requests.get(f"{API}/api/students?limit=1", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15).json()
    # Rough size check via dashboard receipts count
    already = 0
    r = requests.get(f"{API}/api/students?q=LT-", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    if r.ok:
        already = len(r.json())
    print(f"[seed] existing LT- students: {already}")
    if already >= target:
        print("[seed] already at target"); return already
    to_create = target - already
    created_total = 0
    mediums = [
        ("English Medium", "Class 3", None),
        ("English Medium", "Class 5", None),
        ("Semi Medium (Marathi)", "Class 4", None),
        ("Semi Medium (Marathi)", "Class 8", None),
        ("Junior College", "Class 11", "Science"),
        ("Junior College", "Class 12", "Commerce"),
    ]
    for start in range(already, already + to_create, batch_size):
        rows = []
        for i in range(start, min(start + batch_size, already + to_create)):
            med, cls, stream = random.choice(mediums)
            rows.append({
                "admission_no": f"LT-{i:06d}",
                "name": f"LoadTest Student {i:04d}",
                "medium": med, "class_name": cls, "stream": stream,
                "father_name": f"Father {i}", "guardian_mobile": f"98{random.randint(10000000, 99999999)}",
                "bus_stop_no": random.choice([1, 12, 27, 40, 55]) if random.random() < 0.35 else None,
            })
        t0 = time.perf_counter()
        r = requests.post(f"{API}/api/students/bulk-import", json={"rows": rows},
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=120)
        elapsed = time.perf_counter() - t0
        if not r.ok:
            print(f"[seed] batch {start} FAIL: {r.status_code} {r.text[:200]}"); break
        d = r.json(); created_total += d.get("created", 0)
        print(f"[seed] batch {start:05d}: +{d.get('created')} in {elapsed:.1f}s (errors={len(d.get('errors',[]))})")
    print(f"[seed] created {created_total} students")
    return created_total

def scenario_dashboard(token):
    r = requests.get(f"{API}/api/dashboard", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    return r.status_code

def scenario_students_search(token):
    q = random.choice(["Load", "LT-", "0001", "0002", str(random.randint(0, 3000))])
    r = requests.get(f"{API}/api/students?q={q}&limit=25", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    return r.status_code

def scenario_receipt_types(token):
    r = requests.get(f"{API}/api/receipt-types", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    return r.status_code

def scenario_bus_stops(token):
    r = requests.get(f"{API}/api/bus-stops", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    return r.status_code

def scenario_fee_structures(token):
    r = requests.get(f"{API}/api/fee-structures", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    return r.status_code

def scenario_defaulters(token):
    r = requests.get(f"{API}/api/reports/defaulters?quarter=total", headers={"Authorization": f"Bearer {token}"}, timeout=25)
    return r.status_code

SCENARIOS = [
    ("dashboard", scenario_dashboard,      0.20),
    ("students-search", scenario_students_search, 0.30),
    ("receipt-types", scenario_receipt_types, 0.10),
    ("bus-stops", scenario_bus_stops,      0.10),
    ("fee-structures", scenario_fee_structures, 0.10),
    ("defaulters", scenario_defaulters,    0.20),
]

def load_test(admin_token, cashier_token, concurrency=8, duration_s=30):
    tokens = [admin_token, cashier_token]
    stop_at = time.time() + duration_s
    results = {n: [] for n, _, _ in SCENARIOS}
    errors = {n: 0 for n, _, _ in SCENARIOS}

    def worker():
        while time.time() < stop_at:
            r = random.random()
            acc = 0
            for name, fn, weight in SCENARIOS:
                acc += weight
                if r <= acc:
                    token = random.choice(tokens)
                    t0 = time.perf_counter()
                    try:
                        code = fn(token)
                        ms = (time.perf_counter() - t0) * 1000
                        if code == 200:
                            results[name].append(ms)
                        else:
                            errors[name] += 1
                    except Exception:
                        errors[name] += 1
                    break

    print(f"[load] concurrency={concurrency}, duration={duration_s}s starting…")
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(worker) for _ in range(concurrency)]
        for f in as_completed(futures):
            f.result()

    total_ok = sum(len(v) for v in results.values())
    total_err = sum(errors.values())
    rps = total_ok / duration_s
    print(f"\n[load] total OK={total_ok}  errors={total_err}  throughput≈{rps:.1f} req/s\n")
    summary = []
    for name, samples in results.items():
        if not samples: continue
        samples_sorted = sorted(samples)
        summary.append({
            "endpoint": name, "count": len(samples), "errors": errors[name],
            "p50_ms": round(statistics.median(samples), 1),
            "p95_ms": round(samples_sorted[int(len(samples)*0.95) - 1] if len(samples) > 1 else samples[0], 1),
            "max_ms": round(max(samples), 1),
            "avg_ms": round(statistics.mean(samples), 1),
        })
    for row in sorted(summary, key=lambda r: -r["p95_ms"]):
        print(f"  {row['endpoint']:<20} n={row['count']:>4}  p50={row['p50_ms']:>6}ms  p95={row['p95_ms']:>6}ms  max={row['max_ms']:>6}ms  errors={row['errors']}")
    return {"concurrency": concurrency, "duration_s": duration_s, "total_ok": total_ok,
            "total_err": total_err, "rps": round(rps, 1), "per_endpoint": summary}

if __name__ == "__main__":
    admin = login(ADMIN_EMAIL, ADMIN_PWD)
    cash  = login(CASHIER_EMAIL, CASHIER_PWD)
    if "--seed-only" in sys.argv:
        seed_students(admin, target=3000)
        sys.exit(0)
    if "--load-only" not in sys.argv:
        seed_students(admin, target=3000)
    r = load_test(admin, cash, concurrency=8, duration_s=30)
    with open("/tmp/load_test_result.json", "w") as f:
        json.dump(r, f, indent=2)
    print(f"\n[load] result written to /tmp/load_test_result.json")
