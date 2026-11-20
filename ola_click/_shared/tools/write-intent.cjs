const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { parseArgs } = require('node:util');
const { writeJson } = require('./run-stage02.cjs');
const { nonblank, record } = require('./preflight-values.cjs');
const company = require('../../company_users/stages/02_resolve_and_execute/tools/company-operations.cjs');
const clients = require('../../clients/stages/02_resolve_and_execute/tools/client-operations.cjs');
const variants = require('../../menu_manage/stages/02_resolve_and_execute/tools/variant-operations.cjs');

const mcpPipelines = { company_users: company, clients, menu_manage: variants };
const legacyWriter = path.join(__dirname, 'cli', 'write_stage01.py');

function parseEntries(values) {
  if (values.operations !== undefined && values['operations-file'] !== undefined) {
    throw new Error('Supply either --operations or --operations-file.');
  }
  if ((values.operations !== undefined || values['operations-file'] !== undefined) &&
      (values.intent !== undefined || values.entities !== undefined)) {
    throw new Error('Supply either --operations/--operations-file or --intent and --entities.');
  }
  if (values['operations-file'] !== undefined) {
    return JSON.parse(fs.readFileSync(values['operations-file'], 'utf8'));
  }
  if (values.operations !== undefined) {
    return JSON.parse(values.operations);
  }
  return [{ intent: values.intent, entities: JSON.parse(values.entities ?? '{}') }];
}

function main() {
  const { values } = parseArgs({
    options: {
      start: { type: 'boolean', default: false },
      quiet: { type: 'boolean', default: false },
      'out-dir': { type: 'string' },
      'raw-text': { type: 'string' },
      actor: { type: 'string' },
      intent: { type: 'string' },
      entities: { type: 'string' },
      operations: { type: 'string' },
      'operations-file': { type: 'string' },
    },
  });

  const { 'out-dir': directory, 'raw-text': rawText, actor, quiet } = values;
  if (!directory || !nonblank(rawText) || !['owner', 'customer', 'unknown'].includes(actor)) {
    throw new Error('Supply --out-dir, --raw-text and --actor (owner, customer or unknown).');
  }

  const entries = parseEntries(values);
  if (!Array.isArray(entries) || !entries.length) {
    throw new Error('Supply at least one operation.');
  }

  const isMcp = entries.map(entry =>
    Object.keys(mcpPipelines).find(name => mcpPipelines[name].tools.has(entry?.intent)),
  );
  const anyMcp = isMcp.some(Boolean);
  const allMcp = isMcp.every(Boolean);

  if (anyMcp && !allMcp) {
    throw new Error('Direct MCP intents require a separate run from legacy OlaClick intents.');
  }

  if (allMcp) {
    const operations = entries.map((entry, index) => {
      if (!record(entry) || !record(entry.entities)) {
        throw new Error('Each intent needs a JSON entity object.');
      }
      return { intent: entry.intent, pipeline: isMcp[index], entities: entry.entities };
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
    return;
  }

  const args = [legacyWriter, '--start', '--out-dir', directory, '--raw-text', rawText, '--actor', actor];
  if (values['operations-file'] !== undefined) args.push('--operations-file', values['operations-file']);
  else if (values.operations !== undefined) args.push('--operations', values.operations);
  else args.push('--intent', values.intent ?? '', '--entities', values.entities ?? '{}');

  const result = spawnSync('python3', args, {
    encoding: 'utf8',
    stdio: ['inherit', quiet ? 'pipe' : 'inherit', 'inherit'],
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    return;
  }
  if (quiet) {
    console.log(path.join(directory, 'stage01_intent.json'));
  }
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
