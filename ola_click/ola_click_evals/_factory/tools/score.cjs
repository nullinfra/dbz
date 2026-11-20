const fs = require('node:fs');
const path = require('node:path');
const { isDeepStrictEqual, parseArgs } = require('node:util');
const { evaluationDirectory, workDirectory, readJson, turnName } = require('./common.cjs');
const { applyMenuEdits } = require('./prepare.cjs');
const { id } = require('./fixture.cjs');
const { publish } = require('./report.cjs');

const optionalJson = file => fs.existsSync(file) ? readJson(file) : null;
const menuSnapshot = value => Array.isArray(value?.categories) && Array.isArray(value?.products);
const replyAt = directory => {
  const file = path.join(directory, 'reply.md');
  return fs.existsSync(file) ? fs.readFileSync(file, 'utf8').trim() : '';
};

function subset(value, expected) {
  if (Array.isArray(expected)) {
    return Array.isArray(value) && exactMatching(value, expected);
  }
  if (expected && typeof expected === 'object') {
    return value != null && Object.entries(expected).every(([key, field]) => subset(value[key], field));
  }
  return value === expected;
}

function exactMatching(actual, expected) {
  if (actual.length !== expected.length) return false;
  const remaining = [...actual];
  for (const entry of expected) {
    const index = remaining.findIndex(candidate => subset(candidate, entry));
    if (index < 0) return false;
    remaining.splice(index, 1);
  }
  return true;
}

function artifacts(directory) {
  const output = path.join(directory, 'ola_click');
  const runs = fs.existsSync(output) ? fs.readdirSync(output, { withFileTypes: true }).filter(item => item.isDirectory()) : [];
  return runs.sort((first, second) => first.name.localeCompare(second.name, 'en', { numeric: true })).map(run => {
    const dir = path.join(output, run.name);
    return {
      intent: optionalJson(path.join(dir, 'stage01_intent.json')),
      orientation: optionalJson(path.join(dir, 'orientation.json')),
      readiness: optionalJson(path.join(dir, 'draft_readiness.json')),
      offer: optionalJson(path.join(dir, 'menu_offer.json')),
    };
  });
}

