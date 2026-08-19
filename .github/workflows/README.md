# Get Windows EXEs via GitHub Actions — 3 clicks

I put the workflow into `.github/workflows/build-installers.yml`. Here is exactly what you do — **your Main Server stays clean, no Windows PC of yours is touched**.

## Step 1 — Push this codebase to your GitHub account

In the Emergent chat input, click the **"Save to Github"** button and pick a repository name (e.g. `balaji-fee-hub`).

That single click pushes the whole codebase, including the `.github/workflows/build-installers.yml` file, to your new GitHub repo.

## Step 2 — GitHub compiles the EXEs automatically

The moment the push completes, GitHub Actions starts the build on a free Windows runner. In ~4-5 minutes it produces both EXEs, computes SHA-256, and stores them as a downloadable artifact.

Watch it at:
```
https://github.com/<your-username>/balaji-fee-hub/actions
```

## Step 3 — Download the EXEs from GitHub

On the Actions run page you'll see an **Artifacts** section at the bottom:
```
BalajiFeeHub-Installers  (contains 3 files, ~600 MB zipped)
```
Click to download. Inside the zip you'll find:
```
BalajiFeeHub-Server-Setup.exe   (~600 MB, everything bundled including MongoDB)
BalajiFeeHub-Client-Setup.exe   (~150 KB)
SHA256SUMS.txt
```

## Optional — publish a versioned Release

Later, when you want a permanent public download URL, create a Git tag on your repo:
```bash
git tag v1.0.0
git push origin v1.0.0
```
The workflow will additionally attach both EXEs to a GitHub Release, giving you direct URLs like:
```
https://github.com/<you>/balaji-fee-hub/releases/download/v1.0.0/BalajiFeeHub-Server-Setup.exe
https://github.com/<you>/balaji-fee-hub/releases/download/v1.0.0/BalajiFeeHub-Client-Setup.exe
```

## Server EXE payload contents (locked in the workflow)

The workflow explicitly downloads and packs:

| Payload | Source | Verified via SHA-256 |
|---|---|---|
| CORE.zip (installers + wheels + prebuilt frontend + backend + docs) | preview `/downloads/CORE.zip` | ✅ |
| MongoDB Windows Community MSI (569 MB) | joined from msi.001 + msi.002 | ✅ |
| NSSM 2.24 | inside CORE.zip / 05-services/ | ✅ |
| 48 Python wheels for offline pip install | inside CORE.zip / 01-install-main-server/wheels/ | ✅ |
| Prebuilt React static site | inside CORE.zip / 03-source-code/frontend/build/ | ✅ |

The MongoDB MSI parts (.001 + .002) are joined **inside the runner** before Inno Setup packs them — the resulting `BalajiFeeHub-Server-Setup.exe` contains the single full MSI, so the school admin never sees or handles the parts.

## Why this route is safe for your Main Server

- The Main Server never runs any compilation tool.
- Only Inno Setup 6 (used only on the GitHub runner, discarded after each build) touches the payload.
- Every downloaded file's SHA-256 is verified against the published checksums before compilation.
- Only signed, published GitHub Actions from Microsoft's marketplace are used.
