const { integer, nonblank, number, uuid } = require('../../../../_shared/tools/preflight-values.cjs');

const intent = 'update_product_variant';
const moneyFields = ['price', 'original_price', 'cost', 'packaging_price'];
const stockFields = ['stock', 'stock_threshold'];
const changeFields = ['name', 'sku', ...moneyFields, ...stockFields];
const acceptedFields = new Set(['id', 'variantId', ...changeFields]);

function check({ entities }, add, actor) {
  if (actor !== 'owner') {
    add('actor', 'Esta operação está reservada à gerência.', 'UNSUPPORTED_OPERATION');
    return;
  }
  if (!uuid(entities.id)) add('id', 'Indica o UUID do produto verificado.');
  if (!uuid(entities.variantId)) add('variantId', 'Indica o UUID da variante verificada.');
  for (const field of Object.keys(entities)) {
    if (!acceptedFields.has(field)) add(field, `O campo ${field} não pertence a esta operação.`);
  }
  if (!changeFields.some(field => Object.hasOwn(entities, field))) {
    add('variant', 'Indica pelo menos um campo da variante para alterar.');
  }
  if (Object.hasOwn(entities, 'name') && (!nonblank(entities.name) || Array.from(entities.name).length > 191)) {
    add('name', 'Indica um nome de variante entre 1 e 191 caracteres.');
  }
  if (Object.hasOwn(entities, 'sku') && (typeof entities.sku !== 'string' || Array.from(entities.sku).length > 20)) {
    add('sku', 'Indica um SKU com até 20 caracteres.');
  }
  for (const field of moneyFields) {
    if (Object.hasOwn(entities, field) && (!number(entities[field]) ||
        !/^\d{1,9}(\.\d{1,2})?$/.test(String(entities[field])))) {
      add(field, 'Indica um valor entre zero e 999999999,99, com até duas casas decimais.');
    }
  }
  if (entities.price > entities.original_price) {
    add('original_price', 'O preço original tem de ser igual ou superior ao preço de venda.');
  }
  for (const field of stockFields) {
    if (Object.hasOwn(entities, field) && !integer(entities[field])) {
      add(field, 'Indica um valor inteiro igual ou superior a zero.');
    }
  }
}

function verify(payload, { variantId, name }) {
  if (!uuid(payload.data.id) || payload.data.id.toLowerCase() !== variantId.toLowerCase() ||
      (name !== undefined && payload.data.name !== name)) {
    throw new Error('A resposta da OlaClick não confirmou a alteração na variante pedida.');
  }
  return payload;
}

module.exports = { check, tools: new Map([[intent, { scope: 'menu:write', verify }]]) };