function scoreTurn(directory, scenario, turn, index, execution, expectedMenu, rawInput) {
  const name = turnName(index);
  const turnPath = path.join(directory, name);
  const { checks, text } = turn;
  const runs = artifacts(turnPath);
  const results = runs.flatMap(run => run.orientation?.results ?? []);
  const intents = runs.flatMap(run => run.intent?.operations ?? (run.intent ? [run.intent] : []));
  const reply = replyAt(turnPath);
  const calls = execution?.calls?.filter(entry => entry.turn === index + 1) ?? [];
  const writes = calls.filter(entry => entry.write);
  const actual = execution?.turns?.[index];
  const errors = [];
  const failures = [];
  const require = (condition, area, message) => {
    if (condition) return;
    errors.push(message);
    failures.push({ area, message });
  };

  require(actual && !actual.error && reply, 'Turn execution', actual?.error ?? 'Turn did not finish with a reply.');
  require(rawInput === text, 'Turn execution', 'The recorded input differs from the scenario message.');
  require(runs.every(run => run.intent?.actor === scenario.actor && run.intent?.raw_text === text), 'Routing and orientation',
    'Stage 01 must preserve the verified actor and verbatim message.');
  require(!checks.noOla || (!runs.length && !calls.length), 'Routing and orientation', 'This turn should bypass OlaClick.');
  require(!checks.calls?.length || results.length, 'Routing and orientation', 'Missing the OlaClick orientation in this turn directory.');
  require(!results.some(result => result.status === 'API_ERROR') || checks.operations?.some(entry => entry.status === 'API_ERROR'),
    'Tool calls and verification', 'Unexpected API_ERROR in orientation.');
  for (const { intent, status, entities } of checks.operations ?? []) {
    const allowed = Array.isArray(intent) ? intent : [intent];
    require(results.some(result => allowed.includes(result.intent) && result.status === status &&
      (!entities || subset(result.entities, entities))), 'Routing and orientation', `Missing ${allowed.join('/')} orientation with ${status}.`);
  }
  for (const intent of checks.forbidIntents ?? []) {
    require(!intents.some(entry => entry.intent === intent), 'Routing and orientation', `Unexpected intent ${intent}.`);
  }
  for (const expected of checks.calls ?? []) {
    require(calls.some(entry => subset(entry, expected)), 'Tool calls and verification',
      `Missing verified MCP call ${expected.name} ${JSON.stringify(expected.args ?? {})}.`);
  }
  if (checks.orderedCalls) {
    let cursor = -1;
    for (const expected of checks.orderedCalls) {
      const next = calls.findIndex((entry, idx) => idx > cursor && subset(entry, expected));
      require(next > cursor, 'Tool calls and verification', `MCP call ${expected.name} was missing or out of sequence.`);
      cursor = next;
    }
  }
  for (const forbidden of checks.forbidCalls ?? []) {
    require(!calls.some(entry => entry.name === forbidden), 'Tool calls and verification', `Unexpected MCP call ${forbidden}.`);
  }
  require(!calls.some(entry => entry.error?.startsWith('fixture_')), 'Tool calls and verification',
    'An MCP call was unsupported by the fixture or addressed a missing record.');
  require(exactMatching(writes, checks.writes ?? []), 'Writes and checkout', `MCP writes differed. Expected ${JSON.stringify(checks.writes ?? [])}.`);
  if (checks.strictWrites && checks.writes?.length) {
    require(writes.every((entry, offset) => isDeepStrictEqual(entry.args ?? {}, checks.writes[offset]?.args ?? {})),
      'Writes and checkout', 'MCP write arguments included unexpected extra fields.');
  }
  if (checks.orderedWrites) {
    require(writes.every((entry, offset) => entry.name === checks.writes?.[offset]?.name), 'Writes and checkout', 'MCP writes were out of sequence.');
  }
  for (const [field, value] of [['available', true], ['unavailable', false]]) {
    for (const product of checks[field] ?? []) {
      require(results.some(result => result.status === 'COMPLETED' && result.pipeline === 'menu_read' &&
        result.mcp_result?.menu_matches?.some(match => match.id === id(product) && match.available === value)),
      'Catalog and offers', `Missing verified ${field} product ${product}.`);
    }
  }
  if (checks.offer) {
    require(runs.some(run => isDeepStrictEqual(run.offer?.products?.map(product => product.id), checks.offer.map(id))),
      'Catalog and offers', 'Missing the saved menu offer in the requested order.');
  }
  if (checks.draft) {
    const run = runs.filter(entry => (entry.intent?.operations ?? []).some(op => op.intent === 'create_order')).at(-1);
    const draft = run?.intent.operations.find(op => op.intent === 'create_order')?.entities;
    const missing = run?.readiness?.missing?.map(entry => entry.field);
    require(draft && exactMatching(draft.items ?? [], checks.draft.items), 'Order drafts', 'Draft does not have the expected product IDs, variants and quantities.');
    require(missing && checks.draft.missing.every(field => missing.includes(field)), 'Order drafts', 'Missing or incorrect draft-readiness evidence.');
    if (checks.draft.exactMissing) {
      require(missing && isDeepStrictEqual([...new Set(missing)].sort(), [...new Set(checks.draft.missing)].sort()),
        'Order drafts', 'Draft reported unexpected missing fields.');
    }
    if (checks.draft.service) require(draft?.service_type === checks.draft.service, 'Order drafts', 'Draft service type differs.');
    if (checks.draft.service && !checks.draft.missing.length) {
      require(run?.readiness?.status === 'READY', 'Order drafts', 'The fully specified draft should be ready.');
    }
    if (checks.draft.selections) {
      const names = draft?.items?.flatMap(item => item.catalog_review?.groups?.flatMap(group =>
        group.selections?.map(selection => selection.name?.toLowerCase()) ?? []) ?? []) ?? [];
      require(checks.draft.selections.every(selected => names.some(name => name?.includes(selected.toLowerCase()))),
        'Order drafts', 'Draft lost a previously confirmed menu choice.');
    }
  }
  for (const pattern of checks.reply ?? []) require(new RegExp(pattern, 'iu').test(reply), 'Reply content', `Reply is missing /${pattern}/.`);
  for (const pattern of checks.exclude ?? []) require(!new RegExp(pattern, 'iu').test(reply), 'Reply content', `Reply matched forbidden /${pattern}/.`);
  if (reply) {
    require(!/(orientation\.json|stage01_intent|draft_readiness|olaclick_mcp|[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})/i.test(reply),
      'Reply content', 'Reply leaked internal artifacts or raw UUIDs.');
  }
  if (checks.question) require(/\?[\s\p{Emoji_Presentation}\p{Extended_Pictographic}\uFE0F\u200D]*$/u.test(reply), 'Reply content', 'Reply must end with a concrete question.');
  if (actual) require(isDeepStrictEqual(actual.menu, expectedMenu), 'Menu state and restoration', 'Full menu differs from the expected state after this turn.');
  for (const result of results) {
    if (result.intent !== 'create_order' || result.status !== 'COMPLETED') continue;
    require(writes.some(call => call.name === 'create_order' && call.ok), 'Writes and checkout', 'Order marked complete without a successful creation.');
  }
  return { reply, failures, errors };
}

