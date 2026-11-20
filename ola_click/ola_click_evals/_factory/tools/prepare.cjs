const fs = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { isDeepStrictEqual } = require('node:util');
const { id, newFixture } = require('./fixture.cjs');
const { evaluationDirectory, workDirectory, writeJson } = require('./common.cjs');
const scenarios = require('../scenarios.cjs');

function applyMenuEdits(menu, edits = []) {
  for (const { category, number, variant, patch } of edits) {
    const item = category
      ? menu.categories.find(entry => entry.id === id(category))
      : menu.products.find(entry => entry.id === id(number));
    const record = variant ? item?.variants.find(entry => entry.id === id(variant)) : item;
    if (!record || Object.keys(patch).some(key => !Object.hasOwn(record, key))) {
      throw new Error('Unknown menu fixture target or field.');
    }
    Object.assign(record, patch);
  }
}

function validate(cases) {
  const ids = new Set();
  const baseline = newFixture().menu();
  for (const scenario of cases) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(scenario.id) || ids.has(scenario.id) ||
        !['customer', 'owner'].includes(scenario.actor) || !scenario.turns.length) {
      throw new Error(`Invalid or duplicate scenario ${scenario.id}.`);
    }
    ids.add(scenario.id);
    const expected = structuredClone(baseline);
    for (const { text, checks } of scenario.turns) {
      if (!text.trim() || !Object.keys(checks).length) throw new Error(`Empty turn in ${scenario.id}.`);
      for (const pattern of [...(checks.reply ?? []), ...(checks.exclude ?? [])]) new RegExp(pattern, 'iu');
      applyMenuEdits(expected, checks.menu);
    }
    if (!isDeepStrictEqual(expected, baseline)) throw new Error(`${scenario.id} does not restore its menu baseline.`);
  }
}

function main() {
  const { positionals, values } = parseArgs({
    allowPositionals: true,
    options: { case: { type: 'string', multiple: true }, list: { type: 'boolean' } },
  });
  validate(scenarios);
  if (values.list) {
    for (const { id, actor, tags, turns } of scenarios) console.log(`${id}\t${actor}\t${turns.length}\t${tags.join(', ')}`);
    return;
  }
  if (positionals.length !== 1) throw new Error('Use prepare.cjs <message-dir> [--case <id>] or --list.');
  const evaluation = evaluationDirectory(positionals[0], true);
  if (fs.existsSync(evaluation)) throw new Error('This message already has a published OlaClick evaluation.');
  const directory = workDirectory(evaluation);
  const requested = new Set(values.case ?? scenarios.map(entry => entry.id));
  const cases = scenarios.filter(entry => requested.delete(entry.id)).map((entry, index) => ({
    ...entry, directory: String(index + 1).padStart(3, '0'),
  }));
  if (requested.size || !cases.length) throw new Error(`Unknown case: ${[...requested].join(', ')}`);
  fs.mkdirSync(directory, { mode: 0o700 });
  fs.mkdirSync(path.join(directory, 'cases'));
  writeJson(path.join(directory, 'eval.json'), { version: 1, cases });
  writeJson(path.join(directory, 'status.json'), { stage: 'prepared', cases: cases.length });
  fs.writeFileSync(path.join(directory, 'check.md'), 'pass\n');
  console.log(evaluation);
}

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = { applyMenuEdits };
