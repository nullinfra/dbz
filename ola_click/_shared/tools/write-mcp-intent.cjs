const fs = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { writeJson } = require('./run-stage02.cjs');
const { nonblank, record } = require('./preflight-values.cjs');

function writeIntent(pipelines) {
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
    if (values.operations !== undefined && (values.intent !== undefined || values.entities !== undefined)) {
      throw new Error('Supply either --operations or --intent and --entities.');
    }
    const entries = values.operations === undefined
      ? [{ intent: values.intent, entities: JSON.parse(values.entities ?? '{}') }]
      : JSON.parse(values.operations);
    if (!Array.isArray(entries) || !entries.length) throw new Error('Supply at least one operation.');
    const operations = entries.map(entry => {
      if (!record(entry) || !record(entry.entities)) throw new Error('Each intent needs a JSON entity object.');
      const pipeline = Object.keys(pipelines).find(name => pipelines[name].tools.has(entry.intent));
      if (!pipeline) throw new Error(`Use an intent from ${Object.keys(pipelines).join(' or ')}.`);
      return { intent: entry.intent, pipeline, entities: entry.entities };
    });

    fs.mkdirSync(directory, { recursive: true });
    writeJson(directory, 'stage01_intent.json', {
      run_id: path.basename(path.resolve(directory)),
      raw_text: rawText,
      actor,
      is_olaclick_action: true,
      ...operations[0],
      active_pipelines: [...new Set(operations.map(operation => operation.pipeline))],
      operations,
    });
    console.log(path.join(directory, 'stage01_intent.json'));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

module.exports = { writeIntent };
