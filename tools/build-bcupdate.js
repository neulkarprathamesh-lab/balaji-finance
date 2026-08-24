#!/usr/bin/env node
/**
 * build-bcupdate.js  --  Differential .bcupdate package generator
 *
 * Runs inside GitHub Actions AFTER the payload has been assembled and
 * BEFORE the Inno Setup installers are compiled.
 *
 * INPUT (all discovered automatically):
 *   /app/VERSION                                     -> current release version
 *   /app/installer-sources/payload/BalajiConventFeeSoftware-v1.0/
 *                                                    -> "current" source tree
 *   env UPDATER_GITHUB_REPO="owner/name"             -> where to look for the
 *                                                       previous release manifest
 *   env UPDATER_PREVIOUS_MANIFEST_URL (optional)     -> explicit override
 *
 * OUTPUT (into installer-sources/Output/):
 *   BalajiFeeHub-Update-<version>.bcupdate           -> the ZIP delta package
 *                                                       (signed by the backend
 *                                                       keys at CI time; if a
 *                                                       CI private key is not
 *                                                       provisioned, this
 *                                                       script generates an
 *                                                       *unsigned draft* and
 *                                                       fails validate-release
 *                                                       so a broken release
 *                                                       cannot be published)
 *   BalajiFeeHub-Update-<version>.manifest.json      -> {version, sha256, size,
 *                                                       min_supported_version,
 *                                                       release_notes,
 *                                                       base_version,
 *                                                       full_installer_required}
 *   BalajiFeeHub-installed-manifest-<version>.json   -> full per-file manifest
 *                                                       (shipped inside the
 *                                                       installer so the
 *                                                       running app knows its
 *                                                       own file inventory)
 *
 * Bcupdate archive layout (must match what backend/routers/updates.py
 * expects at STAGING_DIR/<id>/):
 *
 *   manifest.json      { version, min_supported_version, release_notes,
 *                        files: { "relpath": "sha256hex", ... },
 *                        requires_backend_restart: true,
 *                        requires_frontend_reload: true,
 *                        build_date: "YYYY-MM-DD" }
 *   manifest.sig       RSA-PSS signature of manifest.json (base64)
 *   payload/           only the files whose sha256 differs from the previous
 *                      release manifest (i.e. differential), with paths
 *                      relative to APP_ROOT on the installed machine.
 *
 * Package-path mapping (payload tree -> backend APP_ROOT relative paths):
 *
 *   payload/03-source-code/backend/     -> backend/
 *   payload/03-source-code/frontend/    -> frontend/
 *   payload/version.json (if present)   -> version.json
 *
 * Anything else in the payload tree (wheels, MongoDB MSI, 04-desktop, .bat
 * scripts) is INTENTIONALLY EXCLUDED from differential updates. Those
 * change rarely and are recovered via the full installer if needed.
 */

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const crypto = require('crypto');
const https = require('https');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const PAYLOAD_ROOT = path.join(ROOT, 'installer-sources', 'payload', 'BalajiConventFeeSoftware-v1.0');
const OUTPUT_DIR = path.join(ROOT, 'installer-sources', 'Output');

// Map <payload tree relative path prefix>  ->  <backend APP_ROOT relative prefix>
const PATH_MAP = [
  { fromPrefix: path.normalize('03-source-code/backend'),  toPrefix: 'backend'  },
  { fromPrefix: path.normalize('03-source-code/frontend'), toPrefix: 'frontend' },
  { fromPrefix: path.normalize('version.json'),            toPrefix: 'version.json', isFile: true },
];

// Only these APP_ROOT-relative prefixes are ever allowed in a manifest.
// (Backend's updates.py enforces this too - defense in depth.)
const ALLOWED_APP_PREFIXES = [
  'frontend/build',
  'backend/core.py',
  'backend/server.py',
  'backend/routers',
  'backend/requirements.txt',
  'frontend/package.json',
  'version.json',
];

function log(...a) { console.log('[build-bcupdate]', ...a); }
function warn(...a) { console.warn('[build-bcupdate]', ...a); }
function fail(msg) { console.error('[build-bcupdate] FAIL:', msg); process.exit(1); }

