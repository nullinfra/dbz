const fs = require('node:fs');
const path = require('node:path');
const { writeJson } = require('./common.cjs');
const { id, newFixture } = require('./fixture.cjs');

const menu = newFixture().menu();
const products = new Map(menu.products.map(product => [product.id, product]));
const categories = new Map(menu.categories.map(category => [category.id, category.name]));
const nameOf = productId => products.get(productId)?.name ?? productId;
const code = value => '`' + (typeof value === 'string' ? value : JSON.stringify(value)) + '`';
const patterns = values => values.map(code).join(', ');
const quote = text => text.split('\n').map(line => line ? '> ' + line : '>').join('\n');
const verdict = passed => passed ? 'PASS' : 'FAIL';
const menuStatus = restored => restored === null ? 'Unavailable' : restored ? 'Matched' : 'Diverged';

function catalogLine({ product_id, variant_id, quantity }) {
  const variant = products.get(product_id)?.variants.find(entry => entry.id === variant_id);
  return quantity + ' × ' + nameOf(product_id) + (variant_id ? ' (' + (variant?.name ?? variant_id) + ')' : '');
}

function toolCalls(calls) {
  return calls.map(({ name, args, ok }) => {
    const fields = args && Object.keys(args).length ? ' ' + code(args) : '';
    return code(name) + fields + (ok ? '' : ' expected to return an error');
  }).join(', ');
}

function expectations(checks) {
  const lines = [];
  if (checks.noOla) lines.push('Reply directly and bypass OlaClick.');
  for (const { intent, status, entities } of checks.operations ?? []) {
    const intents = (Array.isArray(intent) ? intent : [intent]).map(code).join(' or ');
    lines.push('Record ' + intents + ' with status ' + code(status) + (entities ? ' and fields ' + code(entities) : '') + '.');
  }
  if (checks.calls?.length) lines.push('Verify tool calls for ' + toolCalls(checks.calls) + '.');
  if (checks.forbidCalls?.length) lines.push('Avoid tool calls to ' + patterns(checks.forbidCalls) + '.');
  if (checks.forbidIntents?.length) lines.push('Avoid routing to ' + patterns(checks.forbidIntents) + '.');
  lines.push(checks.writes?.length
    ? 'Record exactly these write attempts' + (checks.orderedWrites ? ' in order' : '') + ' — ' + toolCalls(checks.writes) + '.'
    : 'Make zero write attempts.');
  for (const field of ['available', 'unavailable']) {
    if (checks[field]?.length) lines.push('Verify that these products are ' + field + ' — ' + checks[field].map(number => nameOf(id(number))).join(', ') + '.');
  }
  if (checks.offer) lines.push('Save the offer in this order — ' + checks.offer.map(number => nameOf(id(number))).join(', ') + '.');
  if (checks.draft) {
    const { items, missing, service, selections } = checks.draft;
    lines.push('Keep this draft basket — ' + items.map(catalogLine).join(', ') + '.');
    if (missing.length) lines.push('Record these open decisions — ' + patterns(missing) + '.');
    if (service) lines.push('Keep service type ' + code(service) + (missing.length ? '.' : ' and mark the draft ready.'));
    if (selections?.length) lines.push('Keep these choices — ' + selections.join(', ') + '.');
  }
  if (checks.reply?.length) lines.push('Include wording matching each of these patterns — ' + patterns(checks.reply) + '.');
  if (checks.exclude?.length) lines.push('Avoid wording matching these patterns — ' + patterns(checks.exclude) + '.');
  if (checks.question) lines.push('End the reply with a concrete question.');
  for (const { category, number, variant, patch } of checks.menu ?? []) {
    const product = number && products.get(id(number));
    const option = variant && product?.variants.find(entry => entry.id === id(variant));
    const target = category ? categories.get(id(category)) : [product?.name, option?.name].filter(Boolean).join(' / ');
    lines.push('Change only the stated menu fields for ' + target + ' — ' + code(patch) + '.');
  }
  if (!checks.menu?.length) lines.push('Preserve the menu state from the start of this turn.');
  return lines;
}

function messages(result) {
  return result.turns.flatMap((turn, index) => {
    const entries = turn.attempted ? [{
      turn: index + 1, role: result.actor, text: turn.text, received_at: turn.receivedAt,
    }] : [];
    if (turn.reply) entries.push({ turn: index + 1, role: 'assistant', text: turn.reply });
    return entries;
  });
}

function conversation(folder, result, transcript) {
  return [
    '# ' + folder + ' — ' + result.id, '',
    ...transcript.flatMap(({ turn, role, text }) => ['## Turn ' + turn + ' — ' + role, '', quote(text), '']),
  ].join('\n');
}

