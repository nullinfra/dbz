const fs = require('node:fs');
const path = require('node:path');

const dir = process.argv[2];
const events = fs.readFileSync(path.join(dir, 'events.jsonl'), 'utf8')
  .split('\n').filter(Boolean).map(line => JSON.parse(line));
const jsonPath = path.join(dir, 'summary.json');
const mdPath = path.join(dir, 'summary.md');
const summary = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
let report = fs.readFileSync(mdPath, 'utf8');

const end = [...events].reverse().find(e => e.event === 'Stop' || e.event === 'Interrupt');
const start = events.find(e => e.event === 'UserPromptSubmit');
const first = events.find(e => Number.isFinite(e.monotonic_ns));
if (summary.elapsed_seconds == null && first && end && end.monotonic_ns >= first.monotonic_ns) {
  summary.elapsed_seconds = (end.monotonic_ns - first.monotonic_ns) / 1e9;
  summary.elapsed_start = start ? 'prompt' : 'first_observed_event';
  report = report.replace('**Elapsed:** unavailable', `**Elapsed:** ${summary.elapsed_seconds.toFixed(2)} s (from first observed event; actual run may be longer)`);
}

// Only pair requests when there is exactly one outstanding request. Overlapping
// requests cannot be matched reliably without an identifier in both events.
let pending = [];
let ambiguous = false;
const durations = new Map();
for (const e of events) {
  if (e.event === 'PreModelRequest') {
    pending.push(e);
    if (pending.length > 1) ambiguous = true;
  }
  if (e.event === 'PostModelRequest') {
    if (!ambiguous && pending.length === 1 && Number.isFinite(e.monotonic_ns) && Number.isFinite(pending[0].monotonic_ns) && e.monotonic_ns >= pending[0].monotonic_ns) {
      durations.set(e.monotonic_ns, (e.monotonic_ns - pending[0].monotonic_ns) / 1e9);
    }
    if (pending.length) pending.shift();
    if (!pending.length) ambiguous = false;
  }
}
for (const request of summary.model_requests || []) {
  request.duration_seconds = durations.get(request.monotonic_ns) ?? null;
}
const rows = (summary.model_requests || []).map(request => {
  const model = String(request.model ?? 'unknown').replace(/[|\r\n]/g, ' ');
  const duration = request.duration_seconds == null ? 'unavailable' : `${request.duration_seconds.toFixed(2)} s`;
  return `| ${model} | ${duration} | ${JSON.stringify(request.token_usage ?? {})} |`;
});
report = report.replace(/\| Model \| Token usage \|\n\|---\|---\|\n(?:\|[^\n]*\|\n)*/, `| Model | Duration | Token usage |\n|---|---:|---|\n${rows.join('\n')}\n`);
fs.writeFileSync(jsonPath, JSON.stringify(summary, null, 2) + '\n');
fs.writeFileSync(mdPath, report);
