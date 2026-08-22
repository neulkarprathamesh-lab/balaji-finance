#!/usr/bin/env node
/**
 * sync-version.js — Propagates /app/VERSION to every consumer.
 *
 * Reads:   /app/VERSION           (single source of truth)
 * Writes:  /app/desktop/package.json                        ("version": "...")
 *          /app/installer-sources/BalajiFeeHub-Server-Setup.iss  (#define AppVersion ...)
 *          /app/installer-sources/BalajiFeeHub-Client-Setup.iss  (#define AppVersion ...)
 *          /app/version.json                                (version: "...", build_date auto)
 *          /app/backend/routers/diagnostics.py             (APP_VERSION = "...")
 *
 * Idempotent. Fails hard if VERSION is malformed or a target file is missing.
 * Called by CI before build; may also be run locally.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const VERSION_FILE = path.join(ROOT, 'VERSION');

function fail(msg) {
  console.error('sync-version FAILED:', msg);
  process.exit(1);
}

function readVersion() {
  if (!fs.existsSync(VERSION_FILE)) fail(`missing ${VERSION_FILE}`);
  const v = fs.readFileSync(VERSION_FILE, 'utf8').trim();
  if (!/^\d+\.\d+\.\d+(-[0-9a-zA-Z.-]+)?$/.test(v)) {
    fail(`invalid semver in VERSION file: "${v}" (expected e.g. 1.0.1 or 1.0.1-beta.2)`);
  }
  return v;
}

function replaceInFile(file, pattern, replacer, label) {
  if (!fs.existsSync(file)) fail(`target file missing: ${file}`);
  const before = fs.readFileSync(file, 'utf8');
  const after = before.replace(pattern, replacer);
  if (before === after) {
    console.warn(`[warn] ${label}: pattern did not match -> ${file}`);
    return false;
  }
  fs.writeFileSync(file, after, 'utf8');
  console.log(`[ok]   ${label} -> ${path.relative(ROOT, file)}`);
  return true;
}

function main() {
  const version = readVersion();
  const buildDate = new Date().toISOString().slice(0, 10);
  console.log(`Syncing version ${version}  (build_date ${buildDate})\n`);

  // 1. desktop/package.json
  {
    const p = path.join(ROOT, 'desktop', 'package.json');
    if (!fs.existsSync(p)) fail(`missing ${p}`);
    const pkg = JSON.parse(fs.readFileSync(p, 'utf8'));
    pkg.version = version;
    fs.writeFileSync(p, JSON.stringify(pkg, null, 2) + '\n', 'utf8');
    console.log(`[ok]   desktop/package.json version=${version}`);
  }

  // 2. Server .iss
  replaceInFile(
    path.join(ROOT, 'installer-sources', 'BalajiFeeHub-Server-Setup.iss'),
    /#define AppVersion\s+"[^"]+"/,
    `#define AppVersion         "${version}"`,
    'Server .iss AppVersion'
  );

  // 3. Client .iss
  replaceInFile(
    path.join(ROOT, 'installer-sources', 'BalajiFeeHub-Client-Setup.iss'),
    /#define AppVersion\s+"[^"]+"/,
    `#define AppVersion         "${version}"`,
    'Client .iss AppVersion'
  );

  // 4. version.json — read + merge so we do not lose other keys
  {
    const p = path.join(ROOT, 'version.json');
    let v = {};
    if (fs.existsSync(p)) {
      try { v = JSON.parse(fs.readFileSync(p, 'utf8')); } catch (_) { v = {}; }
    }
    v.version = version;
    v.build_date = buildDate;
    v.database_version = v.database_version || '1';
    v.receipt_template_version = v.receipt_template_version || '1.0';
    v.app_template_version = v.app_template_version || '1.0';
    fs.writeFileSync(p, JSON.stringify(v, null, 2) + '\n', 'utf8');
    console.log(`[ok]   version.json version=${version} build_date=${buildDate}`);
  }

  // 5. backend/routers/diagnostics.py APP_VERSION
  replaceInFile(
    path.join(ROOT, 'backend', 'routers', 'diagnostics.py'),
    /APP_VERSION\s*=\s*"[^"]+"/,
    `APP_VERSION = "${version}"`,
    'diagnostics.py APP_VERSION'
  );

  console.log(`\nAll version consumers now report ${version}.`);
}

main();