function sha256File(p) {
  const h = crypto.createHash('sha256');
  h.update(fs.readFileSync(p));
  return h.digest('hex');
}

function sha256Bytes(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function walk(dir) {
  const out = [];
  function rec(d) {
    for (const ent of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, ent.name);
      if (ent.isDirectory()) rec(full);
      else if (ent.isFile()) out.push(full);
    }
  }
  rec(dir);
  return out;
}

function mapPayloadToAppPath(payloadRel) {
  const norm = payloadRel.replace(/\\/g, '/');
  for (const m of PATH_MAP) {
    const fp = m.fromPrefix.replace(/\\/g, '/');
    if (m.isFile) {
      if (norm === fp) return m.toPrefix;
      continue;
    }
    if (norm === fp || norm.startsWith(fp + '/')) {
      return m.toPrefix + norm.slice(fp.length);
    }
  }
  return null; // not part of the differential payload
}

function isAppPathAllowed(appRel) {
  const norm = appRel.replace(/\\/g, '/');
  return ALLOWED_APP_PREFIXES.some((p) => norm === p || norm.startsWith(p + '/'));
}

function readCurrentVersion() {
  const p = path.join(ROOT, 'VERSION');
  if (!fs.existsSync(p)) fail('missing /app/VERSION');
  return fs.readFileSync(p, 'utf8').trim();
}

function fetchJson(url, timeoutMs = 10000) {
  // file:// scheme for local testing (harmless in CI which uses https URLs).
  if (url.startsWith('file://')) {
    return new Promise((resolve, reject) => {
      try {
        const p = url.replace(/^file:\/\//, '');
        resolve(JSON.parse(fs.readFileSync(p, 'utf8')));
      } catch (e) { reject(e); }
    });
  }
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { 'User-Agent': 'BalajiFeeHub-CI' }}, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        fetchJson(res.headers.location, timeoutMs).then(resolve, reject);
        return;
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode} for ${url}`)); }
      let body = '';
      res.on('data', (c) => { body += c.toString('utf8'); });
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch (e) { reject(new Error('non-JSON body')); }
      });
    });
    req.on('error', reject);
    req.setTimeout(timeoutMs, () => { req.destroy(new Error('timeout')); });
  });
}

async function fetchPreviousInstalledManifest() {
  const explicit = process.env.UPDATER_PREVIOUS_MANIFEST_URL;
  if (explicit) {
    log('Fetching previous manifest from explicit URL:', explicit);
    try { return await fetchJson(explicit); }
    catch (e) { warn('explicit URL failed:', e.message); return null; }
  }
  const repo = process.env.UPDATER_GITHUB_REPO;
  if (!repo) {
    warn('UPDATER_GITHUB_REPO not set; skipping previous-release lookup.');
    return null;
  }
  const releasesUrl = `https://api.github.com/repos/${repo}/releases/latest`;
  try {
    const rel = await fetchJson(releasesUrl);
    const asset = (rel.assets || []).find((a) => /installed-manifest.*\.json$/i.test(a.name));
    if (!asset) { warn('previous release has no installed-manifest asset'); return null; }
    return await fetchJson(asset.browser_download_url);
  } catch (e) {
    warn('could not fetch previous release manifest:', e.message);
    return null;
  }
}

function buildCurrentInstalledManifest(version) {
  if (!fs.existsSync(PAYLOAD_ROOT)) fail(`payload root missing: ${PAYLOAD_ROOT}`);
  const files = walk(PAYLOAD_ROOT);
  const manifest = {
    version,
    generated_at: new Date().toISOString(),
    payload_root_hint: 'BalajiConventFeeSoftware-v1.0',
    files: {}, // payload-relative path -> { sha256, size }
    app_files: {}, // APP_ROOT-relative path -> { sha256, size } (subset - only diffable roots)
  };
  for (const f of files) {
    const rel = path.relative(PAYLOAD_ROOT, f);
    const sha = sha256File(f);
    const size = fs.statSync(f).size;
    manifest.files[rel.replace(/\\/g, '/')] = { sha256: sha, size };
    const appRel = mapPayloadToAppPath(rel);
    if (appRel && isAppPathAllowed(appRel)) {
      manifest.app_files[appRel.replace(/\\/g, '/')] = { sha256: sha, size, source: rel.replace(/\\/g, '/') };
    }
  }
  return manifest;
}

