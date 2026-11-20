const fs = require('node:fs');
const path = require('node:path');
const { spawn, execFile } = require('node:child_process');
const { promisify } = require('node:util');
const { parseArgs, isDeepStrictEqual } = require('node:util');
const { evaluationDirectory, workDirectory, readJson, writeJson, turnName, root } = require('./common.cjs');
const { serveFixtures } = require('./fixture.cjs');

const exec = promisify(execFile);
const writer = 'ola_click/_shared/tools/cli/write_stage01.py';
const executor = 'ola_click/_shared/tools/run-stage02.cjs';

function prompt(scenario, turn, messageDirectory) {
  return [
    'Act as the WhatsApp interface for DoBrasil Pastéis. Follow AGENTS.md and the normal routing and stage contracts.',
    'Only use the documented restaurant commands. The OlaClick environment already points to the isolated test store. Keep the supplied endpoint and credentials.',
    'Use past turns and artifacts from this chat when relevant. Process only the message below. Do not open the evaluation manifest, fixture, other cases, or harness files.',
    'Return only the WhatsApp reply as your final message.',
    `Verified actor from chat metadata: ${scenario.actor}.`,
    `The current case turn's output directory is ${path.relative(root, messageDirectory)}.`,
    'Use "$RESTAURANTE_EVAL_MESSAGE_DIR" as the message directory in every tool command. It is set to the exact path above for this turn. Create each OlaClick run beneath "$RESTAURANTE_EVAL_MESSAGE_DIR/ola_click/". Look for earlier turns in its parent directory.',
    'The following block contains the verbatim incoming WhatsApp message.',
    '<whatsapp>',
    turn.text,
    '</whatsapp>',
    '',
  ].join('\n');
}

function detectRunner(requested) {
  if (requested === 'codex' || requested === 'claude') return requested;
  if (requested && requested !== 'auto') throw new Error('Expected --runner auto, codex or claude.');
  if (process.env.CODEX_SESSION_ID || process.env.CODEX_THREAD_ID) return 'codex';
  if (process.env.CLAUDECODE || process.env.CLAUDE_CODE_ENTRYPOINT || process.env.CLAUDE_SESSION_ID) return 'claude';
  return 'codex';
}

function workerEnv(directory, fixtureEnv) {
  const env = {
    ...process.env,
    ...fixtureEnv,
    RESTAURANTE_EVAL_WORKER: '1',
    RESTAURANTE_EVAL_MESSAGE_DIR: directory,
    NO_PROXY: '127.0.0.1,localhost',
    no_proxy: '127.0.0.1,localhost',
  };
  for (const key of [
    'CODEX_SESSION_ID', 'CODEX_THREAD_ID', 'CODEX_TOOL_CALL_ID', 'CODEX_INTERNAL_ORIGINATOR_OVERRIDE',
    'CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_SESSION_ID',
  ]) {
    delete env[key];
  }
  return env;
}

