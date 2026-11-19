const { connect, loadSettings } = require('../../../../_shared/tools/mcp-client.cjs');
const { nonblank, present, integer, number, record, uuid } = require('../../../../_shared/tools/preflight-values.cjs');

const roles = 'admin manager waiter rider cook sales cashier'.split(' ');
const services = 'ONSITE TABLE DELIVERY TAKEAWAY'.split(' ');
const clientFields = ['name', 'phone_number', 'country_calling_code', 'email'];
const filters = {
  filter_type: 'ELITE_BUYER TOP_BUYER FREQUENT_BUYER REPEAT_BUYER BUYER NO_BUYER'.split(' '),
  filter_status: 'ACTIVE INACTIVE SLEEPING AT_RISK'.split(' '),
  filter_source: ['chatbot', 'ecommerce', 'panel'],
};
const sortFields = 'name phone_number available_points used_points source total_orders address'.split(' ');
const scopes = new Map([
  ['get_company', 'companies:read'], ['list_payment_methods', 'payment-methods:read'], ['list_users', 'users:read'],
  ['get_clients', 'clients:read'], ['get_client', 'clients:read'],
  ['create_client', 'clients:write'], ['update_client', 'clients:write'],
]);
const allowed = new Map([
  ['get_company', []],
  ['list_payment_methods', ['service_type']],
  ['list_users', ['role', 'active', 'page', 'per_page']],
  ['get_clients', ['page', 'per_page', 'simple_paginate', 'sort_by', 'direction', 'include_addresses', 'filter_name',
    'filter_phone_number', 'filter_country_calling_code', 'filter_available_points', 'filter_used_points', ...Object.keys(filters)]],
  ['get_client', ['id']],
  ['create_client', clientFields],
  ['update_client', ['id', ...clientFields]],
]);

const csvMatches = (value, options) => nonblank(value) && value.split(',').every(token => options.includes(token.trim()));
const nationalNumber = value => typeof value === 'string' && /^\d{6,20}$/.test(value);
const callingCode = value => typeof value === 'string' && /^\d{1,4}$/.test(value);
const email = value => typeof value === 'string' && value.length <= 150 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
const isWrite = tool => scopes.get(tool)?.endsWith(':write');

