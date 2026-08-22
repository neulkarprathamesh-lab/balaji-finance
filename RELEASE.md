# Releasing Balaji FeeHub

This project ships two paths to the school PCs:

1. **Full installer** (~700 MB) — the existing `BalajiFeeHub-Server-Setup.exe` / `BalajiFeeHub-Client-Setup.exe` produced by every GitHub Actions run. Use for new installs and recovery.
2. **Differential update** (~5–20 MB) — a signed `.bcupdate` package + JSON release manifest published to a GitHub Release. Existing installs discover this automatically and download only what changed.

## Cutting a normal release (differential)

```bash
# 1. Bump the single source of truth
echo "1.0.1" > VERSION
git add VERSION
git commit -m "Bump to 1.0.1"

# 2. Tag it (this is what triggers the release publish step)
git tag v1.0.1
git push origin main
git push origin v1.0.1
```

GitHub Actions will then:

1. Sync `VERSION` into `desktop/package.json`, both `.iss` files, `version.json`, and `diagnostics.py` (`node tools/sync-version.js`).
2. Assemble the payload (existing steps, unchanged).
3. Rebuild the offline Python wheelhouse (existing step, unchanged).
4. Build the Electron desktop shell (existing step, unchanged).
5. **NEW**: Compute the release manifest by diffing this payload against the previous published release. Only files whose SHA-256 changed are packaged into `BalajiFeeHub-Update-1.0.1.bcupdate`.
6. **NEW**: Sign the inner manifest with `UPDATER_PRIVATE_KEY_PEM` (secret).
7. Compile `BalajiFeeHub-Server-Setup.exe` and `BalajiFeeHub-Client-Setup.exe` (existing steps, unchanged).
8. **NEW**: Run `tools/validate-release.js` — this is the gate. If **any** check fails (version mismatch across sources, installer missing, `.bcupdate` sha256 mismatch, unsigned draft, invalid manifest, missing min_supported_version, …), the workflow **exits non-zero and the release is NOT published**.
9. On tag push only: create a GitHub Release containing:
    - `BalajiFeeHub-Server-Setup.exe`
    - `BalajiFeeHub-Client-Setup.exe`
    - `BalajiFeeHub-Update-1.0.1.bcupdate`
    - `BalajiFeeHub-Update-1.0.1.manifest.json`
    - `BalajiFeeHub-installed-manifest-1.0.1.json`
    - `SHA256SUMS.txt`
10. On non-tag pushes: the existing `BalajiFeeHub-Installers` artifact is uploaded as before. No release is created. Nothing about the existing build path changes.

## Repository secrets required for signed differential updates

| Secret | Where | Purpose |
|---|---|---|
| `UPDATER_PRIVATE_KEY_PEM` | Repo → Settings → Secrets → Actions | RSA-PSS-SHA256 private key used to sign the inner `manifest.json`. The matching public key already lives inside the backend at `/app/backend/keys/update_public.pem` and is bundled into every installer. **If this secret is missing, `validate-release.js` will fail and block publication.** |

## First-ever release

If there is no previous release, `tools/build-bcupdate.js` detects this and emits a **baseline manifest** (`is_baseline: true`, `full_installer_required: true`). `validate-release.js` accepts this and the release publishes only the full installers — no `.bcupdate`. Every subsequent release compares against this baseline to produce a real delta.

## No-file-change release

If the payload is byte-identical to the previous release (e.g. a documentation-only tag), the manifest is marked `is_noop: true` and no `.bcupdate` is generated. The installer still ships.

## Client behaviour on install PCs

- **On startup**, ~30 seconds after successful login, the Electron app queries `https://api.github.com/repos/<owner>/<repo>/releases/latest` (public API, no auth). If it fails (offline, GitHub down, DNS), the app carries on silently.
- If a newer version is available, the user sees an **"Update Available"** notification and can pick **Update Now** or **Later**.
- **Update Now** downloads only the `.bcupdate` (typically 5–20 MB), verifies its SHA-256 against the release manifest, then posts it to the local backend's `/api/updates/upload` endpoint. The backend re-verifies the RSA signature and per-file hashes, snapshots every file it is about to touch into `/updates/rollback/<id>/`, takes a DB backup, applies the payload, runs pip install if `requirements.txt` changed, and auto-restarts. On any failure it rolls back automatically.
- Rollback snapshots keep the last 3. Any admin can invoke a manual rollback via `/api/updates/rollback/<id>` (Administrator PIN required).

## Emergency recovery

`Help → Check for Updates → Download Full Installer` links directly to the `.exe` on the latest GitHub Release. Use this if:

- the differential update fails repeatedly
- the installation is suspected corrupted
- the client PC pre-dates the differential updater (bootstrap)

The full installer preserves the existing database and backups on repair (see the Server .iss `[Code] InitializeSetup`).

## Files this workflow will NEVER touch

- MongoDB data (`{app}\mongodb\data\`)
- Backups (`{app}\backups\`)
- Logs (`{app}\logs\`)
- `.env` (backend or frontend)
- Any file outside `ALLOWED_PAYLOAD_ROOTS` in `backend/routers/updates.py`

These are the school's operational data and are the reason we bother writing a proper updater instead of shipping a new full installer every time.