function diff(currentAppFiles, prevAppFiles) {
  // Returns { changed: {appRel: {sha256, size, source}}, removed: [appRel] }
  const changed = {};
  const removed = [];
  for (const [k, v] of Object.entries(currentAppFiles)) {
    if (!prevAppFiles || !prevAppFiles[k] || prevAppFiles[k].sha256 !== v.sha256) {
      changed[k] = v;
    }
  }
  if (prevAppFiles) {
    for (const k of Object.keys(prevAppFiles)) {
      if (!currentAppFiles[k]) removed.push(k);
    }
  }
  return { changed, removed };
}

function signManifest(manifestBytes, privateKeyPem) {
  const s = crypto.createSign('RSA-SHA256');
  s.update(manifestBytes);
  return s.sign({ key: privateKeyPem, padding: crypto.constants.RSA_PKCS1_PSS_PADDING, saltLength: crypto.constants.RSA_PSS_SALTLEN_MAX_SIGN }, 'base64');
}

function zipDirectory(srcDir, zipPath) {
  // Use PowerShell Compress-Archive on Windows CI, fallback to `zip` on POSIX.
  const isWin = process.platform === 'win32';
  let r;
  if (isWin) {
    r = spawnSync('powershell', ['-NoProfile', '-Command',
      `Compress-Archive -Path "${srcDir}\\*" -DestinationPath "${zipPath}" -Force`
    ], { stdio: 'inherit' });
  } else {
    r = spawnSync('sh', ['-c', `cd "${srcDir}" && zip -r "${zipPath}" .`], { stdio: 'inherit' });
  }
  if (r.status !== 0) fail(`zipping failed for ${srcDir} -> ${zipPath} (exit ${r.status})`);
}

function isInDifferentialScope(payloadRel) {
  const norm = payloadRel.replace(/\\/g, '/');
  return PATH_MAP.some((m) => {
    if (m.isFile) return norm === m.fromPrefix.replace(/\\/g, '/');
    const pn = m.fromPrefix.replace(/\\/g, '/');
    return norm === pn || norm.startsWith(pn + '/');
  });
}

// The differential .bcupdate can only ever cover backend/ + frontend/build/
// (see PATH_MAP above). Anything else that changed since the previous
// release - the Electron shell, installer scripts, MongoDB/NSSM bundle -
// can ONLY be delivered via the full installer. Detecting this explicitly
// prevents ever silently shipping a "differential update" that misses a
// real Electron/installer fix (exactly the failure mode that caused the
// original stale-frontend bug this updater exists to fix).
function detectOutOfScopeChanges(currentFiles, prevFiles) {
  const desktopPrefix = '04-desktop/';
  const scriptPrefixes = ['01-install-main-server/', '02-install-client-pc/', '05-services/'];
  let desktopChanged = false;
  let installerScriptsChanged = false;
  let otherChanged = false;
  const allKeys = new Set([...Object.keys(currentFiles || {}), ...Object.keys(prevFiles || {})]);
  for (const k of allKeys) {
    if (isInDifferentialScope(k)) continue;
    const a = currentFiles ? currentFiles[k] : undefined;
    const b = prevFiles ? prevFiles[k] : undefined;
    const changed = !a || !b || a.sha256 !== b.sha256;
    if (!changed) continue;
    if (k.startsWith(desktopPrefix)) desktopChanged = true;
    else if (scriptPrefixes.some((p) => k.startsWith(p))) installerScriptsChanged = true;
    else otherChanged = true;
  }
  return { desktopChanged, installerScriptsChanged, otherChanged };
}

