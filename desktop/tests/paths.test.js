/**
 * paths.test.js — defensive path validation tests.
 * Run:  node desktop/tests/paths.test.js
 */
const { isSafeRelative } = require('../updater/paths');

let pass = 0, fail = 0;
function assert(cond, label) {
  if (cond) { pass++; console.log('  ok:', label); }
  else { fail++; console.error('  FAIL:', label); }
}

console.log('\npath-safety tests\n-----------------');

// SAFE paths
assert(isSafeRelative('backend/core.py') === true, 'safe: backend/core.py');
assert(isSafeRelative('frontend/build/index.html') === true, 'safe: frontend/build/index.html');
assert(isSafeRelative('backend/routers/updates.py') === true, 'safe: nested');
assert(isSafeRelative('frontend\\build\\index.html') === true, 'safe: windows separators tolerated');

// UNSAFE - traversal
assert(isSafeRelative('../etc/passwd') === false, 'unsafe: ../etc/passwd');
assert(isSafeRelative('backend/../../etc/passwd') === false, 'unsafe: nested traversal');
assert(isSafeRelative('..\\Windows\\System32') === false, 'unsafe: windows traversal');
assert(isSafeRelative('./relative/./thing') === false, 'unsafe: leading dot segment');

// UNSAFE - absolute
assert(isSafeRelative('/etc/passwd') === false, 'unsafe: absolute posix');
assert(isSafeRelative('C:\\Windows\\System32') === false, 'unsafe: absolute windows');
assert(isSafeRelative('C:/Windows/System32') === false, 'unsafe: forward-slash absolute windows');
assert(isSafeRelative('D:foo.txt') === false, 'unsafe: drive-relative');

// UNSAFE - UNC
assert(isSafeRelative('\\\\host\\share\\file') === false, 'unsafe: UNC');
assert(isSafeRelative('//host/share/file') === false, 'unsafe: forward-slash UNC');

// UNSAFE - reserved names
assert(isSafeRelative('backend/CON.py') === false, 'unsafe: reserved CON');
assert(isSafeRelative('nul') === false, 'unsafe: reserved NUL bare');
assert(isSafeRelative('COM1.txt') === false, 'unsafe: reserved COM1');
assert(isSafeRelative('backend/lpt3.log') === false, 'unsafe: reserved LPT3 (case-insensitive)');

// UNSAFE - trailing dot / space (Windows)
assert(isSafeRelative('backend/file ') === false, 'unsafe: trailing space');
assert(isSafeRelative('backend/file.') === false, 'unsafe: trailing dot');

// UNSAFE - null / control chars
assert(isSafeRelative('backend/file\x00.py') === false, 'unsafe: null byte');
assert(isSafeRelative('backend/file\n.py') === false, 'unsafe: newline');

// UNSAFE - type
assert(isSafeRelative(null) === false, 'unsafe: null');
assert(isSafeRelative(undefined) === false, 'unsafe: undefined');
assert(isSafeRelative(42) === false, 'unsafe: number');
assert(isSafeRelative('') === false, 'unsafe: empty');

console.log(`\n${pass} passed, ${fail} failed.\n`);
if (fail > 0) process.exit(1);
