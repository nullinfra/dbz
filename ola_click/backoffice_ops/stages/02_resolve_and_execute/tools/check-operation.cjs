const { present, nonblank, uuid, date, integer, coordinates } = require('../../../../_shared/tools/preflight-values.cjs');

module.exports = function check({ intent, entities: e }, add) {
  if (intent === 'list_active_orders' || intent === 'sales_summary') {
    if ([e.start_date, e.end_date].some(value => present(value) && !date(value)) ||
        (present(e.start_date) && present(e.end_date) && e.start_date > e.end_date)) {
      add('date_range', 'Qual é o período do relatório? Indica datas válidas com início igual ou anterior ao fim.');
    }
    if (present(e.top_limit) && !integer(e.top_limit, 1)) {
      add('top_limit', 'Quantos produtos queres ver no relatório?');
    }
  }
  if (intent !== 'manage_customer_address') return;
  if (present(e.customer_id) && !uuid(e.customer_id)) {
    add('customer_id', 'Indica o cliente pelo identificador verificado ou pelo número de telefone.');
  }
  if (!nonblank(e.customer_id) && !nonblank(e.customer_phone) && !nonblank(e.customer_name)) {
    add('customer', 'De que cliente é a morada?');
  }
  if (e.operation !== 'upsert') return;
  if (!uuid(e.customer_id) && (!/^\d{6,20}$/.test(e.customer_phone ?? '') ||
      !/^\d{1,4}$/.test(e.country_calling_code ?? ''))) {
    add('customer_phone', 'Qual é o número nacional e o indicativo do cliente para guardar a morada na ficha correta?');
  }
  if (present(e.coordinates) && !coordinates(e.coordinates.lat, e.coordinates.lng)) {
    add('coordinates', 'Confirma a latitude e longitude da morada.');
  }
  for (const [field, max] of [['delivery_address', 191], ['complement', 100], ['reference', 100]]) {
    if (present(e[field]) && (typeof e[field] !== 'string' || e[field].length > max)) {
      add(field, `Confirma o campo ${field} com até ${max} caracteres.`);
    }
  }
};
