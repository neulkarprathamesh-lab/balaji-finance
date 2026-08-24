/**
 * updater-auth.test.js - plain-node assertions, no test framework.
 * Runs with:  node desktop/tests/updater-auth.test.js
 * Exits non-zero on any failure.
 *
 * Proves the admin-login path the "Check for Updates" button relies on
 * (updater.js postLogin -> parseAuthResponse -> isAdminUser) correctly
 * handles the EXACT response shapes backend/routers/auth.py's
 * POST /api/auth/login actually produces:
 *   - success:            200 {"token": "...", "user": {..., "role": "administrator"}}
 *   - wrong credentials:  401 {"detail": "Invalid email or password"}
 *   - disabled account:   403 {"detail": "Account disabled"}
 *   - pydantic validation errors (malformed email etc.): 422 with a LIST
 *     detail (not a string) - must not crash, must fall back gracefully.
 *   - malformed/non-JSON body - must not throw.
 */
const { parseAuthResponse, isAdminUser, parseSha256Sums } = require('../updater/auth-utils');

let pass = 0, fail = 0;
function eq(actual, expected, label) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) { pass++; console.log('  ok:', label); }
  else { fail++; console.error(`  FAIL: ${label} (expected ${e}, got ${a})`); }
}
function ok(cond, label) {
  if (cond) { pass++; console.log('  ok:', label); }
  else { fail++; console.error(`  FAIL: ${label}`); }
}

console.log('\nupdater admin-login auth tests');
console.log('-------------------------------');

// --- parseAuthResponse: success path, matches auth.py's real response shape ---
{
  const body = JSON.stringify({
    token: 'eyJhbGciOi...',
    user: { id: 'u1', email: 'admin@balajiconvent.in', name: 'Administrator', role: 'administrator', active: true },
  });
  const r = parseAuthResponse(200, body);
  ok(r.ok === true, 'admin login: 200 + token/user -> ok:true');
  eq(r.token, 'eyJhbGciOi...', 'admin login: token extracted');
  ok(isAdminUser(r.user), 'admin login: role administrator recognized');
}

// --- non-admin account should still parse fine (auth is separate from role-check) ---
{
  const body = JSON.stringify({ token: 't2', user: { role: 'cashier' } });
  const r = parseAuthResponse(200, body);
  ok(r.ok === true, 'cashier login: still parses ok (transport-level)');
  ok(!isAdminUser(r.user), 'cashier login: correctly rejected by isAdminUser (role check)');
}

// --- wrong credentials: exact string auth.py raises today ---
{
  const r = parseAuthResponse(401, JSON.stringify({ detail: 'Invalid email or password' }));
  ok(r.ok === false, 'wrong credentials: ok:false');
  eq(r.error, 'Invalid email or password', 'wrong credentials: exact backend message surfaced');
}

// --- disabled account ---
{
  const r = parseAuthResponse(403, JSON.stringify({ detail: 'Account disabled' }));
  ok(r.ok === false, 'disabled account: ok:false');
  eq(r.error, 'Account disabled', 'disabled account: exact backend message surfaced');
}

// --- pydantic validation error: detail is a LIST, not a string - must not crash ---
{
  const body = JSON.stringify({ detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error' }] });
  const r = parseAuthResponse(422, body);
  ok(r.ok === false, 'validation error (non-string detail): ok:false, does not throw');
  eq(r.error, 'HTTP 422', 'validation error: falls back to HTTP code when detail is not a string');
}

// --- malformed JSON body must not throw ---
{
  let threw = false;
  let r;
  try { r = parseAuthResponse(200, '{not json'); } catch (_) { threw = true; }
  ok(!threw, 'malformed JSON body: does not throw');
  ok(r && r.ok === false, 'malformed JSON body: ok:false');
}

// --- missing token/user on a 200 must be treated as failure, not a crash ---
{
  const r = parseAuthResponse(200, JSON.stringify({ unexpected: 'shape' }));
  ok(r.ok === false, '200 with missing token/user: ok:false');
}

// --- isAdminUser edge cases ---
{
  ok(!isAdminUser(null), 'isAdminUser(null) -> false');
  ok(!isAdminUser(undefined), 'isAdminUser(undefined) -> false');
  ok(!isAdminUser({}), 'isAdminUser({}) -> false');
  ok(!isAdminUser({ role: 'manager' }), 'isAdminUser(manager) -> false');
  ok(isAdminUser({ role: 'administrator' }), 'isAdminUser(administrator) -> true');
}

// --- parseSha256Sums: matches the exact format install workflow writes ---
// "{0}  {1}    ({2:N0} bytes)" -f $h,$e,$s
{
  const sums = [
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  BalajiFeeHub-Server-Setup.exe    (123,456,789 bytes)',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  BalajiFeeHub-Client-Setup.exe    (98,765,432 bytes)',
  ].join('\n');
  eq(parseSha256Sums(sums, 'BalajiFeeHub-Server-Setup.exe'), 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'parseSha256Sums: finds server exe hash');
  eq(parseSha256Sums(sums, 'BalajiFeeHub-Client-Setup.exe'), 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'parseSha256Sums: finds client exe hash');
  eq(parseSha256Sums(sums, 'DoesNotExist.exe'), null, 'parseSha256Sums: missing filename -> null');
  eq(parseSha256Sums('', 'anything'), null, 'parseSha256Sums: empty text -> null');
}

console.log(`\n${pass} passed, ${fail} failed.\n`);
process.exit(fail > 0 ? 1 : 0);