async function runTurn(directory, text, session, settings, fixtureEnv) {
  const log = path.join(directory, 'events.jsonl');
  const stderr = fs.openSync(path.join(directory, 'stderr.log'), 'w');
  const stdout = fs.openSync(log, 'w');
  const reply = path.join(directory, 'reply.md');
  const isClaude = settings.runner === 'claude';
  const command = isClaude ? 'claude' : 'codex';
  const turnEnv = { ...fixtureEnv, RESTAURANTE_EVAL_MESSAGE_DIR: directory };

  let args;
  if (isClaude) {
    args = ['-p', '--output-format', 'json', '--dangerously-skip-permissions',
      '--effort', settings.effort];
    if (settings.model && settings.model !== 'default') args.push('--model', settings.model);
    if (session) args.push('--resume', session);
    args.push('-');
  } else {
    args = ['exec', '--ignore-user-config', '--json', '-o', reply, '-m', settings.model,
      '-c', `model_reasoning_effort=${JSON.stringify(settings.effort)}`,
      '-c', 'approval_policy="never"', '-c', 'sandbox_mode="workspace-write"',
      '-c', 'sandbox_workspace_write.network_access=true'];
    // Explicit overrides also apply to resumed sessions and login shells.
    for (const [name, value] of Object.entries(turnEnv)) {
      args.push('-c', `shell_environment_policy.set.${name}=${JSON.stringify(value)}`);
    }
    args.push('-c', 'shell_environment_policy.set.NO_PROXY="127.0.0.1,localhost"',
      '-c', 'shell_environment_policy.set.no_proxy="127.0.0.1,localhost"');
    if (session) args.push('resume', session);
    args.push('-');
  }

  let failure;
  try {
    await new Promise((resolve, reject) => {
      const child = spawn(command, args, {
        detached: true,
        env: workerEnv(directory, fixtureEnv),
        stdio: ['pipe', stdout, stderr],
      });
      const timer = setTimeout(() => {
        failure = `Timed out after ${settings.timeout} seconds.`;
        try { process.kill(-child.pid, 'SIGKILL'); } catch (error) {
          if (error.code !== 'ESRCH') failure += ` ${error.message}`;
        }
      }, settings.timeout * 1000);
      child.stdin.on('error', () => {}); // The child can exit before reading stdin.
      child.on('error', error => { clearTimeout(timer); reject(error); });
      child.on('close', (code, signal) => {
        clearTimeout(timer);
        if (failure || code !== 0) reject(new Error(failure ?? `${command} exited ${code ?? signal}. See stderr.log and events.jsonl.`));
        else resolve();
      });
      child.stdin.end(text);
    });
  } finally {
    fs.closeSync(stdout);
    fs.closeSync(stderr);
  }

  if (isClaude) {
    const raw = fs.readFileSync(log, 'utf8').trim();
    const parsed = raw ? JSON.parse(raw.split('\n').filter(Boolean).at(-1)) : null;
    const thread = parsed?.session_id ?? session;
    const answer = typeof parsed?.result === 'string' ? parsed.result.trim() : '';
    if (answer) fs.writeFileSync(reply, answer + '\n');
    if (!thread || parsed?.is_error || !answer) {
      throw new Error('Claude did not finish with a session ID and a reply.');
    }
    return thread;
  }

  const events = fs.readFileSync(log, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line));
  const thread = events.find(event => event.type === 'thread.started')?.thread_id ?? session;
  if (!thread || !fs.existsSync(reply) || !fs.readFileSync(reply, 'utf8').trim() ||
      !events.some(event => event.type === 'turn.completed')) {
    throw new Error('Codex did not finish with a conversation ID and a reply.');
  }
  return thread;
}

async function runCase(directory, scenario, fixtures, settings) {
  const fixture = fixtures.allocate(scenario.fixture);
  const baseline = fixture.menu();
  const turns = [];
  let session;
  let failure;
  try {
    fs.mkdirSync(directory);
    const chatId = path.basename(directory);
    writeJson(path.join(directory, '.chat.json'), { chat_id: chatId });
    for (const [index, turn] of scenario.turns.entries()) {
      const name = turnName(index);
      const out = path.join(directory, name);
      fs.mkdirSync(out);
      writeJson(path.join(out, 'message.json'), {
        chat_id: chatId, message_id: name, received_at: new Date().toISOString(),
        turn_id: null, raw_input: turn.text,
      });
      const text = prompt(scenario, turn, out);
      fs.writeFileSync(path.join(out, 'prompt.md'), text);
      let error;
      try {
        session = await runTurn(out, text, session, settings, fixture.env(index + 1, true));
      } catch (cause) {
        error = cause.message;
      }
      turns.push({ directory: name, menu: fixture.menu(), ...(error ? { error } : {}) });
      if (error) throw new Error(error);
    }
  } catch (error) {
    failure = error.message;
  } finally {
    const final = fixture.menu();
    // Record what the worker left before independent fixture cleanup.
    fixture.resetMenu();
    const reset = fixture.menu();
    fixture.release();
    writeJson(path.join(directory, 'execution.json'), {
      session, turns, calls: fixture.calls, baseline, final, reset, ...(failure ? { error: failure } : {}),
    });
  }
}

