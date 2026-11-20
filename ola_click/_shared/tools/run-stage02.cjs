const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { record } = require('./preflight-values.cjs');
const { execute } = require('./execute-mcp-operations.cjs');
const { inspectDraft } = require('../../order_create/stages/02_resolve_and_execute/tools/check-draft.cjs');
const company = require('../../company_users/stages/02_resolve_and_execute/tools/company-operations.cjs');
const clients = require('../../clients/stages/02_resolve_and_execute/tools/client-operations.cjs');
const variants = require('../../menu_manage/stages/02_resolve_and_execute/tools/variant-operations.cjs');

const mcpAdapters = new Map([['company_users', company], ['clients', clients], ['menu_manage', variants]]);

function adapterFor({ pipeline, intent }) {
  // Earlier Stage 01 artifacts stored client operations under company_users.
  if (pipeline === 'company_users' && clients.tools.has(intent)) return clients;
  const adapter = mcpAdapters.get(pipeline);
  return pipeline === 'menu_manage' && !adapter.tools.has(intent) ? undefined : adapter;
}

function writeJson(directory, filename, data) {
  const target = path.join(directory, filename);
  const temporary = target + '.' + randomUUID() + '.tmp';
  try {
    fs.writeFileSync(temporary, JSON.stringify(data, null, 2) + '\n', { mode: 0o600 });
    fs.renameSync(temporary, target);
  } finally {
    fs.rmSync(temporary, { force: true });
  }
}

function orientation(intent, results) {
  const single = results.length === 1 ? results[0] : {};
  return {
    ...intent,
    ...single,
    confirmed: results.every(result => result.status === 'COMPLETED'),
    needs_clarification: results.some(result => result.needs_clarification),
    confirmation_required: results.some(result => result.confirmation_required),
    results,
  };
}

function summarizeOrientation(directory, data) {
  const compactResult = result => {
    const entry = {
      intent: result.intent,
      pipeline: result.pipeline,
      status: result.status,
      clarification_reason: result.clarification_reason ?? null,
      unsupported_reason: result.unsupported_reason ?? null,
      needs_clarification: Boolean(result.needs_clarification),
      confirmation_required: Boolean(result.confirmation_required),
      suggested_message: result.suggested_message ?? null,
    };
    if (result.preflight_issues?.length) entry.preflight_issues = result.preflight_issues;
    if (result.proposed_action) entry.proposed_action = result.proposed_action;
    if (result.mcp_result) {
      const mcp = { ...result.mcp_result };
      // Avoid echoing duplicate raw API response when structured matches/summary are present.
      if ((mcp.menu_matches || mcp.menu_summary || mcp.sales_summary) && mcp.response) {
        delete mcp.response;
      }
      entry.mcp_result = mcp;
    }
    return entry;
  };
  return {
    run_id: data.run_id,
    orientation_file: path.join(directory, 'orientation.json'),
    status: data.status,
    confirmed: data.confirmed,
    needs_clarification: data.needs_clarification,
    confirmation_required: data.confirmation_required,
    results: (data.results ?? []).map(compactResult),
  };
}

function emit(directory, intent, results, summary = false) {
  const result = orientation(intent, results);
  writeJson(directory, 'orientation.json', result);
  console.log(JSON.stringify(summary ? summarizeOrientation(directory, result) : result, null, 2));
}

