const {
  nonblank, present, uuid, csvMatches, checkPagination,
} = require('../../../../_shared/tools/preflight-values.cjs');

const profileFields = ['name', 'phone_number', 'country_calling_code', 'email'];
const csvFilters = {
  filter_type: 'ELITE_BUYER TOP_BUYER FREQUENT_BUYER REPEAT_BUYER BUYER NO_BUYER'.split(' '),
  filter_status: 'ACTIVE INACTIVE SLEEPING AT_RISK'.split(' '),
  filter_source: ['chatbot', 'ecommerce', 'panel'],
};
const sortFields = 'name phone_number available_points used_points source total_orders address'.split(' ');
const listFields = [
  'page', 'per_page', 'simple_paginate', 'sort_by', 'direction', 'include_addresses', 'filter_name',
  'filter_phone_number', 'filter_country_calling_code', 'filter_available_points', 'filter_used_points',
  ...Object.keys(csvFilters),
];
const tools = new Map([
  ['get_clients', { scope: 'clients:read', fields: listFields, list: true, prepare: prepareFilters }],
  ['get_client', { scope: 'clients:read', fields: ['id'], verify: verifyClient }],
  ['create_client', { scope: 'clients:write', fields: profileFields, verify: verifyClient }],
  ['update_client', { scope: 'clients:write', fields: ['id', ...profileFields], verify: verifyClient }],
]);

const matches = (value, pattern) => typeof value === 'string' && pattern.test(value);
const callingCode = value => matches(value, /^\d{1,4}$/);

function prepareFilters(fields) {
  for (const field of Object.keys(csvFilters)) {
    if (present(fields[field])) fields[field] = fields[field].split(',').map(value => value.trim()).join(',');
  }
  return fields;
}

function verifyClient(payload, { id }) {
  const returnedId = payload.data.id;
  if (!uuid(returnedId) || (id && id.toLowerCase() !== returnedId.toLowerCase())) {
    throw new Error('Não foi possível confirmar a ficha do cliente na resposta.');
  }
  return payload;
}

function checkList(entities, add) {
  checkPagination(entities, add);
  for (const field of ['simple_paginate', 'include_addresses']) {
    if (present(entities[field]) && typeof entities[field] !== 'boolean') add(field, `Confirma o filtro ${field}.`);
  }
  for (const [field, options] of Object.entries(csvFilters)) {
    if (present(entities[field]) && !csvMatches(entities[field], options)) add(field, `Confirma o filtro de clientes ${field}.`);
  }
  const {
    sort_by: sortBy, direction, filter_name: name, filter_phone_number: phone, filter_country_calling_code: country,
  } = entities;
  if (present(sortBy) && !sortFields.includes(sortBy)) add('sort_by', 'Por que campo queres ordenar os clientes?');
  if (present(direction) && !['asc', 'desc'].includes(direction)) add('direction', 'Queres ordem ascendente ou descendente?');
  if (present(name) && !nonblank(name)) add('filter_name', 'Qual é o nome a pesquisar?');
  if (present(phone) && !matches(phone, /^\d{1,20}$/)) {
    add('filter_phone_number', 'Indica o número nacional ou o prefixo só com algarismos.');
  }
  if (present(country) && (!callingCode(country) || !present(phone))) {
    add('filter_country_calling_code', 'Indica o indicativo só com algarismos e o número nacional a pesquisar.');
  }
  for (const field of ['filter_available_points', 'filter_used_points']) {
    if (present(entities[field]) && !Number.isFinite(entities[field])) add(field, 'Indica um número de pontos válido.');
  }
}

function checkProfile(entities, add, creating) {
  const { name, phone_number: phone, country_calling_code: country, email } = entities;
  if ((creating || Object.hasOwn(entities, 'name')) && (!nonblank(name) || Array.from(name).length > 150)) {
    add('name', 'Indica o nome do cliente, até 150 caracteres.');
  }
  if ((creating || Object.hasOwn(entities, 'phone_number')) && !matches(phone, /^\d{6,20}$/)) {
    add('phone_number', 'Indica o número nacional com 6 a 20 algarismos.');
  }
  if ((creating || Object.hasOwn(entities, 'country_calling_code')) && !callingCode(country)) {
    add('country_calling_code', 'Indica o código do país sem o sinal +.');
  }
  if (Object.hasOwn(entities, 'email') && (!matches(email, /^[^\s@]+@[^\s@]+\.[^\s@]+$/) || email.length > 150)) {
    add('email', 'Indica um endereço de email válido.');
  }
  if (!creating && !profileFields.some(field => Object.hasOwn(entities, field))) {
    add('profile', 'O que queres alterar na ficha do cliente?');
  }
}

function check({ intent, entities }, add, actor) {
  const tool = tools.get(intent);
  if (!tool) {
    add('intent', 'Esta operação de clientes não está disponível.', 'UNSUPPORTED_OPERATION');
    return;
  }
  if (actor !== 'owner') {
    add('actor', 'Esta operação está reservada à gerência.', 'UNSUPPORTED_OPERATION');
    return;
  }
  for (const field of Object.keys(entities)) {
    if (!tool.fields.includes(field)) add(field, `O campo ${field} não pertence a esta operação.`);
  }
  if (intent === 'get_clients') {
    checkList(entities, add);
    return;
  }
  if (tool.fields.includes('id') && !uuid(entities.id)) {
    add('id', 'Qual é o cliente? Usa o identificador da ficha verificada.');
  }
  if (tool.scope === 'clients:write') checkProfile(entities, add, intent === 'create_client');
}

module.exports = { check, tools };
