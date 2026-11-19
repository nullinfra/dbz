const { present, nonblank, number, uuid } = require('../../../../_shared/tools/preflight-values.cjs');

module.exports = function check({ intent, entities }, add) {
  if (intent === 'check_menu_item' && !uuid(entities.product_id) && !nonblank(entities.product_query)) {
    add('product_id', 'Qual é o produto que queres consultar?');
  }
  if (intent !== 'get_menu_category') return;
  const { min_price: min, max_price: max } = entities;
  if ([min, max].some(value => present(value) && !number(value)) ||
      (present(min) && present(max) && min > max)) {
    add('price_range', 'Qual é o intervalo de preços? O mínimo tem de ser positivo ou zero e igual ou inferior ao máximo.');
  }
  if (['dietary', 'include_ingredient', 'exclude_ingredient'].some(field => nonblank(entities[field]))) {
    add('catalog_selection', 'Consulta a lista detalhada e confirma os produtos compatíveis com o pedido.');
  }
};
