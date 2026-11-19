const fs = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { writeJson } = require('../../../../_shared/tools/run-stage02.cjs');
const { nonblank, record } = require('../../../../_shared/tools/preflight-values.cjs');
const { intents } = require('../../02_resolve_and_execute/tools/company-operations.cjs');

try {
  const { values } = parseArgs({ options: {
    'out-dir': { type: 'string' },
    'raw-text': { type: 'string' },
    actor: { type: 'string' },
    intent: { type: 'string' },
    entities: { type: 'string' },
    operations: { type: 'string' },
  } });
  const { 'out-dir': directory, 'raw-text': rawText, actor } = values;
  if (!directory || !nonblank(rawText) || !['owner', 'customer', 'unknown'].includes(actor)) {
    throw new Error('Supply --out-dir, --raw-text and --actor (owner, customer or unknown).');
  }
  if (values.operations && (values.intent || values.entities)) {
    throw new Error('Supply either --operations or --intent and --entities.');
  }
  const entries = values.operations ? JSON.parse(values.operations) :
    [{ intent: values.intent, entities: JSON.parse(values.entities ?? '{}') }];
  if (!Array.isArray(entries) || !entries.length || entries.some(entry => !intents.has(entry?.intent) || !record(entry.entities))) {
    throw new Error('Use a Company & Users intent with a JSON entity object.');
  }
  const operations = entries.map(({ intent, entities }) => ({ intent, entities, pipeline: 'company_users' }));
  const filename = 'stage01_intent.json';
  fs.mkdirSync(directory, { recursive: true });
  writeJson(directory, filename, {
    run_id: path.basename(path.resolve(directory)),
    raw_text: rawText,
    actor,
    is_olaclick_action: true,
    ...operations[0],
    active_pipelines: ['company_users'],
    operations,
  });
  console.log(path.join(directory, filename));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
