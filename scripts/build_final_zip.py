#!/usr/bin/env python3
"""Build the final Balaji FeeHub v1.0 delivery ZIP.

Produces `/app/dist/BalajiFeeHub-v1.0-FINAL.zip` with:
    - backend/          full FastAPI source (no __pycache__, no keys)
    - frontend/         full React source (no node_modules, no build cache)
    - scripts/          production_purge.py, build_bcupdate.py
    - installers/       .bat / .ps1 installers
    - docs/             README, LICENSE, RELEASE_NOTES
    - version.json
    - README.md         entry-point instructions

Run:
    python -m scripts.build_final_zip
"""
from __future__ import annotations
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

APP = Path("/app")
OUT = APP / "dist" / "BalajiFeeHub-v1.0-FINAL.zip"

EXCLUDE_DIRS = {
    "__pycache__", "node_modules", ".pytest_cache",
    "build", "dist", ".git", ".emergent",
    "backups", "updates", "keys",           # runtime + secrets
    "test_reports", "load",                 # dev-only
    ".cache", ".yarn", "coverage",
}
EXCLUDE_FILES = {
    ".DS_Store", "*.pyc", "*.log", "yarn-error.log",
    "update_private.pem",                   # NEVER ship the private key
}
INCLUDE_TOP = [
    "backend", "frontend/src", "frontend/public",
    "frontend/package.json", "frontend/postcss.config.js", "frontend/tailwind.config.js",
    "frontend/jsconfig.json", "frontend/craco.config.js",
    "scripts", "installers", "docs",
    "version.json",
]


def should_skip(p: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in p.parts):
        return True
    if p.name in EXCLUDE_FILES:
        return True
    if p.suffix in {".pyc", ".log"}:
        return True
    if p.name == "update_private.pem":
        return True
    return False


def add_tree(zf: zipfile.ZipFile, src: Path, arc_base: str) -> int:
    n = 0
    if src.is_file():
        if should_skip(src):
            return 0
        zf.write(src, arc_base)
        return 1
    for p in src.rglob("*"):
        if not p.is_file() or should_skip(p):
            continue
        arc = f"{arc_base}/{p.relative_to(src).as_posix()}"
        zf.write(p, arc)
        n += 1
    return n


def main() -> int:
    if not (APP / "version.json").exists():
        print("ERROR: /app/version.json is missing.", file=sys.stderr); return 2

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists(): OUT.unlink()

    print(f"Building {OUT.name} …")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        total = 0
        for top in INCLUDE_TOP:
            src = APP / top
            if not src.exists():
                print(f"  skip  {top}  (missing)")
                continue
            n = add_tree(zf, src, top)
            print(f"  ok    {top}  · {n} file(s)")
            total += n

        # README with build metadata
        readme = f"""# Balaji FeeHub v{(APP / 'version.json').read_text()}
Balaji Convent & Junior College · Butibori, Nagpur
Fee Management System

Built: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
Files: {total}

## Quick start (Main Server)
  1. Extract this ZIP to C:\\BalajiFeeHub
  2. Right-click installers/install-main-server.bat → Run as administrator
  3. Open Chrome → http://localhost:3000 → complete the Setup Wizard

## Quick start (Client PC)
  1. Copy installers/install-client-pc.bat to the client
  2. Right-click → Run as administrator (auto-discovers the Main Server)

## Documentation
  - docs/RELEASE_NOTES.md
  - docs/LICENSE_AND_OWNERSHIP.md
  - Installation Manual PDF — generate any time from Menu → Delivery Center → "Generate & Download Manual"

## Software Updates
  Menu → Software Updates → upload a .bcupdate file. See docs/RELEASE_NOTES.md for details.
"""
        zf.writestr("README.md", readme)
        total += 1
        print(f"  ok    README.md  · 1 file")

    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"\nDone → {OUT}  ({size_mb:.2f} MB, {total} files)")

    # Also expose from the running app for admin download
    dl_dir = APP / "frontend" / "public" / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT, dl_dir / OUT.name)
    print(f"Published → /downloads/{OUT.name}  (accessible via the running app)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
