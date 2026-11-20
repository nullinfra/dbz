const { present, csvMatches, checkPagination } = require('../../../../_shared/tools/preflight-values.cjs');

const roles = 'admin manager waiter rider cook sales cashier'.split(' ');
const services = 'ONSITE TABLE DELIVERY TAKEAWAY'.split(' ');
const tools = new Map([
  ['get_company', { scope: 'companies:read', fields: [] }],
  ['list_payment_methods', {
    scope: 'payment-methods:read', fields: ['service_type'], list: true,
    prepare: () => ({}), verify: filterPaymentMethods,
  }],
  ['list_users', {
    scope: 'users:read', fields: ['role', 'active', 'page', 'per_page'], list: true, prepare: normalizeRoles,
  }],
]);

function normalizeRoles(fields) {
  if (present(fields.role)) fields.role = fields.role.split(',').map(value => value.trim()).join(',');
  return fields;
}

function filterPaymentMethods(payload, { service_type: service }) {
  if (!service) return payload;
  if (payload.data.some(method => !Array.isArray(method?.service_types))) {
    throw new Error('OlaClick não indicou as modalidades de pagamento.');
  }
  const data = payload.data.filter(method => method.service_types.some(type => String(type).toUpperCase() === service));
  return { ...payload, data };
}

function check({ intent, entities }, add, actor) {
  const tool = tools.get(intent);
  if (!tool) {
    add('intent', 'Esta operação de empresa ou utilizadores não está disponível.', 'UNSUPPORTED_OPERATION');
    return;
  }
  if (intent === 'list_users' && actor !== 'owner') {
    add('actor', 'Esta operação está reservada à gerência.', 'UNSUPPORTED_OPERATION');
    return;
  }
  for (const field of Object.keys(entities)) {
    if (!tool.fields.includes(field)) add(field, `O campo ${field} não pertence a esta operação.`);
  }
  if (present(entities.service_type) && !services.includes(entities.service_type)) {
    add('service_type', 'Queres os métodos de pagamento para entrega, levantamento, mesa ou consumo no local?');
  }
  if (intent === 'list_users') {
    checkPagination(entities, add);
    if (present(entities.role) && !csvMatches(entities.role, roles)) add('role', 'Indica uma função válida da equipa.');
    if (present(entities.active) && typeof entities.active !== 'boolean') add('active', 'Confirma o filtro active.');
  }
}

module.exports = { check, tools };
