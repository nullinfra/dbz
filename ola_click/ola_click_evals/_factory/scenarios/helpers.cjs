const { id } = require('../tools/fixture.cjs');

const completed = 'COMPLETED';
const clarify = 'NEEDS_CLARIFICATION';
const unsupported = 'UNSUPPORTED_OPERATION';
const op = (intent, status = completed, entities) => ({ intent, status, ...(entities ? { entities } : {}) });
const call = (name, args, ok = true) => ({ name, ...(args ? { args } : {}), ok });
const item = (number, quantity, variant) => ({
  product_id: id(number), quantity, ...(variant ? { variant_id: id(variant) } : {}),
});
const draft = (items, missing = [], extra) => ({ items, missing, ...extra });
const menuEdit = (number, variant, patch) => ({ number, variant, patch });
const question = (...reply) => ({ reply, question: true });
const stock = (number, variant, value) => ({
  writes: [call('update_product_variant', { id: id(number), variantId: id(variant), stock: value })],
  menu: [menuEdit(number, variant, { stock: value })],
});
const paidMethods = (service, ...reply) => ({
  operations: [op('list_payment_methods', completed, { service_type: service })],
  calls: [call('list_payment_methods')], reply,
});
const t = (text, checks) => ({ text, checks });
const scenario = (scenarioId, actor, tags, ...turns) => ({ id: scenarioId, actor, tags, turns });
const scenarioWithFixture = (scenarioId, actor, tags, fixture, ...turns) => ({
  id: scenarioId, actor, tags, fixture, turns,
});

module.exports = {
  id, completed, clarify, unsupported, op, call, item, draft, menuEdit, question, stock, paidMethods,
  t, scenario, scenarioWithFixture,
};
