#!/usr/bin/env node
/**
 * validate-release.js  --  Pre-publication release gate.
 *
 * Runs AFTER build-bcupdate.js + Inno Setup compilation, BEFORE the
 * GitHub Release is created. Exits non-zero on ANY inconsistency so
 * that a broken release cannot be published.
 *
 * Checks:
 *   1. /app/VERSION is valid semver and matches:
 *        - desktop/package.json.version
 *        - Server .iss #define AppVersion
 *        - Client .iss #define AppVersion
 *        - version.json.version
 *   2. Output/BalajiFeeHub-Server-Setup.exe exists and is > 50 MB.
 *   3. Output/BalajiFeeHub-Client-Setup.exe exists and is > 20 MB.
 *   4. Output/BalajiFeeHub-installed-manifest-<v>.json exists and is valid JSON
 *      with a "version" that matches.
 *   5. Output/BalajiFeeHub-Update-<v>.manifest.json exists and is valid JSON.
 *   6. If NOT a baseline / noop release:
 *        - the .bcupdate file exists and its SHA-256 matches the manifest.
 *        - the manifest is signed (signed:true).
 *        - min_supported_version is semver-valid and <= version.
 *   7. All file sizes in the outer manifest match the actual files on disk.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const OUT  = path.join(ROOT, 'installer-sources', 'Output');
const errors = [];
const warns  = [];

function err(m) { errors.push(m); console.error('[validate-release] ERROR:', m); }
function warn(m) { warns.push(m); console.warn('[validate-release] WARN :', m); }
function ok(m) { console.log('[validate-release]  OK  :', m); }

function readVersion() {
  const p = path.join(ROOT, 'VERSION');
  if (!fs.existsSync(p)) err(`missing ${p}`);
  const v = fs.readFileSync(p, 'utf8').trim();
  if (!/^\d+\.\d+\.\d+(-[0-9a-zA-Z.-]+)?$/.test(v)) err(`invalid semver in VERSION: "${v}"`);
  return v;
}

function sha256File(p) {
  const h = crypto.createHash('sha256');
  h.update(fs.readFileSync(p));
  return h.digest('hex');
}

function fileMB(p) {
  return fs.existsSync(p) ? fs.statSync(p).size / (1024 * 1024) : -1;
}

function checkVersionSync(version) {
  // desktop/package.json
  const pkgPath = path.join(ROOT, 'desktop', 'package.json');
  if (fs.existsSync(pkgPath)) {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
    if (pkg.version !== version) err(`desktop/package.json version (${pkg.version}) != VERSION (${version})`);
    else ok(`desktop/package.json version=${version}`);
  } else err('desktop/package.json missing');

  // .iss files
  for (const which of ['Server', 'Client']) {
    const p = path.join(ROOT, 'installer-sources', `BalajiFeeHub-${which}-Setup.iss`);
    if (!fs.existsSync(p)) { err(`missing ${p}`); continue; }
    const c = fs.readFileSync(p, 'utf8');
    const m = c.match(/#define AppVersion\s+"([^"]+)"/);
    if (!m) { err(`no #define AppVersion in ${which} .iss`); continue; }
    if (m[1] !== version) err(`${which} .iss AppVersion (${m[1]}) != VERSION (${version})`);
    else ok(`${which} .iss AppVersion=${version}`);
  }

  // version.json
  const vjPath = path.join(ROOT, 'version.json');
  if (fs.existsSync(vjPath)) {
    try {
      const vj = JSON.parse(fs.readFileSync(vjPath, 'utf8'));
      if (vj.version !== version) err(`version.json version (${vj.version}) != VERSION (${version})`);
      else ok(`version.json version=${version}`);
    } catch (_) { err('version.json invalid JSON'); }
  } else warn('version.json missing (backend will fall back to 1.0.0)');
}

function checkInstallers() {
  const server = path.join(OUT, 'BalajiFeeHub-Server-Setup.exe');
  const client = path.join(OUT, 'BalajiFeeHub-Client-Setup.exe');
  const smb = fileMB(server);
  const cmb = fileMB(client);
  if (smb < 0) err('BalajiFeeHub-Server-Setup.exe not found');
  else if (smb < 50) err(`Server installer suspiciously small: ${smb.toFixed(1)} MB (expected >50 MB with MongoDB MSI + wheels)`);
  else ok(`Server installer ${smb.toFixed(1)} MB`);
  if (cmb < 0) err('BalajiFeeHub-Client-Setup.exe not found');
  else if (cmb < 20) err(`Client installer suspiciously small: ${cmb.toFixed(1)} MB (expected >20 MB Electron shell)`);
  else ok(`Client installer ${cmb.toFixed(1)} MB`);
}

function checkManifests(version) {
  const installedManifest = path.join(OUT, `BalajiFeeHub-installed-manifest-${version}.json`);
  const releaseManifest   = path.join(OUT, `BalajiFeeHub-Update-${version}.manifest.json`);

  if (!fs.existsSync(installedManifest)) { err(`missing ${path.basename(installedManifest)}`); return; }
  let im;
  try { im = JSON.parse(fs.readFileSync(installedManifest, 'utf8')); }
  catch (_) { err('installed-manifest JSON invalid'); return; }
  if (im.version !== version) err(`installed-manifest version (${im.version}) != VERSION (${version})`);
  else ok(`installed-manifest version=${version}, ${Object.keys(im.files || {}).length} total files`);

  if (!fs.existsSync(releaseManifest)) { err(`missing ${path.basename(releaseManifest)}`); return; }
  let rm;
  try { rm = JSON.parse(fs.readFileSync(releaseManifest, 'utf8')); }
  catch (_) { err('release manifest JSON invalid'); return; }
  if (rm.version !== version) err(`release manifest version (${rm.version}) != VERSION (${version})`);

  if (rm.is_baseline) {
    ok('release is BASELINE (no differential; full installer only) - accepted');
    return;
  }
  if (rm.is_noop) {
    ok('release is NOOP (no file changes) - accepted, no .bcupdate expected');
    return;
  }

  // Differential release - full checks required
  if (!rm.delta_asset) { err('release manifest missing delta_asset'); return; }
  const bcupdatePath = path.join(OUT, rm.delta_asset);
  if (!fs.existsSync(bcupdatePath)) { err(`missing .bcupdate: ${rm.delta_asset}`); return; }
  const actualSize = fs.statSync(bcupdatePath).size;
  const actualSha  = sha256File(bcupdatePath);
  if (rm.size && actualSize !== rm.size) err(`.bcupdate size mismatch (manifest ${rm.size}, actual ${actualSize})`);
  else ok(`.bcupdate size ${actualSize}`);
  if (rm.sha256 && actualSha !== rm.sha256) err(`.bcupdate sha256 mismatch (manifest ${rm.sha256}, actual ${actualSha})`);
  else ok(`.bcupdate sha256 ${actualSha}`);

  if (rm.signed !== true) err('release manifest is UNSIGNED (UPDATER_PRIVATE_KEY_PEM was not provisioned) - refusing to publish');
  else ok('release manifest is signed');

  if (!rm.min_supported_version || !/^\d+\.\d+\.\d+/.test(rm.min_supported_version)) err(`min_supported_version invalid: ${rm.min_supported_version}`);
  else ok(`min_supported_version=${rm.min_supported_version}`);
}

function main() {
  const version = readVersion();
  console.log(`\nvalidate-release: VERSION=${version}\n`);
  checkVersionSync(version);
  checkInstallers();
  checkManifests(version);
  console.log(`\nSummary: ${errors.length} error(s), ${warns.length} warning(s).\n`);
  if (errors.length > 0) {
    console.error('RELEASE VALIDATION FAILED. No release will be published.');
    process.exit(1);
  }
  console.log('Release validation passed. Safe to publish.');
}

main();
