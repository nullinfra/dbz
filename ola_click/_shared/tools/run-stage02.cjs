const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { record } = require('./preflight-values.cjs');
const { inspectDraft } = require('../../order_create/stages/02_resolve_and_execute/tools/check-draft.cjs');
const company = require('../../company_users/stages/02_resolve_and_execute/tools/company-operations.cjs');

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

function emit(directory, intent, results) {
  const result = orientation(intent, results);
  writeJson(directory, 'orientation.json', result);
  console.log(JSON.stringify(result, null, 2));
}

async function main() {
  const directory = process.argv[2];
  if (!directory) throw new Error('Usage: run-stage02.cjs <run-directory>');
  const intent = JSON.parse(fs.readFileSync(path.join(directory, 'stage01_intent.json'), 'utf8'));
  const operations = intent.operations ?? [intent];
  if (!Array.isArray(operations) || !operations.length || operations.some(operation => !record(operation?.entities))) {
    throw new Error('Stage 01 must contain checked operations with entity objects.');
  }
  const usesCompany = operations.some(operation => operation.pipeline === 'company_users');
  if (usesCompany && operations.some(operation => operation.pipeline !== 'company_users')) {
    throw new Error('Company & Users requires a separate run from the legacy executor.');
  }
  const checkedModules = new Set(['menu_read', 'menu_manage', 'order_modify', 'promotions', 'logistics_delivery', 'backoffice_ops']);
  const checks = new Map([['company_users', company.check]]);
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
    checks.get(operation.pipeline)?.(operation, add, intent.actor);
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
    }));
    return;
  }
  if (usesCompany) {
    const results = await company.execute(operations);
    emit(directory, intent, results);
    if (results.some(result => result.status === 'API_ERROR')) process.exitCode = 1;
    return;
  }
  const commands = intent.active_pipelines?.length ? ['olaclick_mcp.py', 'write_stage02.py'] : ['write_stage02.py'];
  for (const command of commands) {
    const result = spawnSync('python3', [path.join(__dirname, 'cli', command), '--out-dir', directory], { stdio: 'inherit' });
    if (result.error) throw result.error;
    if (result.status !== 0) {
      process.exitCode = result.status ?? 1;
      return;
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
