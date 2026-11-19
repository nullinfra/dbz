const { present, nonblank, list, uuid, integer, number, dateTime } = require('../../../../_shared/tools/preflight-values.cjs');
const { checkItem } = require('../../../../order_create/stages/02_resolve_and_execute/tools/check-draft.cjs');

module.exports = function check({ intent, entities: e }, add) {
  if (intent === 'update_order') {
    if (list(e.ambiguous_notes).length) add('ambiguous_notes', 'A que artigo se aplica cada observação?');
    const seenCombos = new Set();
    for (const field of ['items_add', 'items_remove', 'items_set_quantity', 'items_swap']) {
      for (const [index, item] of list(e[field]).entries()) {
        const reference = `${field}[${index}]`;
        const minimum = field === 'items_set_quantity' ? 0 : 1;
        if ((present(item?.quantity) || field === 'items_set_quantity') && !integer(item?.quantity, minimum)) {
          add(reference + '.quantity', 'Confirma a quantidade inteira da alteração.');
        }
        if (field !== 'items_add') {
          if (!uuid(item?.combo_id) || seenCombos.has(item.combo_id)) {
            add(reference + '.combo_id', 'Indica uma linha distinta do pedido atual para cada alteração.');
          } else {
            seenCombos.add(item.combo_id);
          }
        }
        if (field === 'items_add' || field === 'items_swap') {
          const selected = field === 'items_swap' ? item?.replacement : item;
          checkItem(selected, (choice, details) => add(reference + '.' + choice,
            details?.question ?? 'Confirma os detalhes do artigo a adicionar.', undefined,
            { product: selected?.name, ...details }));
        }
      }
    }
    for (const field of ['delivery_price', 'packaging_price']) {
      if (present(e[field]) && !number(e[field])) add(field, 'Confirma o preço, que deve ser igual ou superior a zero.');
    }
    if (present(e.scheduled_delivery_date) && !dateTime(e.scheduled_delivery_date)) {
      add('scheduled_delivery_date', 'Confirma a data e a hora agendadas com o fuso horário.');
    }
  }
  if (intent === 'advance_order_status') {
    const ids = [e.order_id, ...list(e.order_ids)].filter(nonblank);
    if (new Set(ids.map(id => id.trim().toLowerCase())).size !== ids.length) {
      add('order_ids', 'Quais são os pedidos distintos cujo estado queres alterar?');
    }
    if (!['PENDING', 'PREPARING', 'READY', 'DELIVERED', 'FINALIZED'].includes(e.new_status)) {
      add('new_status', 'Para que estado devo avançar o pedido?');
    }
  }
  if (intent === 'apply_coupon_or_promo') {
    const coupon = nonblank(e.coupon_code);
    const discount = present(e.discount_type) || present(e.discount_value);
    if (Number(coupon) + Number(discount) + Number(e.remove_discount === true) !== 1) {
      add('discount_action', 'Queres aplicar um cupão, dar um desconto manual ou remover um desconto?');
    } else if (discount && (!['PERCENTAGE', 'AMOUNT'].includes(e.discount_type) ||
        !number(e.discount_value, Number.MIN_VALUE, e.discount_type === 'PERCENTAGE' ? 100 : Infinity))) {
      add('discount_value', 'Indica o tipo e o valor do desconto.');
    } else if (e.remove_discount === true && !uuid(e.discount_id)) {
      add('discount_id', 'Qual dos descontos do pedido queres remover?');
    }
  }
  if (intent !== 'register_payment') return;
  const payments = list(e.payments);
  if (e.remove_payment === true) {
    if (!uuid(e.payment_id) || payments.length || present(e.payment_method_id) || present(e.amount)) {
      add('payment_id', 'Qual é o pagamento a remover? Indica-o sem acrescentar outro pagamento na mesma operação.');
    }
    return;
  }
  if (payments.length && ['payment_method_id', 'amount', 'received_amount', 'tip_amount'].some(field => present(e[field]))) {
    add('payments', 'Confirma se é um pagamento único ou dividido e indica o montante por método.');
  }
  for (const [index, payment] of (payments.length ? payments : [e]).entries()) {
    if (!uuid(payment?.payment_method_id) || ((payments.length || present(payment.amount)) &&
        !number(payment.amount, Number.MIN_VALUE))) {
      add(`payments[${index}]`, 'Indica o método e o montante positivo de cada pagamento.');
      continue;
    }
    if (present(payment.received_amount) && (!number(payment.received_amount) ||
        (present(payment.amount) && payment.received_amount < payment.amount))) {
      add(`payments[${index}].received_amount`, 'Confirma quanto foi recebido para cobrir o montante cobrado.');
    }
    if (present(payment.tip_amount) && !number(payment.tip_amount)) {
      add(`payments[${index}].tip_amount`, 'Indica uma gorjeta igual ou superior a zero.');
    }
  }
};
