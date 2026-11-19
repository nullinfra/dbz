const { present, nonblank, record, list, uuid, integer, number } = require('../../../../_shared/tools/preflight-values.cjs');

function priceCheck(e, add) {
  for (const field of ['price', 'original_price', 'packaging_price']) {
    if (present(e[field]) && !number(e[field])) add(field, 'O preço tem de ser um número igual ou superior a zero.');
  }
  if (present(e.price) && present(e.original_price) && e.price > e.original_price) {
    add('original_price', 'O preço original tem de ser igual ou superior ao preço de venda.');
  }
}

module.exports = function check({ intent, entities: e }, add) {
  if (e.apply_all === true && intent !== 'edit_menu') {
    add('apply_all', 'Confirma os produtos que devem mudar. O ajuste de stock tem de indicar cada produto para abranger todos os escolhidos.');
  }
  for (const field of ['product_id', 'category_id']) {
    if (present(e[field]) && !uuid(e[field])) add(field, 'Usa o identificador do catálogo ou indica o nome para fazer a pesquisa.');
  }
  if ((intent !== 'edit_menu' || e.operation === 'create_variant' ||
      (!e.operation && e.patch && !e.category_id && !e.category_query)) && !uuid(e.product_id)) {
    add('product_id', 'Confirma o produto no catálogo e usa o respetivo identificador.');
  }
  if (present(e.variant_id) && !uuid(e.variant_id)) {
    add('variant_id', 'Confirma a variante do produto no catálogo.');
  }
  if (intent === 'restore_item_in_stock' && !integer(e.stock, 1)) {
    add('stock', 'Quantas unidades queres repor? Indica um número inteiro superior a zero.');
  }
  if (intent !== 'edit_menu') return;
  if (e.operation === 'delete_category') {
    add('operation', 'A eliminação de categorias é feita no painel da OlaClick.', 'UNSUPPORTED_OPERATION');
  }
  const patch = record(e.patch) ? e.patch : {};
  priceCheck(e, add);
  priceCheck(patch, add);
  if (present(patch.price_delta) && present(patch.price_percent)) {
    add('price_change', 'Queres ajustar o preço por um valor fixo ou por uma percentagem?');
  }
  if ((present(patch.price_delta) && !number(patch.price_delta, -Infinity)) ||
      (present(patch.price_percent) && !number(patch.price_percent, -100))) {
    add('price_change', 'Indica um ajuste numérico. Uma redução percentual pode ir até 100%.');
  }
  if (patch.end_promo === true && ['price', 'original_price', 'price_delta', 'price_percent'].some(key => present(patch[key]))) {
    add('price_change', 'Indica o preço final pretendido depois de terminar a promoção.');
  }
  for (const field of ['position', 'stock', 'stock_threshold']) {
    if (present(patch[field]) && !integer(patch[field])) add(field, 'Indica um valor inteiro igual ou superior a zero.');
  }
  if (['create_product', 'create_variant'].includes(e.operation) && (!nonblank(e.name) || !number(e.price))) {
    add('new_item', 'Preciso do nome e do preço do novo produto ou variante.');
  }
  for (const [index, category] of list(e.categories).entries()) {
    if (!nonblank(category?.name) || !Array.isArray(category.products)) {
      add(`categories[${index}]`, 'Indica o nome da categoria e os produtos a importar.');
      continue;
    }
    if (category.products.some(product => !nonblank(product?.name) || !number(product.price))) {
      add(`categories[${index}].products`, `Verifica os nomes e preços de todos os produtos de ${category.name}.`);
    }
  }
};