function scoreCase(scenario, directory) {
  const execution = optionalJson(path.join(directory, 'execution.json'));
  const baseline = execution?.baseline;
  const expected = menuSnapshot(baseline) ? structuredClone(baseline) : null;
  const turns = scenario.turns.map((turn, index) => {
    if (expected) applyMenuEdits(expected, turn.checks.menu);
    const name = turnName(index);
    const turnPath = path.join(directory, name);
    const attempted = fs.existsSync(path.join(turnPath, 'message.json'));
    const metadata = { name, text: turn.text, expected: turn.checks, attempted };
    if (!attempted) {
      const message = 'This turn was never sent.';
      return { ...metadata, reply: '', errors: [message], failures: [{ area: 'Turn execution', message }] };
    }
    try {
      const input = readJson(path.join(turnPath, 'message.json'));
      return {
        ...metadata, text: typeof input.raw_input === 'string' ? input.raw_input : turn.text,
        receivedAt: input.received_at, ...scoreTurn(directory, scenario, turn, index, execution, expected, input.raw_input),
      };
    } catch (error) {
      const message = `Invalid turn artifact. ${error.message}`;
      return {
        ...metadata, reply: replyAt(turnPath), errors: [message], failures: [{ area: 'Turn execution', message }],
      };
    }
  });
  const errors = [];
  const failures = [];
  const fail = (area, message) => {
    errors.push(message);
    failures.push({ area, message });
  };
  if (!execution || execution.error || execution.turns?.length !== scenario.turns.length) {
    fail('Turn execution', execution?.error ?? 'Case did not complete.');
  }
  const compareMenu = snapshot => menuSnapshot(baseline) && menuSnapshot(snapshot)
    ? isDeepStrictEqual(snapshot, baseline) : null;
  const restored = compareMenu(execution?.final);
  const reset = compareMenu(execution?.reset);
  if (execution && (restored === null || reset === null)) {
    fail('Menu state and restoration', 'The initial, final or post-cleanup menu snapshot is missing.');
  }
  if (restored === false) fail('Menu state and restoration', 'The final menu differs from the baseline before harness cleanup.');
  if (reset === false) fail('Menu state and restoration', 'Harness cleanup could not restore the fixture menu.');
  if (execution?.calls?.some(entry => entry.turn < 1 || entry.turn > scenario.turns.length)) {
    fail('Tool calls and verification', 'Fixture recorded calls outside the conversation.');
  }
  const passed = Boolean(restored && reset && !errors.length && turns.every(turn => !turn.errors.length));
  const menuEdits = scenario.turns.some(turn => turn.checks.menu?.length);
  return {
    id: scenario.id, directory: path.basename(directory), actor: scenario.actor, tags: scenario.tags,
    passed, menuEdits, restored, reset, failures, errors, turns,
  };
}

function main() {
  const { positionals, values } = parseArgs({ allowPositionals: true, options: { from: { type: 'string' } } });
  if (positionals.length !== 1) throw new Error('Use score.cjs <eval-dir> [--from <legacy-eval-dir>].');
  const evaluation = evaluationDirectory(positionals[0]);
  const directory = values.from ? evaluationDirectory(values.from) : workDirectory(evaluation);
  if (fs.existsSync(evaluation)) throw new Error('This message already has a published OlaClick evaluation.');
  if (!fs.lstatSync(directory, { throwIfNoEntry: false })?.isDirectory()) {
    throw new Error('The evaluation working directory is missing.');
  }
  const status = readJson(path.join(directory, 'status.json'));
  if (!['executed', 'execution_failed'].includes(status.stage)) {
    throw new Error('Run the evaluation before publishing its report.');
  }
  const { cases } = readJson(path.join(directory, 'eval.json'));
  const results = cases.map(scenario => scoreCase(scenario, path.join(directory, 'cases', scenario.directory ?? scenario.id)));
  const { passed, heading } = publish(evaluation, status, results);
  if (!values.from) fs.rmSync(directory, { recursive: true });
  console.log(`${heading} Report: ${path.join(evaluation, 'eval_report.md')}`);
  if (passed < results.length) process.exitCode = 1;
}

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = { scoreCase };
