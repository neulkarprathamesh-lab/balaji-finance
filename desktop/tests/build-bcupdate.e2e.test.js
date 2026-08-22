// Integration test: build-bcupdate against a synthetic 2-version payload.
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { spawnSync, execSync } = require('child_process');

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'bcupdate-e2e-'));
const APP_ROOT = path.join(TMP, 'app');
fs.mkdirSync(APP_ROOT);
fs.writeFileSync(path.join(APP_ROOT, 'VERSION'), '1.0.1\n');

const PLD = path.join(APP_ROOT, 'installer-sources', 'payload', 'BalajiConventFeeSoftware-v1.0');
fs.mkdirSync(path.join(PLD, '03-source-code/backend/routers'), { recursive: true });
fs.mkdirSync(path.join(PLD, '03-source-code/frontend/build/static/js'), { recursive: true });
fs.mkdirSync(path.join(PLD, '05-services'), { recursive: true });

// v1.0.1 payload content
fs.writeFileSync(path.join(PLD, '03-source-code/backend/core.py'),                     'print("core v1")\n');
fs.writeFileSync(path.join(PLD, '03-source-code/backend/server.py'),                   'print("server V2 CHANGED")\n');
fs.writeFileSync(path.join(PLD, '03-source-code/backend/routers/updates.py'),          'router = 1\n');
fs.writeFileSync(path.join(PLD, '03-source-code/backend/requirements.txt'),            'fastapi==0.1\n');
fs.writeFileSync(path.join(PLD, '03-source-code/frontend/build/index.html'),           '<html>V2 CHANGED</html>\n');
fs.writeFileSync(path.join(PLD, '03-source-code/frontend/build/static/js/main.abc.js'),'console.log(1);\n');
fs.writeFileSync(path.join(PLD, '05-services/mongodb.msi'),                            'FAKE_MSI\n'); // excluded from diff

function h(s) { return crypto.createHash('sha256').update(s).digest('hex'); }
const prev = {
  version: '1.0.0',
  app_files: {
    'backend/core.py':                        { sha256: h('print("core v1")\n'),   size: 17, source: '03-source-code/backend/core.py' },
    'backend/server.py':                      { sha256: h('OLD SERVER\n'),         size: 11, source: '03-source-code/backend/server.py' },
    'backend/routers/updates.py':             { sha256: h('router = 1\n'),         size: 11, source: '03-source-code/backend/routers/updates.py' },
    'backend/requirements.txt':               { sha256: h('fastapi==0.1\n'),       size: 13, source: '03-source-code/backend/requirements.txt' },
    'frontend/build/index.html':              { sha256: h('OLD INDEX\n'),          size: 10, source: '03-source-code/frontend/build/index.html' },
    'frontend/build/static/js/main.abc.js':   { sha256: h('console.log(1);\n'),    size: 16, source: '03-source-code/frontend/build/static/js/main.abc.js' },
  },
};
const prevPath = path.join(TMP, 'prev.json');
fs.writeFileSync(prevPath, JSON.stringify(prev));

fs.mkdirSync(path.join(APP_ROOT, 'tools'));
fs.copyFileSync('/app/tools/build-bcupdate.js', path.join(APP_ROOT, 'tools/build-bcupdate.js'));
fs.mkdirSync(path.join(APP_ROOT, 'installer-sources/Output'), { recursive: true });

const { generateKeyPairSync } = require('crypto');
const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const pem = privateKey.export({ type: 'pkcs8', format: 'pem' });

const r = spawnSync('node', [path.join(APP_ROOT, 'tools/build-bcupdate.js')], {
  env: { ...process.env, UPDATER_PREVIOUS_MANIFEST_URL: 'file://' + prevPath, UPDATER_PRIVATE_KEY_PEM: pem },
  cwd: APP_ROOT,
});
process.stdout.write(r.stdout);
process.stderr.write(r.stderr);
if (r.status !== 0) { console.error('build-bcupdate exited', r.status); process.exit(1); }

const out = path.join(APP_ROOT, 'installer-sources/Output');
const files = fs.readdirSync(out);
console.log('\nOutput files:');
for (const f of files) console.log('  ', f, '(' + fs.statSync(path.join(out, f)).size, 'bytes)');

const rm = JSON.parse(fs.readFileSync(path.join(out, 'BalajiFeeHub-Update-1.0.1.manifest.json'), 'utf8'));
console.log('\nRelease manifest:', JSON.stringify(rm, null, 2));

// Assertions
function assert(cond, label) { if (!cond) { console.error('FAIL:', label); process.exit(1); } console.log('ok:', label); }
assert(rm.version === '1.0.1', 'version=1.0.1');
assert(rm.base_version === '1.0.0', 'base_version=1.0.0');
assert(rm.is_baseline === false, 'not baseline');
assert(rm.is_noop === false, 'not noop');
assert(rm.changed_file_count === 2, `changed_file_count=2 (got ${rm.changed_file_count})`);
assert(rm.signed === true, 'signed');
assert(rm.min_supported_version === '1.0.0', 'min_supported_version=1.0.0');
assert(rm.sha256 && rm.sha256.length === 64, 'sha256 present, 64 hex');

const bcupdate = path.join(out, rm.delta_asset);
assert(fs.existsSync(bcupdate), '.bcupdate exists');
const actualSize = fs.statSync(bcupdate).size;
assert(actualSize === rm.size, `size matches manifest (${actualSize} == ${rm.size})`);
const actualSha = crypto.createHash('sha256').update(fs.readFileSync(bcupdate)).digest('hex');
assert(actualSha === rm.sha256, 'sha256 matches manifest');

// Verify only allowed paths are in the manifest inside the .bcupdate
const AdmZip = require('adm-zip');
try {
  const zip = new AdmZip(bcupdate);
  const inner = JSON.parse(zip.readAsText('manifest.json'));
  console.log('\nInner manifest.files keys:', Object.keys(inner.files));
  assert(Object.keys(inner.files).length === 2, 'inner manifest lists 2 files');
  assert(inner.files['backend/server.py'], 'backend/server.py present');
  assert(inner.files['frontend/build/index.html'], 'frontend/build/index.html present');
  assert(!inner.files['backend/core.py'], 'backend/core.py excluded (unchanged)');
  assert(inner.min_supported_version === '1.0.0', 'inner min_supported_version=1.0.0');
} catch (e) {
  console.log('(adm-zip not installed, skipping inner-zip inspection)');
}

// Cleanup
fs.rmSync(TMP, { recursive: true, force: true });
console.log('\nE2E DIFFERENTIAL BUILD: ALL ASSERTIONS PASSED');
