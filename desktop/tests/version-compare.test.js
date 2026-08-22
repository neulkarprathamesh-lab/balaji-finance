/**
 * version-compare.test.js — plain-node assertions, no test framework.
 * Runs with:  node desktop/tests/version-compare.test.js
 * Exits non-zero on any failure.
 */
const { compare, gt, isUpgrade } = require('../updater/version-compare');

let pass = 0, fail = 0;
function eq(actual, expected, label) {
  if (actual === expected) { pass++; console.log('  ok:', label); }
  else { fail++; console.error(`  FAIL: ${label}  actual=${actual} expected=${expected}`); }
}

console.log('\nversion-compare tests\n---------------------');

// The famous 1.0.9 vs 1.0.10 string-compare bug
eq(compare('1.0.10', '1.0.9'), 1, '1.0.10 > 1.0.9 (numeric compare)');
eq(compare('1.0.9', '1.0.10'), -1, '1.0.9 < 1.0.10');
eq(gt('2.0.0', '1.99.99'), true, '2.0.0 > 1.99.99');
eq(compare('1.0.0', '1.0.0'), 0, 'equal');
eq(compare('v1.2.3', '1.2.3'), 0, 'v-prefix tolerated');

// Prerelease semantics
eq(compare('1.0.0-rc.1', '1.0.0'), -1, '1.0.0-rc.1 < 1.0.0');
eq(compare('1.0.0-alpha.2', '1.0.0-alpha.1'), 1, 'alpha.2 > alpha.1');
eq(compare('1.0.0-alpha', '1.0.0-beta'), -1, 'alpha < beta');
eq(compare('1.0.0-1', '1.0.0-alpha'), -1, 'numeric prerelease id has lower precedence');

// Upgrade semantics + downgrade rejection
eq(isUpgrade('1.0.0', '1.0.1'), true, 'upgrade: 1.0.0 -> 1.0.1');
eq(isUpgrade('1.0.5', '1.0.4'), false, 'reject downgrade 1.0.5 -> 1.0.4');
eq(isUpgrade('1.0.0', '1.0.0'), false, 'no upgrade if equal');
eq(isUpgrade('1.0.9', '1.0.10'), true, 'upgrade: 1.0.9 -> 1.0.10 (NOT string-compare)');
eq(isUpgrade('1.0.0-rc.1', '1.0.0'), true, 'rc.1 -> stable is an upgrade');
eq(isUpgrade('1.0.0', '1.0.0-rc.1'), false, 'stable -> rc.1 is NOT an upgrade');

// Malformed input safety
eq(compare(null, '1.0.0'), -1, 'null treated as 0.0.0');
eq(compare('1.0.0', undefined), 1, 'undefined treated as 0.0.0');
eq(compare('garbage', 'garbage'), 0, 'garbage == garbage (both 0.0.0)');
eq(isUpgrade('', '1.0.1'), true, 'empty installed treated as 0.0.0');

console.log(`\n${pass} passed, ${fail} failed.\n`);
if (fail > 0) process.exit(1);
