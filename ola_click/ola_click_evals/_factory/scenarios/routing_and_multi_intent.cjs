const { id, completed, clarify, unsupported, op, call, item, draft, menuEdit, question, t, scenario } = require('./helpers.cjs');

module.exports = [
  scenario('route-question-plus-order', 'customer', ['routing', 'batch', 'short'],
    t('Estão abertos agora? Quero 2 Pastéis de Carne para levar, ainda não envies.', {
      calls: [call('get_company')],
      draft: draft([item(11, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['abert', '10[,.]4'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('route-order-plus-delivery-quote-plus-payment', 'customer', ['routing', 'batch', 'delivery', 'short'],
    t('Quero 2 Pastéis de Carne para entrega no distrito de Corroios. Quanto custa a entrega e aceitam MB WAY?', {
      calls: [call('get_delivery_pricing'), call('get_delivery_quote', { district_id: id(421) }), call('list_payment_methods')],
      reply: ['2[,.]5', 'mb[ -]*way'],
    })),

  scenario('route-greeting-with-embedded-order', 'customer', ['routing', 'draft', 'short'],
    t('Boa tarde! Quero 2 Pastéis de Carne para levar, ainda não envies.', {
      draft: draft([item(11, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['pastel de carne', '10[,.]4'],
    })),

  scenario('route-owner-read-plus-write-plus-unsupported', 'owner', ['routing', 'batch', 'long'],
    t('Diz-me os estafetas ativos, muda o preço do Brigadeiro para 1,60 € e apaga o Pudim.', {
      calls: [call('list_users', { role: 'rider', active: true })],
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), price: 1.6 })],
      menu: [menuEdit(32, 132, { price: 1.6, original_price: 1.6 })],
      reply: ['rui lopes', '1[,.]6', 'apagar|painel'],
    }),
    t('Volta a pôr o preço e preço original do Brigadeiro a 1,50 €.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), price: 1.5, original_price: 1.5 })],
      menu: [menuEdit(32, 132, { price: 1.5, original_price: 1.5 })],
      reply: ['1[,.]5'],
    })),

  scenario('route-owner-two-writes-same-product', 'owner', ['routing', 'batch', 'long'],
    t('Muda a descrição do Pastel de Carne para "Receita especial da casa." e o preço para 5,50 €.', {
      operations: [op('edit_menu', completed)],
      writes: [
        call('update_product', { product_id: id(11), description: 'Receita especial da casa.' }),
        call('update_product_variant', { id: id(11), variantId: id(111), price: 5.5 }),
      ],
      menu: [
        { number: 11, patch: { description: 'Receita especial da casa.' } },
        menuEdit(11, 111, { price: 5.5, original_price: 5.5 }),
      ],
      reply: ['5[,.]5', 'receita especial'],
    }),
    t('Repõe a descrição do Pastel de Carne para "Pastel frito com recheio de carne de vaca." e o preço e preço original para 5,20 €.', {
      operations: [op('edit_menu', completed)],
      writes: [
        call('update_product', { product_id: id(11), description: 'Pastel frito com recheio de carne de vaca.' }),
        call('update_product_variant', { id: id(11), variantId: id(111), price: 5.2, original_price: 5.2 }),
      ],
      menu: [
        { number: 11, patch: { description: 'Pastel frito com recheio de carne de vaca.' } },
        menuEdit(11, 111, { price: 5.2, original_price: 5.2 }),
      ],
      reply: ['5[,.]2'],
    })),

  scenario('route-owner-dependent-write-chain', 'owner', ['routing', 'promotions', 'short'],
    t('Cria o cupão TESTE10 de 10% desconto, mínimo 5 €, limite 10 usos, de 2026-11-01 a 2026-12-31, ativo, e depois pausa-o logo.', {
      orderedWrites: true,
      writes: [
        call('create_promotion', { coupon_code: 'TESTE10', discount_value: 10 }),
        call('update_promotion', { published: false }),
      ],
      reply: ['teste10', 'pausad|desativad'],
    })),

  scenario('route-analytics-plus-stock-action', 'owner', ['routing', 'backoffice', 'stock', 'long'],
    t('Qual foi o produto mais vendido de 1 a 7 de novembro de 2026? Marca-o como esgotado.', {
      calls: [call('get_products_sold')],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), stock: 0 })],
      menu: [menuEdit(11, 111, { stock: 0 })],
      reply: ['pastel de carne', '4', 'esgotad'],
    }),
    t('Repõe o Pastel de Carne com 13 unidades.', {
      operations: [op('restore_item_in_stock', completed)],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), stock: 13 })],
      menu: [menuEdit(11, 111, { stock: 13 })],
      reply: ['13'],
    })),

  scenario('route-multi-turn-pronoun-resolution', 'customer', ['routing', 'draft', 'long'],
    t('Quanto custa o Pudim?', {
      calls: [call('get_menu')],
      available: [31],
      reply: ['3[,.]25'],
    }),
    t('E o Brigadeiro?', {
      calls: [call('get_menu')],
      available: [32],
      reply: ['1[,.]5'],
    }),
    t('Mete 2 desse último para levar, ainda não envies.', {
      draft: draft([item(32, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['brigadeiro', '3[,.]00|3 €'],
    })),

  scenario('route-owner-order-by-daily-id', 'owner', ['routing', 'orders', 'long'],
    t('Vê o estado do pedido #1.', {
      operations: [op('check_order_status', completed)],
      calls: [call('get_order', { id: id(301) })],
      reply: ['pt-eval101', 'prepar'],
    }),
    t('Marca esse como pronto.', {
      operations: [op('advance_order_status', completed)],
      writes: [call('update_order_status', { id: id(301), status: 'READY' })],
      reply: ['pronto'],
    })),
];