function check({ intent, entities: e }, add, actor) {
  if (!allowed.has(intent)) {
    add('intent', 'Esta operação de empresa, utilizadores ou clientes não está disponível.', 'UNSUPPORTED_OPERATION');
    return;
  }
  if (!['get_company', 'list_payment_methods'].includes(intent) && actor !== 'owner') {
    add('actor', 'Esta operação está reservada à gerência.', 'UNSUPPORTED_OPERATION');
    return;
  }
  for (const field of Object.keys(e)) {
    if (!allowed.get(intent).includes(field)) add(field, `O campo ${field} não pertence a esta operação.`);
  }
  if (present(e.service_type) && !services.includes(e.service_type)) {
    add('service_type', 'Queres os métodos de pagamento para entrega, levantamento, mesa ou consumo no local?');
  }
  if (present(e.page) && !integer(e.page, 1)) add('page', 'Indica uma página a partir de 1.');
  if (present(e.per_page) && !integer(e.per_page, 1, 100)) add('per_page', 'Indica entre 1 e 100 resultados por página.');
  if (present(e.role) && !csvMatches(e.role, roles)) add('role', 'Indica uma função válida da equipa.');
  for (const field of ['active', 'simple_paginate', 'include_addresses']) {
    if (present(e[field]) && typeof e[field] !== 'boolean') add(field, `Confirma o filtro ${field}.`);
  }
  if (intent === 'get_clients') {
    for (const [field, options] of Object.entries(filters)) {
      if (present(e[field]) && !csvMatches(e[field], options)) add(field, `Confirma o filtro de clientes ${field}.`);
    }
    if (present(e.sort_by) && !sortFields.includes(e.sort_by)) add('sort_by', 'Por que campo queres ordenar os clientes?');
    if (present(e.direction) && !['asc', 'desc'].includes(e.direction)) add('direction', 'Queres ordem ascendente ou descendente?');
    if (present(e.filter_name) && !nonblank(e.filter_name)) add('filter_name', 'Qual é o nome a pesquisar?');
    if (present(e.filter_phone_number) && (typeof e.filter_phone_number !== 'string' || !/^\d{1,20}$/.test(e.filter_phone_number))) {
      add('filter_phone_number', 'Indica o número nacional ou o prefixo só com algarismos.');
    }
    if (present(e.filter_country_calling_code) && (!callingCode(e.filter_country_calling_code) || !present(e.filter_phone_number))) {
      add('filter_country_calling_code', 'Indica o indicativo só com algarismos e o número nacional a pesquisar.');
    }
    for (const field of ['filter_available_points', 'filter_used_points']) {
      if (present(e[field]) && !number(e[field])) add(field, 'Indica um número de pontos igual ou superior a zero.');
    }
  }
  if (['get_client', 'update_client'].includes(intent) && !uuid(e.id)) {
    add('id', 'Qual é o cliente? Usa o identificador da ficha verificada.');
  }
  if (!isWrite(intent)) return;
  const creating = intent === 'create_client';
  if ((creating || Object.hasOwn(e, 'name')) && (!nonblank(e.name) || e.name.length > 150)) {
    add('name', 'Indica o nome do cliente, até 150 caracteres.');
  }
  if ((creating || Object.hasOwn(e, 'phone_number')) && !nationalNumber(e.phone_number)) {
    add('phone_number', 'Indica o número nacional com 6 a 20 algarismos.');
  }
  if ((creating || Object.hasOwn(e, 'country_calling_code')) && !callingCode(e.country_calling_code)) {
    add('country_calling_code', 'Indica o código do país sem o sinal +.');
  }
  if (Object.hasOwn(e, 'email') && !email(e.email)) add('email', 'Indica um endereço de email válido.');
  if (!creating && !clientFields.some(field => Object.hasOwn(e, field))) {
    add('profile', 'O que queres alterar na ficha do cliente?');
  }
}

async function execute(operations) {
  loadSettings();
  const key = process.env.OLACLICK_API_KEY;
  const configured = nonblank(key) && key !== 'olk_live_replace_me';
  const results = [];
  let session;
  for (const operation of operations) {
    const { intent, entities } = operation;
    const { service_type: service, ...fields } = entities;
    const args = Object.fromEntries(Object.entries(fields).filter(([, value]) => present(value)));
    for (const field of ['role', ...Object.keys(filters)]) {
      if (typeof args[field] === 'string') args[field] = args[field].split(',').map(value => value.trim()).join(',');
    }
    const scope = scopes.get(intent);
    const write = isWrite(intent);
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
      let payload = await session(intent, args);
      if (!record(payload) || (['list_users', 'get_clients', 'list_payment_methods'].includes(intent)
        ? !Array.isArray(payload.data) : !record(payload.data))) {
        throw new Error('OlaClick devolveu uma resposta incompleta.');
      }
      if (write && (!uuid(payload.data.id) ||
          (intent === 'update_client' && args.id.toLowerCase() !== payload.data.id.toLowerCase()))) {
        throw new Error('Não foi possível confirmar a ficha do cliente na resposta.');
      }
      if (intent === 'list_payment_methods' && service) {
        if (payload.data.some(method => !Array.isArray(method?.service_types))) {
          throw new Error('OlaClick não indicou as modalidades de pagamento.');
        }
        payload = { ...payload, data: payload.data.filter(method =>
          method.service_types.some(type => String(type).toUpperCase() === service)) };
      }
      results.push({ ...base, status: 'COMPLETED', mcp_result: { mode: 'live', endpoint: intent, required_scope: scope, response: payload } });
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

module.exports = { check, execute, intents: new Set(scopes.keys()) };
