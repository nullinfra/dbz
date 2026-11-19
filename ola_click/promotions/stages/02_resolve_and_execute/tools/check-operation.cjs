const { present, nonblank, record, list, uuid, integer, number, date, dateTime } = require('../../../../_shared/tools/preflight-values.cjs');

const services = ['delivery', 'takeaway', 'onsite', 'table'];
const weekdays = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];
const clock = value => typeof value === 'string' && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);

module.exports = function check({ entities: e }, add) {
  const operation = e.operation ?? 'list';
  if (!['list', 'get', 'create', 'update', 'delete'].includes(operation)) {
    add('operation', 'Queres consultar, criar, alterar ou eliminar uma promoção?');
    return;
  }
  if (['get', 'update', 'delete'].includes(operation) && !uuid(e.promotion_id)) {
    add('promotion_id', 'Confirma a promoção na lista da OlaClick e usa o respetivo identificador.');
  }
  if (!['create', 'update'].includes(operation)) return;
  if (operation === 'create' && (!nonblank(e.name) || !nonblank(e.code) ||
      !present(e.discount_value) || !present(e.minimum_order_amount) || !nonblank(e.valid_from) ||
      !nonblank(e.valid_until) || typeof e.published !== 'boolean' || !Object.hasOwn(e, 'usage_limit'))) {
    add('coupon', 'Confirma o código, valor, prazo, mínimo de compra, limite de utilizações e publicação do cupão.');
  }
  if ((operation === 'create' || present(e.discount_type)) && !['percentage', 'amount'].includes(e.discount_type)) {
    add('discount_type', 'O desconto é um montante fixo ou uma percentagem?');
  }
  if (present(e.discount_value) && (!number(e.discount_value) || e.discount_value === 0 ||
      (e.discount_type === 'percentage' && e.discount_value > 100))) {
    add('discount_value', 'Indica um desconto superior a zero e de até 100% se for uma percentagem.');
  }
  if ([e.valid_from, e.valid_until].some(value => present(value) && !date(value) && !dateTime(value)) ||
      (present(e.valid_from) && present(e.valid_until) && Date.parse(e.valid_from) >= Date.parse(e.valid_until))) {
    add('validity', 'Confirma as datas de início e fim da promoção.');
  }
  if (present(e.usage_limit) && !integer(e.usage_limit, 1)) {
    add('usage_limit', 'Indica um limite inteiro superior a zero.');
  }
  if (present(e.service_types) && (!Array.isArray(e.service_types) ||
      e.service_types.some(service => !services.includes(service)))) {
    add('service_types', 'Em que modalidades de serviço se aplica a promoção?');
  }
  if (present(e.schedule)) {
    const { active_days: days, time_from: start, time_to: end } = record(e.schedule) ? e.schedule : {};
    if (!Array.isArray(days) || days.some(day => !weekdays.includes(day)) ||
        ((list(days).length || present(start) || present(end)) && (!clock(start) || !clock(end)))) {
      add('schedule', 'Confirma os dias e as horas de início e fim em que o cupão pode ser usado.');
    }
  }
  if (list(e.product_queries).length || ((e.promotion_type === 'products' || present(e.products)) &&
      (e.promotion_type !== 'products' || !list(e.products).length ||
       e.products.some(product => !uuid(product?.id) || !nonblank(product.name))))) {
    add('products', 'Quais são os produtos do cupão? Usa os nomes e identificadores da lista atual.');
  }
};
