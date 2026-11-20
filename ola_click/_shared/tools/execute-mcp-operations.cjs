const { connect, loadSettings } = require('./mcp-client.cjs');
const { nonblank, present, record } = require('./preflight-values.cjs');

async function execute(operations, adapterFor) {
  loadSettings();
  const key = process.env.OLACLICK_API_KEY;
  const configured = nonblank(key) && key !== 'olk_live_replace_me';
  const results = [];
  let session;
  for (const operation of operations) {
    const { intent, entities } = operation;
    const { scope, list, prepare, verify } = adapterFor(operation).tools.get(intent);
    const fields = Object.fromEntries(Object.entries(entities).filter(([, value]) => present(value)));
    const args = prepare ? prepare(fields) : fields;
    const write = scope.endsWith(':write');
    const base = { ...operation, needs_clarification: false, confirmation_required: false, mcp_result: null };
    const planned = { method: 'MCP', endpoint: intent, required_scope: scope, payload: args };
    if (write && (process.env.OLACLICK_ALLOW_WRITES !== '1' || !configured)) {
      results.push({ ...base, status: 'NEEDS_CONFIRMATION', confirmation_required: true, proposed_action: planned });
      continue;
    }
    if (!configured) {
      results.push({ ...base, status: 'PLANNED_DRY_RUN', proposed_action: planned });
      continue;
    }
    try {
      session ??= await connect(key, process.env.OLACLICK_MCP_URL);
      const payload = await session(intent, args);
      if (!record(payload) || !(list ? Array.isArray(payload.data) : record(payload.data))) {
        throw new Error('OlaClick devolveu uma resposta incompleta.');
      }
      const response = verify ? verify(payload, entities) : payload;
      results.push({
        ...base,
        status: 'COMPLETED',
        mcp_result: { mode: 'live', endpoint: intent, required_scope: scope, response },
      });
    } catch (error) {
      const problem = error.problem;
      results.push({
        ...base,
        status: 'API_ERROR',
        suggested_message: problem?.detail ?? error.message,
        mcp_result: { endpoint: intent, required_scope: scope, ...(problem ? { problem } : {}) },
      });
    }
  }
  return results;
}

module.exports = { execute };