async function main() {
  const version = readCurrentVersion();
  const buildDate = new Date().toISOString().slice(0, 10);
  await fsp.mkdir(OUTPUT_DIR, { recursive: true });

  log(`Version: ${version}`);
  log(`Payload: ${PAYLOAD_ROOT}`);
  log(`Output : ${OUTPUT_DIR}`);

  // 1. Build the current installed-manifest.json
  const current = buildCurrentInstalledManifest(version);
  const currentAppFileCount = Object.keys(current.app_files).length;
  log(`Indexed ${Object.keys(current.files).length} total payload files, ${currentAppFileCount} eligible for differential update.`);
  const installedManifestPath = path.join(OUTPUT_DIR, `BalajiFeeHub-installed-manifest-${version}.json`);
  fs.writeFileSync(installedManifestPath, JSON.stringify(current, null, 2), 'utf8');
  log(`Wrote ${path.relative(ROOT, installedManifestPath)}`);

  // Also drop a copy inside the payload so a fresh install carries its
  // own inventory - the updater on the target machine reads this to know
  // exactly what it has.
  try {
    const inPayloadCopy = path.join(PAYLOAD_ROOT, 'updates', 'installed-manifest.json');
    fs.mkdirSync(path.dirname(inPayloadCopy), { recursive: true });
    fs.writeFileSync(inPayloadCopy, JSON.stringify({ version, files: current.app_files, generated_at: current.generated_at }, null, 2), 'utf8');
    log(`Embedded manifest into payload at updates/installed-manifest.json`);
  } catch (e) {
    warn('failed to embed manifest in payload:', e.message);
  }

  // 2. Fetch the previous release's manifest (if any)
  const prev = await fetchPreviousInstalledManifest();
  if (!prev) {
    log('No previous release manifest -- this is a BASELINE release (no differential).');
    // Emit a stub release-manifest so the release_validator recognises this
    // situation and does NOT fail the build.
    const stub = {
      version,
      base_version: null,
      is_baseline: true,
      full_installer_required: true,
      release_notes: 'Baseline release - no differential update package (fresh installations use the full installer).',
      build_date: buildDate,
      sha256: null,
      size: 0,
      min_supported_version: version,
      components: null,
    };
    const p = path.join(OUTPUT_DIR, `BalajiFeeHub-Update-${version}.manifest.json`);
    fs.writeFileSync(p, JSON.stringify(stub, null, 2), 'utf8');
    log(`Wrote baseline manifest: ${path.relative(ROOT, p)}`);
    return;
  }

  const baseVersion = prev.version || 'unknown';
  const { changed, removed } = diff(current.app_files, prev.app_files || prev.files || {});
  const changedCount = Object.keys(changed).length;
  const outOfScope = detectOutOfScopeChanges(current.files, prev.files || {});
  const fullInstallerRequired = outOfScope.desktopChanged || outOfScope.installerScriptsChanged || outOfScope.otherChanged;
  log(`Diff vs ${baseVersion}: ${changedCount} changed file(s), ${removed.length} removed.`);
  if (fullInstallerRequired) {
    log(`Out-of-scope changes detected (desktop=${outOfScope.desktopChanged}, installer_scripts=${outOfScope.installerScriptsChanged}, other=${outOfScope.otherChanged}) - full_installer_required will be set.`);
  }

  if (changedCount === 0) {
    log('No differential-eligible (backend/frontend) file changes between releases.');
    const noop = {
      version,
      base_version: baseVersion,
      is_baseline: false,
      is_noop: !fullInstallerRequired,
      full_installer_required: fullInstallerRequired,
      release_notes: fullInstallerRequired
        ? 'This release only changes the desktop application and/or installer scripts - install via the full installer.'
        : 'No application file changes in this release (documentation-only).',
      build_date: buildDate,
      sha256: null,
      size: 0,
      min_supported_version: baseVersion,
      components: {
        backend: false,
        frontend: false,
        desktop: outOfScope.desktopChanged,
        installer_scripts: outOfScope.installerScriptsChanged,
      },
    };
    fs.writeFileSync(path.join(OUTPUT_DIR, `BalajiFeeHub-Update-${version}.manifest.json`),
                     JSON.stringify(noop, null, 2), 'utf8');
    return;
  }

  // 3. Assemble the .bcupdate archive
  const stagingRoot = path.join(OUTPUT_DIR, `_stage-${version}`);
  const payloadDir = path.join(stagingRoot, 'payload');
  if (fs.existsSync(stagingRoot)) fs.rmSync(stagingRoot, { recursive: true, force: true });
  fs.mkdirSync(payloadDir, { recursive: true });

  const filesMap = {}; // "appRel" -> sha256 (backend manifest format)
  for (const [appRel, meta] of Object.entries(changed)) {
    if (!isAppPathAllowed(appRel)) fail(`ILLEGAL app path in diff: ${appRel}`);
    const srcAbs = path.join(PAYLOAD_ROOT, meta.source);
    const dstAbs = path.join(payloadDir, appRel);
    fs.mkdirSync(path.dirname(dstAbs), { recursive: true });
    fs.copyFileSync(srcAbs, dstAbs);
    filesMap[appRel] = meta.sha256;
  }

  // Build inner manifest.json (matches backend/routers/updates.py contract)
  const releaseNotes = process.env.UPDATER_RELEASE_NOTES ||
    `Version ${version} - ${changedCount} file(s) updated since ${baseVersion}.`;
  const innerManifest = {
    version,
    min_supported_version: baseVersion,
    release_notes: releaseNotes,
    build_date: buildDate,
    files: filesMap,
    migrations: [], // populate manually via UPDATER_MIGRATIONS if ever needed
    requires_backend_restart: true,
    requires_frontend_reload: true,
    database_version: '1',
  };
  const innerManifestPath = path.join(stagingRoot, 'manifest.json');
  const innerBytes = Buffer.from(JSON.stringify(innerManifest, null, 2), 'utf8');
  fs.writeFileSync(innerManifestPath, innerBytes);

  // Sign the manifest (if a private key is provisioned)
  const privKey = process.env.UPDATER_PRIVATE_KEY_PEM || null;
  let sigB64 = null;
  if (privKey) {
    sigB64 = signManifest(innerBytes, privKey);
    fs.writeFileSync(path.join(stagingRoot, 'manifest.sig'), sigB64, 'utf8');
    log('Signed manifest with UPDATER_PRIVATE_KEY_PEM.');
  } else {
    warn('UPDATER_PRIVATE_KEY_PEM not set - writing UNSIGNED draft. validate-release will FAIL and block publication.');
    fs.writeFileSync(path.join(stagingRoot, 'manifest.sig'), 'UNSIGNED_DRAFT', 'utf8');
  }

  // Zip -> .bcupdate
  const bcupdatePath = path.join(OUTPUT_DIR, `BalajiFeeHub-Update-${version}.bcupdate`);
  if (fs.existsSync(bcupdatePath)) fs.unlinkSync(bcupdatePath);
  zipDirectory(stagingRoot, bcupdatePath);
  fs.rmSync(stagingRoot, { recursive: true, force: true });

  const size = fs.statSync(bcupdatePath).size;
  const sha  = sha256File(bcupdatePath);
  log(`Built ${path.basename(bcupdatePath)} - ${(size / 1024 / 1024).toFixed(2)} MB, sha256=${sha}`);

  // 4. Emit the outer release manifest.json
  const outer = {
    version,
    base_version: baseVersion,
    is_baseline: false,
    is_noop: false,
    full_installer_required: fullInstallerRequired,
    release_notes: releaseNotes,
    build_date: buildDate,
    sha256: sha,
    size: size,
    min_supported_version: baseVersion,
    signed: !!privKey,
    changed_file_count: changedCount,
    removed_file_count: removed.length,
    delta_asset: path.basename(bcupdatePath),
    components: {
      backend: Object.keys(changed).some((k) => k === 'backend' || k.startsWith('backend/')),
      frontend: Object.keys(changed).some((k) => k === 'frontend' || k.startsWith('frontend/')),
      desktop: outOfScope.desktopChanged,
      installer_scripts: outOfScope.installerScriptsChanged,
    },
  };
  fs.writeFileSync(path.join(OUTPUT_DIR, `BalajiFeeHub-Update-${version}.manifest.json`),
                   JSON.stringify(outer, null, 2), 'utf8');
  log(`Wrote outer manifest: BalajiFeeHub-Update-${version}.manifest.json`);
}

main().catch((e) => fail(e.stack || e.message));
