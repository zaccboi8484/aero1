// Build-producing unit tests must finish before the final React artifact check.
import {readdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const artifact = 'react_release_artifacts.test.mjs';
const tests = readdirSync('tests').filter(n => (n.endsWith('.test.mjs') || n === 'test_apiGuard.mjs') && n !== artifact).sort();
for (const [command, args] of [
  [process.execPath, ['--test', ...tests.map(n => 'tests/' + n)]],
  [process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build']],
  [process.execPath, ['--test', 'tests/' + artifact]],
]) {
  const result = spawnSync(command, args, {stdio: 'inherit'});
  if (result.error) console.error(result.error.message);
  if (result.status !== 0) process.exit(result.status || 1);
}
