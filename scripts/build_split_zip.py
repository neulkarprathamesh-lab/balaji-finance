#!/usr/bin/env python3
"""Split the FINAL delivery into three downloadable pieces:

    1) BalajiConventFeeSoftware_v1.0_CORE.zip     (small — code, installers, wheels, docs)
    2) mongodb-windows-x86_64.msi.001              (~ 300 MB — first half of MongoDB MSI)
    3) mongodb-windows-x86_64.msi.002              (~ remainder of MongoDB MSI)

The Main Server installer will detect the .001/.002 parts and recombine them into
the original MSI via Windows `copy /b` before running the silent install.
"""
from __future__ import annotations
import hashlib, os, shutil, sys, zipfile
from datetime import datetime
from pathlib import Path

APP        = Path("/app")
DIST_ROOT  = APP / "dist" / "BalajiConventFeeSoftware-v1.0"
OUT_DIR    = APP / "dist"
DL_DIR     = APP / "frontend" / "public" / "downloads"
MSI_SRC    = DIST_ROOT / "05-services" / "mongodb-windows-x86_64.msi"
SPLIT_SIZE = 300 * 1024 * 1024   # 300 MB

CORE_ZIP   = OUT_DIR / "BalajiConventFeeSoftware_v1.0_CORE.zip"
MSI_P1     = OUT_DIR / "mongodb-windows-x86_64.msi.001"
MSI_P2     = OUT_DIR / "mongodb-windows-x86_64.msi.002"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""): h.update(c)
    return h.hexdigest()


def build_core_zip() -> int:
    """Everything in the delivery tree EXCEPT the MongoDB MSI."""
    if CORE_ZIP.exists(): CORE_ZIP.unlink()
    n = 0
    with zipfile.ZipFile(CORE_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in DIST_ROOT.rglob("*"):
            if not p.is_file(): continue
            rel = p.relative_to(DIST_ROOT)
            if rel.name == "mongodb-windows-x86_64.msi":
                continue     # split out separately
            zf.write(p, rel.as_posix()); n += 1
        # A README pointing at the two MSI parts
        zf.writestr("05-services/README-mongodb-parts.txt",
                    "The MongoDB installer is delivered separately as two parts:\n"
                    "  mongodb-windows-x86_64.msi.001\n"
                    "  mongodb-windows-x86_64.msi.002\n"
                    "Download BOTH and place them in this folder (05-services/).\n"
                    "install-main-server.bat will detect them and recombine them automatically.\n")
    return n


def split_msi() -> tuple[int, int]:
    """Split MongoDB MSI into two chunks ~300 MB and remainder."""
    if not MSI_SRC.exists():
        print(f"ERROR: {MSI_SRC} missing.", file=sys.stderr); sys.exit(2)
    for p in (MSI_P1, MSI_P2):
        if p.exists(): p.unlink()
    with open(MSI_SRC, "rb") as src, open(MSI_P1, "wb") as p1:
        remaining = SPLIT_SIZE
        while remaining > 0:
            chunk = src.read(min(1024 * 1024, remaining))
            if not chunk: break
            p1.write(chunk); remaining -= len(chunk)
        with open(MSI_P2, "wb") as p2:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk: break
                p2.write(chunk)
    return MSI_P1.stat().st_size, MSI_P2.stat().st_size


def publish() -> dict:
    DL_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for f in (CORE_ZIP, MSI_P1, MSI_P2):
        dst = DL_DIR / f.name
        shutil.copy2(f, dst)
        h = sha(f)
        manifest[f.name] = {"size_bytes": f.stat().st_size, "sha256": h}
    (DL_DIR / "SHA256SUM.txt").write_text("\n".join(
        f"{v['sha256']}  {k}" for k, v in manifest.items()
    ) + "\n")
    (DL_DIR / "SPLIT_MANIFEST.json").write_text(
        __import__("json").dumps({
            "version": "1.0.0",
            "built_at": datetime.utcnow().isoformat() + "Z",
            "parts": manifest,
            "reassembly_note": (
                "Windows: place the two .001/.002 files in 05-services/ next to the CORE zip's "
                "installers.  install-main-server.bat will run:  copy /b .msi.001 + .msi.002 "
                "mongodb-windows-x86_64.msi  and then run the MSI silently."
            ),
        }, indent=2)
    )
    return manifest


def main() -> int:
    print("Splitting Balaji FeeHub v1.0 delivery into 3 pieces …")
    n = build_core_zip()
    print(f"  ok   core zip                       ·  {CORE_ZIP.stat().st_size/1024/1024:.2f} MB  ·  {n} files")
    p1, p2 = split_msi()
    print(f"  ok   mongodb-windows-x86_64.msi.001 ·  {p1/1024/1024:.2f} MB")
    print(f"  ok   mongodb-windows-x86_64.msi.002 ·  {p2/1024/1024:.2f} MB")
    manifest = publish()
    print("\nPublished under /downloads/ :")
    for k, v in manifest.items():
        print(f"  {k:52s}  {v['size_bytes']/1024/1024:>8.2f} MB   SHA-256 {v['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
