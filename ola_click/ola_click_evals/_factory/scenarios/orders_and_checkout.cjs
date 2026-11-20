const { id, completed, clarify, unsupported, op, call, item, draft, question, t, scenario, scenarioWithFixture } = require('./helpers.cjs');

module.exports = [
  scenario('order-menu-student-ineligible-pastry', 'customer', ['draft', 'menu', 'short'],
    t('Quero um Menu Estudante com pastel de frango.', {
      draft: draft([item(41, 1)], ['catalog_review.selection']),
      ...question('carne|queijo'),
    })),

  scenario('order-menu-student-ineligible-drink', 'customer', ['draft', 'menu', 'short'],
    t('Quero um Menu Estudante com pastel de carne, molho de alho e uma Água.', {
      draft: draft([item(41, 1)], ['catalog_review.selection'], { selections: ['Carne', 'Alho'] }),
      ...question('guaraná|coca'),
    })),

  scenario('order-menu-student-garrafa-1l-ineligible', 'customer', ['draft', 'menu', 'short'],
    t('Quero um Menu Estudante com pastel de carne, molho picante e Guaraná garrafa de 1 litro.', {
      draft: draft([item(41, 1)], ['catalog_review.selection'], { selections: ['Carne', 'Picante'] }),
      ...question('lata|330'),
    })),

  scenario('order-menu-student-no-sauce-blocked', 'customer', ['draft', 'menu', 'short'],
    t('Quero um Menu Estudante com pastel de carne, sem molho, e lata de Coca-Cola.', {
      draft: draft([item(41, 1)], ['catalog_review.selection'], { selections: ['Carne', 'Coca-Cola'] }),
      ...question('alho|picante|molho'),
    })),

  scenario('order-menu-student-two-sauces-blocked', 'customer', ['draft', 'menu', 'short'],
    t('Quero um Menu Estudante com pastel de queijo, molho de alho e picante, e lata de Guaraná.', {
      draft: draft([item(41, 1)], ['catalog_review.selection'], { selections: ['Queijo', 'Guaraná'] }),
      ...question('um molho|apenas|alho|picante'),
    })),

  scenario('order-menu-student-standalone-drink-split', 'customer', ['draft', 'menu', 'short'],
    t('Quero um Menu Estudante com pastel de carne, molho de alho e Guaraná, e à parte uma Coca-Cola.', {
      draft: draft([item(41, 1), item(22, 1, 122)], ['service_type'], { selections: ['Carne', 'Alho', 'Guaraná'] }),
      ...question('entrega|levantamento|recolha'),
    })),

  scenario('order-menu-student-two-units-different-choices', 'customer', ['draft', 'menu', 'long'],
    t('Quero dois Menus Estudante para levar.', {
      draft: draft([item(41, 2)], ['catalog_review.selection'], { service: 'TAKEAWAY' }),
      question: true,
    }),
    t('Um com carne, alho e Guaraná; o outro com queijo, picante e Coca-Cola. Ainda não envies.', {
      draft: draft([item(41, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['17[,.]00|17 €'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-menu-student-weekend-blocked', 'customer', ['draft', 'dates', 'short'],
    t('Quero um Menu Estudante para domingo, 29 de novembro de 2026.', {
      reply: ['segunda|sexta|disponível|domingo'],
    })),

  scenario('order-scheduled-outside-hours', 'customer', ['draft', 'dates', 'hours', 'short'],
    t('Quero um Pastel de Carne para levantar hoje às 23:30.', {
      calls: [call('get_company')],
      reply: ['22:00|horário|fech'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-scheduled-past-date', 'customer', ['draft', 'dates', 'short'],
    t('Quero um Pastel de Carne para ontem às 14:00.', {
      reply: ['passad|ontem|data|futur'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-frozen-acknowledgement', 'customer', ['draft', 'short'],
    t('Quero dois Pastéis de Carne Congelados para levar.', {
      draft: draft([item(51, 2)], ['catalog_review.issue'], { service: 'TAKEAWAY' }),
      ...question('congelad|fritar'),
    })),

  scenario('order-lactose-vs-cheese', 'customer', ['draft', 'allergens', 'short'],
    t('Quero um Pastel de Queijo. Sou intolerante à lactose.', {
      draft: draft([item(12, 1)], ['allergy_review']),
      reply: ['leite|lactose|alerg'],
      exclude: ['sem risco|garanto que não tem leite'],
    })),

  scenario('order-gluten-celiac-warning', 'customer', ['draft', 'allergens', 'short'],
    t('Sou celíaco, posso comer o Pastel de Carne?', {
      calls: [call('get_menu')],
      reply: ['trigo|glúten|alerg|não'],
      exclude: ['sem glúten|seguro para celíacos'],
    })),

  scenario('order-allergy-post-draft-added', 'customer', ['draft', 'allergens', 'long'],
    t('Quero um Brigadeiro para levar.', {
      draft: draft([item(32, 1)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['brigadeiro'],
    }),
    t('Esqueci-me de dizer: tenho alergia grave a frutos secos.', {
      draft: draft([item(32, 1)], ['allergy_review'], { service: 'TAKEAWAY' }),
      reply: ['alerg|frutos secos|confirm'],
      exclude: ['garanto|sem risco'],
    })),

  scenario('order-ambiguous-quantity', 'customer', ['draft', 'short'],
    t('Quero uns pastéis de carne para levar.', {
      ...question('quantos|quantidade'),
    })),

  scenario('order-quantity-dozen', 'customer', ['draft', 'short'],
    t('Quero meia dúzia de brigadeiros para levar. Ainda não envies.', {
      draft: draft([item(32, 6)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['6', '9[,.]00|9 €'],
    })),

  scenario('order-quantity-zero-rejected', 'customer', ['draft', 'validation', 'short'],
    t('Quero 0 pastéis de carne.', {
      forbidCalls: ['create_order'],
      reply: ['quant|positiv|pelo menos 1|zero'],
    })),

  scenario('order-service-aliases-onsite', 'customer', ['draft', 'short'],
    t('Quero uma Água para comer aí.', {
      draft: draft([item(23, 1)], [], { service: 'ONSITE', exactMissing: true }),
      reply: ['água', '1[,.]2'],
    })),

  scenario('order-service-aliases-takeaway', 'customer', ['draft', 'short'],
    t('Quero uma Água, eu vou buscar.', {
      draft: draft([item(23, 1)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['água', '1[,.]2'],
    })),

  scenario('order-service-table', 'customer', ['draft', 'short'],
    t('Quero uma Água para a Mesa 4. Ainda não envies.', {
      calls: [call('list_tables')],
      draft: draft([item(23, 1)], [], { service: 'TABLE', exactMissing: true }),
      reply: ['mesa 4', 'água'],
    })),

  scenario('order-service-table-invalid', 'customer', ['draft', 'short'],
    t('Quero uma Água para a Mesa 99.', {
      calls: [call('list_tables')],
      ...question('mesa 1|mesa 4|não encontr'),
    })),

  scenario('order-service-type-switch-to-delivery', 'customer', ['draft', 'delivery', 'long'],
    t('Quero 2 Pastéis de Carne para levar.', {
      draft: draft([item(11, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['10[,.]4'],
    }),
    t('Afinal vai ser para entrega.', {
      draft: draft([item(11, 2)], ['delivery_address'], { service: 'DELIVERY', exactMissing: true }),
      ...question('morada|endereço|rua'),
    })),

  scenario('order-invalid-payment-mbway-takeaway', 'customer', ['orders', 'payments', 'short'],
    t('Quero um Brigadeiro para levantar e pagar por MB WAY.', {
      calls: [call('list_payment_methods')],
      reply: ['mb[ -]*way', 'entrega|numerário|dinheiro|cartão'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-invalid-payment-card-delivery', 'customer', ['orders', 'payments', 'short'],
    t('Quero um Brigadeiro para entregar na Av. Cristo Rei, 47, Corroios, pago com cartão.', {
      calls: [call('list_payment_methods')],
      reply: ['cartão', 'balcão|numerário|mb[ -]*way'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-cash-change-valid', 'customer', ['orders', 'payments', 'short'],
    t('Quero dois Pastéis de Carne para levar. Envia já, pago em dinheiro com troco para 20 €.', {
      operations: [op('create_order', completed)],
      writes: [
        call('create_order', { service_type: 'TAKEAWAY' }),
        call('add_order_combos', { combos: [{ variant_id: id(111), quantity: 2 }] }),
        call('update_order_status', { status: 'PENDING' }),
      ],
      reply: ['pt-eval105', '20'],
    })),

  scenario('order-cash-change-below-total', 'customer', ['orders', 'payments', 'short'],
    t('Quero dois Pastéis de Carne para levar, pago em dinheiro com troco para 5 €.', {
      reply: ['5', '10[,.]4|insuficiente|inferior|troco'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-stock-exceeded', 'customer', ['orders', 'stock', 'short'],
    t('Quero 20 Pastéis de Carne para levar. Envia já.', {
      reply: ['13|stock|disponív|quantidade'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-delivery-missing-address', 'customer', ['draft', 'delivery', 'short'],
    t('Quero dois Pastéis de Carne para entrega.', {
      draft: draft([item(11, 2)], ['delivery_address'], { service: 'DELIVERY', exactMissing: true }),
      ...question('morada|endereço|rua'),
    })),

  scenarioWithFixture('order-closed-store-blocked', 'customer', ['orders', 'hours', 'short'],
    { company: { currently_open: false } },
    t('Quero um Pastel de Carne para levar agora. Envia já.', {
      calls: [call('get_company')],
      reply: ['fechad|horário'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-idempotency-double-send', 'customer', ['orders', 'long'],
    t('Quero um Brigadeiro para levar. Envia já, pago em dinheiro.', {
      operations: [op('create_order', completed)],
      orderedWrites: true,
      writes: [
        call('create_order', { service_type: 'TAKEAWAY' }),
        call('add_order_combos', { combos: [{ variant_id: id(132), quantity: 1 }] }),
        call('update_order_status', { status: 'PENDING' }),
      ],
      reply: ['pt-eval105'],
    }),
    t('Quero um Brigadeiro para levar. Envia já, pago em dinheiro.', {
      forbidCalls: ['create_order'],
      reply: ['pt-eval105|já'],
    })),

  scenario('order-basket-replacement', 'customer', ['draft', 'long'],
    t('Quero dois Pastéis de Carne.', {
      draft: draft([item(11, 2)], ['service_type']),
      question: true,
    }),
    t('Esquece tudo, afinal quero começar de novo só com 2 Águas para levar.', {
      draft: draft([item(23, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['água', '2[,.]4'],
    })),

  scenario('order-remove-nonexistent-item', 'customer', ['draft', 'long'],
    t('Quero 2 Pastéis de Carne.', {
      draft: draft([item(11, 2)], ['service_type']),
      question: true,
    }),
    t('Tira a Água do pedido.', {
      draft: draft([item(11, 2)], ['service_type']),
      reply: ['água', 'não está|não tinha|rascunho'],
    })),

  scenario('order-remove-more-than-exists', 'customer', ['draft', 'long'],
    t('Quero 2 Brigadeiros.', {
      draft: draft([item(32, 2)], ['service_type']),
      question: true,
    }),
    t('Tira 3 brigadeiros.', {
      reply: ['2|brigadeiro|remov|zero|vazio'],
    })),

  scenario('order-clear-entire-draft', 'customer', ['draft', 'long'],
    t('Quero 2 Pastéis de Carne.', {
      draft: draft([item(11, 2)], ['service_type']),
      question: true,
    }),
    t('Tira tudo, esvazia o rascunho.', {
      forbidIntents: ['cancel_order'],
      reply: ['vazio|limp|cancel|rascunho'],
    })),

  scenario('order-language-switch-pt-to-en', 'customer', ['draft', 'language', 'long'],
    t('Quero um Pastel de Queijo.', {
      draft: draft([item(12, 1)], ['service_type']),
      question: true,
    }),
    t('Actually, make it two cheese pastries for takeaway.', {
      draft: draft([item(12, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['cheese|queijo', '9[,.]6'],
    })),

  scenario('order-unrelated-question-mid-draft', 'customer', ['draft', 'long'],
    t('Quero 2 Pastéis de Carne.', {
      draft: draft([item(11, 2)], ['service_type']),
      question: true,
    }),
    t('Já agora, estão abertos agora?', {
      calls: [call('get_company')],
      forbidIntents: ['create_order'],
      reply: ['abert'],
    }),
    t('Boa, então é para levantar, mas ainda não envies.', {
      draft: draft([item(11, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('order-multi-turn-add-this-to-order', 'customer', ['draft', 'long'],
    t('Quanto custa o Pudim?', {
      calls: [call('get_menu')],
      available: [31],
      reply: ['3[,.]25'],
    }),
    t('Adiciona isto ao pedido para levar, mas ainda não envies.', {
      draft: draft([item(31, 1)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['pudim', '3[,.]25'],
    })),

  scenarioWithFixture('order-modify-add-item-pending', 'owner', ['orders', 'short'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'PENDING',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva',
        combos: [{ id: id(601), variant_id: id(111), quantity: 1, name: 'Pastel de Carne', price: 5.2 }],
        items: [{ id: id(601), variant_id: id(111), quantity: 1, name: 'Pastel de Carne', price: 5.2 }],
        total: 5.2, payments: [], discounts: [],
      }],
    },
    t('Adiciona 1 Brigadeiro ao pedido PT-EVAL101.', {
      operations: [op('update_order', completed)],
      writes: [call('add_order_combos', { id: id(301), combos: [{ variant_id: id(132), quantity: 1 }] })],
      reply: ['brigadeiro', 'pt-eval101'],
    })),

  scenario('order-modify-change-comment', 'owner', ['orders', 'short'],
    t('Adiciona a nota "sem guardanapos" ao pedido PT-EVAL101.', {
      operations: [op('update_order', completed)],
      writes: [call('update_order', { id: id(301), comment: 'sem guardanapos' })],
      reply: ['pt-eval101', 'guardanapos'],
    })),

  scenario('order-modify-cancel-order', 'owner', ['orders', 'short'],
    t('Cancela o pedido PT-EVAL101 porque o cliente desistiu.', {
      operations: [op('cancel_order', completed)],
      writes: [call('cancel_order', { id: id(301) })],
      reply: ['pt-eval101', 'cancelad'],
    })),

  scenarioWithFixture('order-modify-cancel-paid-order-blocked', 'owner', ['orders', 'payments', 'short'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'PREPARING',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 5.2,
        payments: [{ id: id(801), amount: 5.2, payment_method_id: id(401) }], discounts: [],
      }],
    },
    t('Cancela o pedido PT-EVAL101.', {
      reply: ['pagamento|pag|não'],
    })),

  scenarioWithFixture('order-modify-finalized-status-blocked', 'owner', ['orders', 'short'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'FINALIZED',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 5.2,
        payments: [], discounts: [],
      }],
    },
    t('Volta o pedido PT-EVAL101 para em preparação.', {
      reply: ['finaliz|não'],
    })),

  scenarioWithFixture('order-modify-backwards-status-blocked', 'owner', ['orders', 'short'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'READY',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 5.2,
        payments: [], discounts: [],
      }],
    },
    t('Volta o pedido PT-EVAL101 para pendente.', {
      forbidCalls: ['update_order_status'],
      reply: ['retroced|pronto|ready|não'],
    })),

  scenario('order-modify-apply-coupon-service-mismatch', 'owner', ['orders', 'promotions', 'short'],
    t('Aplica o cupão BALCAO10 ao pedido PT-EVAL102.', {
      reply: ['takeaway|levant|entrega|delivery|não'],
    })),

  scenarioWithFixture('order-modify-apply-coupon-below-min', 'owner', ['orders', 'promotions', 'short'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'PREPARING',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 5.2,
        payments: [], discounts: [],
      }],
    },
    t('Aplica o cupão BALCAO10 ao pedido PT-EVAL101.', {
      reply: ['mínim|10|5[,.]2|não'],
    })),

  scenarioWithFixture('order-modify-apply-coupon-success', 'owner', ['orders', 'promotions', 'short'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'PREPARING',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 15.0,
        payments: [], discounts: [],
      }],
    },
    t('Aplica o cupão BALCAO10 ao pedido PT-EVAL101.', {
      operations: [op('apply_coupon_or_promo', completed)],
      writes: [call('apply_order_coupon', { id: id(301), coupon_code: 'BALCAO10' })],
      reply: ['balcao10', 'aplicad'],
    })),

  scenario('order-modify-register-payment', 'owner', ['orders', 'payments', 'short'],
    t('Regista um pagamento de 5,20 € em numerário no pedido PT-EVAL101.', {
      operations: [op('register_payment', completed)],
      writes: [call('add_order_payment', { id: id(301), amount: 5.2 })],
      reply: ['5[,.]2|regist|pagamento'],
    })),

  scenario('order-modify-register-payment-negative-blocked', 'owner', ['orders', 'payments', 'short'],
    t('Regista um pagamento de -5 € no pedido PT-EVAL101.', {
      forbidCalls: ['add_order_payment'],
      reply: ['negativ|inválid|positiv'],
    })),
];
