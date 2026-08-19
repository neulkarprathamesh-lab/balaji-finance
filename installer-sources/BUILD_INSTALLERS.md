# Compiling Balaji FeeHub Windows Installers (.exe)

This folder contains two Inno Setup source files that compile into the two Windows `.exe` installers your school needs:

* **BalajiFeeHub-Server-Setup.exe** — Main Server installer (single EXE that installs MongoDB, backend, frontend and all Windows services).
* **BalajiFeeHub-Client-Setup.exe** — Client PC installer (small EXE that auto-discovers the Main Server and creates shortcuts).

Everything the compiled `.exe` needs is already in `../dist/BalajiConventFeeSoftware-v1.0/` — the `.iss` files reference that folder as their payload.

---

## Option A — Compile on any Windows PC (recommended, 5 minutes)

1. Download Inno Setup 6 (free, ~6 MB): <https://jrsoftware.org/isdl.php>
2. Install it with the default options.
3. Copy this whole `installer-sources/` folder AND the `dist/BalajiConventFeeSoftware-v1.0/` folder to the Windows PC. Keep them side-by-side, exactly as they are in this project.
4. Open PowerShell **as Administrator** in the `installer-sources/` folder and run:

   ```powershell
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" BalajiFeeHub-Server-Setup.iss
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" BalajiFeeHub-Client-Setup.iss
   ```
5. The two `.exe` files appear under `Output/`:
   * `Output\BalajiFeeHub-Server-Setup.exe`  (~600 MB — everything bundled)
   * `Output\BalajiFeeHub-Client-Setup.exe`  (~150 KB)
6. Compute the SHA-256 checksums:
   ```powershell
   Get-FileHash Output\BalajiFeeHub-Server-Setup.exe -Algorithm SHA256
   Get-FileHash Output\BalajiFeeHub-Client-Setup.exe -Algorithm SHA256
   ```

That is the entire process. From now on the school gets two `.exe` files — nothing else.

---

## Option B — Compile with GitHub Actions (no Windows PC needed)

If you push this repository to GitHub, add `.github/workflows/build-installers.yml`:

```yaml
name: Build Windows Installers
on: [push]
jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Inno Setup
        run: choco install innosetup -y
      - name: Compile Server installer
        run: '& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer-sources\BalajiFeeHub-Server-Setup.iss'
      - name: Compile Client installer
        run: '& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer-sources\BalajiFeeHub-Client-Setup.iss'
      - uses: actions/upload-artifact@v4
        with:
          name: installers
          path: installer-sources/Output/*.exe
```

GitHub's free Windows runner produces both `.exe` files automatically.

---

## What each `.iss` compiles into

### Server installer

* Bundles the entire `dist/BalajiConventFeeSoftware-v1.0/` folder (installers, backend, prebuilt frontend, wheels, NSSM, MongoDB MSI parts, docs).
* Runs `preflight.bat` — blocks if any BLOCKING check fails.
* Runs `install-main-server.bat` — 14 stages, silent MongoDB MSI install, offline pip install, service registration.
* Refuses to overwrite an existing database — prompts to confirm repair/update.
* Provides `Repair`, `Update`, `Uninstall` from Add/Remove Programs.
* Post-install health check + opens the browser on success.

### Client installer

* Bundles only `02-install-client-pc/*` (~150 KB total).
* Runs `install-client-pc.bat` — discovers the Main Server on the LAN, verifies HTTP 200 on `/api/version`, creates Desktop + Start Menu shortcuts.
* Manual-IP fallback if discovery fails.
* Provides `Uninstall` from Add/Remove Programs.

---

## Windows testing (still mandatory before daily school use)

Neither the Linux container nor any AI agent can substitute for a real Windows clean-install test. After you compile the two `.exe` files, please run them on:

1. A fresh Windows 10 Pro 64-bit VM (no Python, MongoDB, or Node preinstalled).
2. A fresh Windows 11 Pro 64-bit VM (same state).

Send back the preflight output if any BLOCK line appears; each blocker can be patched by editing the corresponding `.bat` file inside `dist/BalajiConventFeeSoftware-v1.0/01-install-main-server/` — no need to re-open Inno Setup unless you want to change the installer wizard itself.