async function main() {
  const rawArgs = process.argv.slice(2);
  const summary = rawArgs.includes('--summary') || rawArgs.includes('--quiet');
  const directory = rawArgs.find(arg => !arg.startsWith('--'));
  if (!directory) throw new Error('Usage: run-stage02.cjs [--summary] <run-directory>');
  const intent = JSON.parse(fs.readFileSync(path.join(directory, 'stage01_intent.json'), 'utf8'));
  const operations = intent.operations ?? [intent];
  if (!Array.isArray(operations) || !operations.length || operations.some(operation => !record(operation?.entities))) {
    throw new Error('Stage 01 must contain checked operations with entity objects.');
  }
  const usesMcpAdapters = operations.some(adapterFor);
  if (usesMcpAdapters && !operations.every(adapterFor)) {
    throw new Error('Direct MCP intents require a separate run from the legacy executor.');
  }
  const checkedModules = new Set(['menu_read', 'menu_manage', 'order_modify', 'promotions', 'logistics_delivery', 'backoffice_ops']);
  const checks = new Map();
  for (const { pipeline } of operations) {
    if (checkedModules.has(pipeline) && !checks.has(pipeline)) {
      checks.set(pipeline, require(`../../${pipeline}/stages/02_resolve_and_execute/tools/check-operation.cjs`));
    }
  }

  const draft = inspectDraft(intent);
  if (operations.some(operation => operation.intent === 'create_order')) {
    writeJson(directory, 'draft_readiness.json', draft);
  }
  const reports = operations.map((operation, index) => {
    const issues = [];
    const add = (field, message, status = 'NEEDS_CLARIFICATION', details) =>
      issues.push({ field, message, status, ...details });
    const missing = draft.missing.filter(entry => entry.operation === index + 1);
    if (missing.length) add('draft', 'Ainda faltam escolhas ou detalhes para concluir o pedido.', undefined, { missing });
    const check = adapterFor(operation)?.check ?? checks.get(operation.pipeline);
    check?.(operation, add, intent.actor);
    return { operation: index + 1, intent: operation.intent, pipeline: operation.pipeline, issues };
  });
  const blocked = reports.some(report => report.issues.length);
  writeJson(directory, 'preflight.json', { status: blocked ? 'BLOCKED' : 'READY', operations: reports });
  if (blocked) {
    emit(directory, intent, operations.map((operation, index) => {
      const { issues } = reports[index];
      const status = issues.find(issue => issue.status === 'UNSUPPORTED_OPERATION')?.status ??
        (issues.length ? 'NEEDS_CLARIFICATION' : 'NO_ACTION');
      return {
        ...operation,
        status,
        clarification_reason: status === 'NEEDS_CLARIFICATION' ? 'PREFLIGHT' : null,
        unsupported_reason: status === 'UNSUPPORTED_OPERATION' ? 'PREFLIGHT' : null,
        needs_clarification: status === 'NEEDS_CLARIFICATION',
        confirmation_required: false,
        suggested_message: issues.map(issue => issue.message).join(' ') || null,
        preflight_issues: issues,
        proposed_action: null,
        mcp_result: null,
      };
    }), summary);
    return;
  }
  if (usesMcpAdapters) {
    const results = await execute(operations, adapterFor);
    emit(directory, intent, results, summary);
    if (results.some(result => result.status === 'API_ERROR')) process.exitCode = 1;
    return;
  }
  const commands = intent.active_pipelines?.length ? ['olaclick_mcp.py', 'write_stage02.py'] : ['write_stage02.py'];
  for (const command of commands) {
    const captureSummary = summary && command === 'write_stage02.py';
    const result = spawnSync('python3', [path.join(__dirname, 'cli', command), '--out-dir', directory], {
      encoding: 'utf8',
      stdio: ['inherit', captureSummary ? 'pipe' : 'inherit', 'inherit'],
    });
    if (result.error) throw result.error;
    if (result.status !== 0) {
      if (captureSummary && result.stdout) process.stdout.write(result.stdout);
      process.exitCode = result.status ?? 1;
      return;
    }
  }
  if (summary) {
    const orientationFile = path.join(directory, 'orientation.json');
    if (fs.existsSync(orientationFile)) {
      const data = JSON.parse(fs.readFileSync(orientationFile, 'utf8'));
      console.log(JSON.stringify(summarizeOrientation(directory, data), null, 2));
    }
  }
}

if (require.main === module) {
  main().catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
}

module.exports = { writeJson };
