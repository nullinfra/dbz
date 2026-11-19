const fs = require('node:fs');
const path = require('node:path');

function cell(value) {
  return String(value).replace(/[|\r\n]/g, ' ');
}

function duration(start, end) {
  return start == null || end < start ? '—' : `${((end - start) / 1000).toFixed(2)} s`;
}

function report(records, end) {
  const counts = new Map();
  const toolStarts = new Map();
  const tools = [];
  const models = [];
  let pendingModel;
  let pendingModels = 0;

  for (const record of records) {
    const { name, at, toolId } = record;
    counts.set(name, (counts.get(name) || 0) + 1);
    if (name === 'PreToolUse' && toolId) {
      toolStarts.set(toolId, at);
    }
    if (name === 'PostToolUse' || name === 'PostToolUseFailure') {
      tools.push([
        record.tool || 'unknown',
        name === 'PostToolUse' ? 'observed_post' : 'observed_failure',
        duration(toolStarts.get(toolId), at),
        record.exitCode ?? '—',
      ]);
      toolStarts.delete(toolId);
    }
    if (name === 'PreModelRequest') {
      pendingModels += 1;
      pendingModel = pendingModels === 1 ? at : undefined;
    }
    if (name === 'PostModelRequest') {
      models.push([
        record.model || 'unknown',
        duration(pendingModel, at),
        JSON.stringify(record.usage || {}),
      ]);
      pendingModel = undefined;
      pendingModels = Math.max(pendingModels - 1, 0);
    }
  }

  const table = rows => rows.map(row => `| ${row.map(cell).join(' | ')} |`);
  return [
    '# Hook run report', '',
    `- **Status:** ${end.name === 'Interrupt' ? 'interrupted' : 'stopped'}`,
    `- **Elapsed:** ${duration(records[0].at, end.at)}`,
    `- **Events:** ${records.length}`, '',
    '## Event counts', '', '| Event | Count |', '|---|---:|',
    ...table([...counts.entries()].sort()), '',
    '## Tool calls', '', '| Tool | Status | Duration | Exit code |', '|---|---|---:|---:|',
    ...table(tools), '',
    '## Model requests', '', '| Model | Duration | Token usage |', '|---|---:|---|',
    ...table(models), '',
    '> Recorded timing includes hook overhead.', '',
  ].join('\n');
}

function appendObservation(directory, event) {
  const events = path.join(directory, '.events.jsonl');
  const name = event.hook_event_name;
  const record = {
    name,
    at: Number(process.hrtime.bigint() / 1000000n),
    tool: event.tool_name,
    toolId: event.tool_use_id,
    exitCode: event.tool_response?.exit_code ?? event.tool_response?.exitCode,
    model: event.model,
    usage: event.token_usage,
  };
  fs.appendFileSync(events, JSON.stringify(record) + '\n');
  if (name === 'Stop' || name === 'Interrupt') {
    const records = fs.readFileSync(events, 'utf8').trim().split('\n').map(line => JSON.parse(line));
    const summary = path.join(directory, 'summary.md');
    const temporary = `${summary}.${process.pid}.tmp`;
    fs.writeFileSync(temporary, report(records, record));
    fs.renameSync(temporary, summary);
  }
}

module.exports = { appendObservation };
