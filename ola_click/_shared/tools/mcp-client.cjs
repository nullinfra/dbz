const path = require('node:path');

const defaultUrl = 'https://public-api.olaclick.app/mcp';

function loadSettings() {
  try {
    process.loadEnvFile(path.join(__dirname, '../../.env'));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
}

async function connect(apiKey, endpoint = defaultUrl) {
  const url = new URL(endpoint);
  if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Expected an HTTPS MCP endpoint.');
  const headers = {
    Authorization: `Bearer ${apiKey}`,
    Accept: 'application/json, text/event-stream',
    'Content-Type': 'application/json',
  };
  let nextId = 0;

  async function request(method, params, notification = false) {
    const id = notification ? undefined : ++nextId;
    const response = await fetch(url, {
      method: 'POST',
      headers,
      redirect: 'error',
      signal: AbortSignal.timeout(15000),
      body: JSON.stringify({ jsonrpc: '2.0', id, method, params }),
    });
    if (!response.ok) throw new Error(`OlaClick MCP returned HTTP ${response.status}.`);
    const session = response.headers.get('mcp-session-id');
    if (session) headers['Mcp-Session-Id'] = session;
    const body = await response.text();
    if (notification) return;
    const contentType = response.headers.get('content-type') ?? '';
    const messages = contentType.includes('text/event-stream')
      ? body.split(/\r?\n\r?\n/).map(event => event.split(/\r?\n/)
        .filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n'))
        .filter(Boolean).map(data => JSON.parse(data))
      : [JSON.parse(body)];
    const message = messages.find(candidate => candidate.id === id);
    if (!message || message.error || !message.result) {
      throw new Error(`OlaClick MCP failed to complete ${method}.`);
    }
    return message.result;
  }

  const initialized = await request('initialize', {
    protocolVersion: '2025-03-26',
    capabilities: {},
    clientInfo: { name: 'restaurante-icm', version: '1.0.0' },
  });
  if (typeof initialized.protocolVersion !== 'string') throw new Error('OlaClick MCP did not negotiate a protocol version.');
  headers['MCP-Protocol-Version'] = initialized.protocolVersion;
  await request('notifications/initialized', undefined, true);

  return async (name, args) => {
    const result = await request('tools/call', { name, arguments: args });
    const text = result.content?.find(item => item.type === 'text')?.text;
    let data = result.structuredContent;
    if (data === undefined && text) {
      try { data = JSON.parse(text); } catch { data = undefined; }
    }
    if (result.isError) {
      const error = new Error('OlaClick rejected this operation.');
      error.problem = data;
      throw error;
    }
    if (data === undefined) throw new Error('OlaClick MCP returned no structured result.');
    return data;
  };
}

module.exports = { connect, loadSettings };