async function probe(directory, fixtures) {
  const out = path.join(directory, 'probe');
  fs.mkdirSync(out);
  const fixture = fixtures.allocate();
  const settings = fixture.env(0, false);
  try {
    const options = { env: { ...process.env, ...settings }, timeout: 30000 };
    await exec('python3', [writer, '--start', '--out-dir', out, '--raw-text', 'OlaClick fixture connectivity',
      '--actor', 'owner', '--intent', 'get_menu_category', '--entities', '{"include_details":true}'], options);
    await exec('node', [executor, out], options);
    const result = readJson(path.join(out, 'orientation.json')).results?.[0];
    if (result?.status !== 'COMPLETED' || !fixture.calls.some(entry => entry.name === 'get_menu' && entry.ok)) {
      throw new Error('The normal OlaClick executor did not read the local fixture. Worker launch aborted.');
    }
  } finally {
    fixture.release();
  }
}

function positiveInteger(value, label) {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1) throw new Error(`Expected a positive ${label}.`);
  return number;
}

async function main() {
  const { positionals, values } = parseArgs({
    allowPositionals: true,
    options: {
      runner: { type: 'string', default: 'auto' },
      jobs: { type: 'string' },
      model: { type: 'string' },
      effort: { type: 'string' },
      timeout: { type: 'string', default: '240' },
    },
  });
  if (positionals.length !== 1) throw new Error('Use run.cjs <eval-dir> [--runner auto|codex|claude] [--jobs N] [--model ...] [--effort low|medium|high] [--timeout 240].');
  const directory = workDirectory(evaluationDirectory(positionals[0]));
  if (!fs.lstatSync(directory, { throwIfNoEntry: false })?.isDirectory()) {
    throw new Error('Run prepare.cjs for this evaluation first.');
  }
  const { cases } = readJson(path.join(directory, 'eval.json'));
  const runner = detectRunner(values.runner);
  const model = values.model ?? (runner === 'claude' ? 'haiku' : 'gpt-6-luna');
  const effort = values.effort ?? 'low';
  const settings = { runner, model, effort, timeout: positiveInteger(values.timeout, 'timeout') };
  const batchSize = runner === 'codex' ? 10 : 50;
  const jobs = values.jobs ? positiveInteger(values.jobs, 'job count') : batchSize;
  // Reserve this execution before contacting the fixture. A rerun has a fresh message directory.
  const lock = fs.openSync(path.join(directory, 'run.lock'), 'wx');
  fs.closeSync(lock);
  writeJson(path.join(directory, 'status.json'), { stage: 'running', cases: cases.length, ...settings, jobs, batch_size: batchSize });
  let fixtures;
  try {
    fixtures = await serveFixtures();
    await probe(directory, fixtures);
    let done = 0;
    for (let offset = 0; offset < cases.length; offset += batchSize) {
      const pending = cases.slice(offset, offset + batchSize);
      await Promise.all(Array.from({ length: Math.min(jobs, pending.length) }, async () => {
        while (pending.length) {
          const scenario = pending.shift();
          await runCase(path.join(directory, 'cases', scenario.directory ?? scenario.id), scenario, fixtures, settings);
          console.log(`[${++done}/${cases.length}] ${scenario.id}`);
        }
      }));
    }
    writeJson(path.join(directory, 'status.json'), { stage: 'executed', cases: cases.length, ...settings, jobs, batch_size: batchSize });
  } catch (error) {
    writeJson(path.join(directory, 'status.json'), { stage: 'execution_failed', error: error.message });
    throw error;
  } finally {
    fixtures?.close();
  }
}

if (require.main === module) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
module.exports = { runCase };