function failurePatterns(cases) {
  const byArea = new Map();
  for (const { folder, result } of cases) {
    const record = (failures, turn) => {
      for (const { area } of failures) {
        if (!byArea.has(area)) byArea.set(area, { cases: new Set(), turns: new Set() });
        const group = byArea.get(area);
        group.cases.add(folder);
        if (turn) group.turns.add(folder + '/' + turn);
      }
    };
    record(result.failures);
    for (const turn of result.turns) record(turn.failures, turn.name);
  }
  const sorted = [...byArea].sort(([first, a], [second, b]) => b.cases.size - a.cases.size || first.localeCompare(second, 'en'));
  return ['## Patterns of failure', '', ...(sorted.length
    ? ['A test can appear in more than one row.', '',
      '| Pattern | Tests | Affected turns | Where it appeared |', '|---|---:|---:|---|',
      ...sorted.map(([label, group]) => '| ' + label + ' | ' + group.cases.size + ' | ' + group.turns.size + ' | ' +
        [...group.cases].map(folder => '[' + folder + '](#' + folder.toLowerCase() + ')').join(', ') + ' |')]
    : ['Every check passed.']), ''];
}

function report(status, cases, heading) {
  const restored = cases.filter(({ result }) => result.restored === true).length;
  const diverged = cases.filter(({ result }) => result.restored === false).length;
  const menuEdits = cases.filter(({ result }) => result.menuEdits);
  const editRestores = menuEdits.filter(({ result }) => result.restored === true).length;
  return [
    '# OlaClick evaluation report', '', heading, '',
    'Menu baseline before cleanup — ' + restored + ' matched, ' + diverged + ' diverged, ' +
      (cases.length - restored - diverged) + ' unavailable.',
    ...(menuEdits.length ? [editRestores + '/' + menuEdits.length + ' menu-edit tests ended at their starting baseline.'] : []),
    ...(status.error ? ['', '**Execution error**', '', quote(status.error)] : []),
    '', '| Test | Scenario | Actor | Turns | Result | Menu baseline |', '|---|---|---|---:|---|---|',
    ...cases.map(({ folder, result }) => '| [' + folder + '](#' + folder.toLowerCase() + ') | ' + result.id + ' | ' +
      result.actor + ' | ' + result.turns.length + ' | ' + verdict(result.passed) + ' | ' + menuStatus(result.restored) + ' |'),
    ...cases.flatMap(({ folder, result }) => [
      '', '## ' + folder, '',
      '**' + result.id + ' — ' + verdict(result.passed) + '** · ' + result.actor + ' · Menu baseline ' +
        menuStatus(result.restored).toLowerCase() + '. [Conversation](' + folder + '/conversation.md)',
      '', ...result.errors.map(error => '- ' + error),
      ...result.turns.flatMap(turn => [
        '', '### Turn ' + turn.name + ' — ' + (turn.attempted ? verdict(!turn.errors.length) : 'Not run'), '',
        turn.attempted ? '**Sent**' : '**Planned message**', '', quote(turn.text), '',
        '**Reply**', '', turn.reply ? quote(turn.reply) : '_No reply recorded._', '',
        '**Expected**', '', ...expectations(turn.expected).map(line => '- ' + line),
        ...(turn.errors.length ? ['', '**Failed checks**', '', ...turn.errors.map(error => '- ' + error)] : []),
      ]),
    ]),
    '', ...failurePatterns(cases),
  ].join('\n');
}

function publish(destination, status, results) {
  const cases = results.map((result, index) => ({ folder: 'TEST_' + (index + 1), result }));
  const passed = results.filter(result => result.passed).length;
  const totalTurns = results.reduce((total, result) => total + result.turns.length, 0);
  const replies = results.reduce((total, result) => total + result.turns.filter(turn => turn.reply).length, 0);
  const heading = passed + '/' + results.length + ' tests passed. ' + replies + '/' + totalTurns + ' turns returned a reply.';
  const temporary = fs.mkdtempSync(path.join(path.dirname(destination), '.ola_click_eval_report-'));
  try {
    for (const { folder, result } of cases) {
      const directory = path.join(temporary, folder);
      const transcript = messages(result);
      fs.mkdirSync(directory);
      writeJson(path.join(directory, 'summary.json'), {
        test: folder, scenario: result.id, actor: result.actor, tags: result.tags,
        passed: result.passed, menu_edit_expected: result.menuEdits, menu_restored: result.restored,
        cleanup_verified: result.reset, failures: result.failures,
        turns: result.turns.map(turn => ({
          turn: Number(turn.name), attempted: turn.attempted, passed: !turn.errors.length,
          expected: turn.expected, failures: turn.failures,
        })),
      });
      writeJson(path.join(directory, 'message.json'), {
        test: folder, scenario: result.id, actor: result.actor, messages: transcript,
      });
      fs.writeFileSync(path.join(directory, 'conversation.md'), conversation(folder, result, transcript));
    }
    fs.writeFileSync(path.join(temporary, 'eval_report.md'), report(status, cases, heading));
    fs.renameSync(temporary, destination);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
  return { passed, heading };
}

module.exports = { publish };
