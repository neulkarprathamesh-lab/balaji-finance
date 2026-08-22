# Differential Update Architecture

## Summary

- **Full installer** (~700 MB) — new/recovery installs only. Contains MongoDB MSI + Python wheels + Electron + React + installer scripts.
- **Differential `.bcupdate`** (~5–20 MB typical) — existing installs pull only changed backend/frontend files from GitHub Releases.

## Component split

| Component | Full installer | Differential | Rationale |
|---|---|---|---|
| MongoDB MSI (~500 MB) | ✅ | ❌ | Almost never changes; full installer only |
| Python wheels (~200 MB) | ✅ | ❌ | Bumped rarely; full installer only |
| Electron shell (~150 MB) | ✅ | ❌ | Client-side app; if it must change, use full installer |
| Backend Python `.py` | ✅ | ✅ | Changes often — safe to hot-swap while service stopped |
| Frontend `build/` | ✅ | ✅ | Changes often — served by backend; atomic swap |
| Installer scripts | ✅ | (optional) | Live in installer, not in APP_ROOT — full installer only |
| `version.json` | ✅ | ✅ | Bumped on every release |

## Data protection

The updater **never** touches:

- `{app}\mongodb\data\` — the actual MongoDB data files
- `{app}\backups\` — school backups
- `{app}\logs\`
- Any `.env` file
- Any path outside the whitelist in `backend/routers/updates.py::ALLOWED_PAYLOAD_ROOTS`

Backend also enforces this whitelist server-side; the CI-side generator refuses to build a `.bcupdate` that references anything outside it.

## Trust chain

1. **CI signs** `manifest.json` with `UPDATER_PRIVATE_KEY_PEM` (RSA-PSS-SHA256).
2. **Installer ships** the matching `update_public.pem` inside `backend/keys/`.
3. **Electron client** downloads `.bcupdate` + verifies release-level SHA-256 against public GitHub Release manifest.
4. **Backend re-verifies** the RSA signature over `manifest.json` before touching a single file.
5. **Backend re-verifies** every listed file's SHA-256 against the manifest.
6. **Backend snapshots** every file it will replace into `/updates/rollback/<id>/`.
7. **Backend replaces** files.
8. **Backend auto-rollbacks** on any failure step (apply, pip install, migration).

Any of steps 1–5 failing aborts before the filesystem is modified.

## Version SSOT

`/app/VERSION` is the single source. `tools/sync-version.js` propagates it to:

- `desktop/package.json`
- `installer-sources/BalajiFeeHub-Server-Setup.iss`
- `installer-sources/BalajiFeeHub-Client-Setup.iss`
- `version.json`
- `backend/routers/diagnostics.py`

Backend `/api/version` reads `version.json` at request-time so a fresh `.bcupdate` install becomes visible without a code-level restart.

## Release trigger

- **Every push**: build + upload artifact (existing behaviour, unchanged).
- **Tag `v*` push**: build + validate + publish GitHub Release with full installer + `.bcupdate` + manifests.
- **No auto-tagging** — releases are always explicit.

## Client → GitHub flow

```
Balaji FeeHub (Electron)
    |
    | GET https://api.github.com/repos/<owner>/<repo>/releases/latest
    v
Release JSON with assets: [.bcupdate, .manifest.json, .exe, SHA256SUMS.txt]
    |
    | Fetch .manifest.json (public, ~2 KB)
    v
{version, sha256, size, min_supported_version, release_notes}
    |
    | Compare (semver) with installed version
    v
If upgrade -> notify user -> [Update Now] -> download .bcupdate -> verify SHA-256
    |
    | POST /api/updates/upload  (multipart, admin PIN)
    v
Backend verifies signature + per-file SHA-256 + path whitelist
    |
    | POST /api/updates/install/<update_id>  (admin PIN)
    v
Backend: DB backup -> config snapshot -> file snapshot -> apply -> pip -> migrate -> version.json -> restart
    |
    | Electron reconnects after ~5 seconds
    v
Version bump visible in About dialog and /api/version.
```

## Rollback

- Backend keeps the last 3 rollback snapshots (`ROLLBACK_KEEP = 3`).
- Auto-triggered by the backend on any failed apply/pip/migration step.
- Manually triggerable via `POST /api/updates/rollback/<rollback_id>` (Administrator PIN required).

## Files never modified by updater

Enforced in two places:

1. **CI-side** — `tools/build-bcupdate.js::ALLOWED_APP_PREFIXES` refuses to emit a package containing any other path.
2. **Backend-side** — `backend/routers/updates.py::ALLOWED_PAYLOAD_ROOTS` re-validates on upload AND on install.

Defence in depth.
