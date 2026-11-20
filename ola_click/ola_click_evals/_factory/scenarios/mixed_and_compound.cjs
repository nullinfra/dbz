const { id, completed, clarify, unsupported, op, call, item, draft, menuEdit, question, t, scenario, scenarioWithFixture } = require('./helpers.cjs');

module.exports = [
  scenario('mix-offer-to-draft-to-delivery-quote-payment', 'customer', ['routing', 'offers', 'delivery', 'payments', 'long'],
    t('Mostra-me as bebidas numa lista numerada.', {
      calls: [call('get_menu')],
      offer: [21, 22, 23],
      reply: ['guaraná', 'coca', 'água'],
    }),
    t('Quero 2 da terceira opção para entrega no distrito de Corroios. Quanto custa a entrega e aceitam MB WAY?', {
      calls: [call('get_delivery_pricing'), call('get_delivery_quote', { district_id: id(421) }), call('list_payment_methods')],
      reply: ['água', '2[,.]5', 'mb[ -]*way'],
    })),

  scenario('mix-maps-order-quote-and-confirm', 'customer', ['routing', 'maps', 'orders', 'delivery', 'payments', 'long'],
    t('Quero 2 Pastéis de Carne para entregar na Av. Cristo Rei, 47, Corroios. Quanto fica tudo com a entrega e posso pagar por MB WAY?', {
      calls: [call('list_payment_methods')],
      reply: ['10[,.]4', '2[,.]5', 'mb[ -]*way'],
    }),
    t('Confirmo, envia já o pedido e pago por MB WAY.', {
      operations: [op('create_order', completed)],
      writes: [
        call('create_order', { service_type: 'DELIVERY' }),
        call('add_order_combos', { combos: [{ variant_id: id(111), quantity: 2 }] }),
        call('update_order_status', { status: 'PENDING' }),
      ],
      reply: ['pt-eval105'],
    })),

  scenario('mix-student-menu-frozen-and-service-switch', 'customer', ['draft', 'menu', 'delivery', 'long'],
    t('Quero um Menu Estudante com carne, alho e Coca-Cola, mais um Pastel de Carne Congelado, para levar.', {
      draft: draft([item(41, 1), item(51, 1)], ['catalog_review.issue'], { service: 'TAKEAWAY', selections: ['Carne', 'Alho', 'Coca-Cola'] }),
      ...question('congelad|fritar'),
    }),
    t('Sim, sei que vem congelado. Afinal muda para entrega.', {
      draft: draft([item(41, 1), item(51, 1)], ['delivery_address'], { service: 'DELIVERY', exactMissing: true }),
      ...question('morada|endereço|rua'),
    })),

  scenario('mix-cheapest-allergen-and-low-cash-change', 'customer', ['menu', 'allergens', 'payments', 'long'],
    t('Qual é a sobremesa mais barata e tem leite?', {
      calls: [call('get_menu')],
      available: [32],
      reply: ['brigadeiro', '1[,.]5', 'leite'],
    }),
    t('Quero 4 brigadeiros para levar, pago em dinheiro com troco para 5 €.', {
      reply: ['6', '5', 'troco|insuficiente|inferior'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenarioWithFixture('mix-closed-store-hours-then-schedule', 'customer', ['hours', 'dates', 'draft', 'long'],
    { company: { currently_open: false } },
    t('Estão abertos agora? Quero 2 Pastéis de Carne para levar já.', {
      calls: [call('get_company')],
      reply: ['fechad'],
      exclude: ['pedido (confirmado|enviado)'],
    }),
    t('Então agenda para sexta-feira 27 de novembro de 2026 às 13:00, ainda não envies.', {
      draft: draft([item(11, 2)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['13:00|27'],
    })),

  scenario('mix-owner-client-lookup-address-and-quote', 'owner', ['clients', 'backoffice', 'delivery', 'long'],
    t('Procura a cliente Ana Silva e guarda a morada Av. Cristo Rei, 47, Corroios no perfil dela.', {
      calls: [call('get_clients', { filter_name: 'Ana Silva' })],
      writes: [call('create_address', { client_id: id(211) })],
      reply: ['ana silva', 'cristo rei'],
    }),
    t('Quanto custa a entrega para o distrito de Corroios?', {
      operations: [op('quote_delivery', completed)],
      calls: [call('get_delivery_pricing'), call('get_delivery_quote', { district_id: id(421) })],
      reply: ['2[,.]5'],
    })),

  scenario('mix-owner-full-delivery-logistics-chain', 'owner', ['delivery', 'orders', 'long'],
    t('Vê os estafetas ativos e atribui o Rui Lopes ao pedido PT-EVAL102.', {
      calls: [call('list_users', { role: 'rider', active: true })],
      writes: [call('assign_rider', { id: id(302), user_id: id(411) })],
      reply: ['rui lopes', 'pt-eval102'],
    }),
    t('Marca o PT-EVAL102 como a caminho para entrega e atualiza a posição para 38.635, -9.152.', {
      writes: [
        call('update_delivery_status', { id: id(302), delivery_status: 'DELIVERING' }),
        call('report_rider_position', { id: id(302), latitude: 38.635, longitude: -9.152 }),
      ],
      reply: ['entrega|caminho', '38[,.]635'],
    })),

  scenarioWithFixture('mix-owner-order-line-edit-discount-and-payment', 'owner', ['orders', 'payments', 'long'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'PENDING',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva',
        combos: [{ id: id(601), variant_id: id(111), quantity: 2, name: 'Pastel de Carne', price: 5.2 }],
        items: [{ id: id(601), variant_id: id(111), quantity: 2, name: 'Pastel de Carne', price: 5.2 }],
        total: 10.4, payments: [], discounts: [],
      }],
    },
    t('Remove o combo atual do pedido PT-EVAL101 e adiciona 3 Brigadeiros.', {
      writes: [
        call('remove_order_combo', { id: id(301), comboId: id(601) }),
        call('add_order_combos', { id: id(301), combos: [{ variant_id: id(132), quantity: 3 }] }),
      ],
      reply: ['brigadeiro', 'pt-eval101'],
    }),
    t('Regista um pagamento de 4,50 € em numerário no pedido PT-EVAL101.', {
      operations: [op('register_payment', completed)],
      writes: [call('add_order_payment', { id: id(301), amount: 4.5 })],
      reply: ['4[,.]5'],
    })),

  scenario('mix-owner-promo-create-pause-and-delete', 'owner', ['promotions', 'gates', 'long'],
    t('Cria o cupão FDS10 de 10% desconto, mínimo 5 €, limite 15 usos, de 2026-11-01 até 2026-12-31, ativo.', {
      operations: [op('manage_promotions', completed, { operation: 'create' })],
      writes: [call('create_promotion', { coupon_code: 'FDS10', discount_value: 10 })],
      reply: ['fds10'],
    }),
    t('Pausa o cupão FDS10.', {
      operations: [op('manage_promotions', completed, { operation: 'update' })],
      writes: [call('update_promotion', { published: false })],
      reply: ['pausad|desativad'],
    }),
    t('Agora apaga o cupão FDS10. Sim, confirmo já que é para apagar.', {
      operations: [op('manage_promotions', completed, { operation: 'delete' })],
      writes: [call('delete_promotion')],
      reply: ['apagad|eliminad'],
    })),

  scenario('mix-owner-mixed-ready-and-blocked-stock-and-category', 'owner', ['menu', 'stock', 'batch', 'long'],
    t('Marca o Pudim como esgotado, marca o Brigadeiro como esgotado e esconde a categoria Menus.', {
      writes: [
        call('update_product_variant', { id: id(32), variantId: id(132), stock: 0 }),
        call('update_category', { id: id(4), visible: false }),
      ],
      menu: [
        menuEdit(32, 132, { stock: 0 }),
        { category: 4, patch: { visible: false } },
      ],
      reply: ['pudim', 'stock|painel', 'brigadeiro', 'menus'],
    }),
    t('Repõe o Brigadeiro com 17 unidades e volta a mostrar a categoria Menus.', {
      writes: [
        call('update_product_variant', { id: id(32), variantId: id(132), stock: 17 }),
        call('update_category', { id: id(4), visible: true }),
      ],
      menu: [
        menuEdit(32, 132, { stock: 17 }),
        { category: 4, patch: { visible: true } },
      ],
      reply: ['17', 'menus'],
    })),

  scenario('mix-owner-ambiguous-stock-plus-valid-price', 'owner', ['menu', 'stock', 'batch', 'long'],
    t('Marca o pastel como esgotado e muda o preço do Brigadeiro para 1,80 €.', {
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), price: 1.8 })],
      menu: [menuEdit(32, 132, { price: 1.8, original_price: 1.8 })],
      reply: ['1[,.]8', 'carne|queijo|frango'],
    }),
    t('Volta a pôr o preço e preço original do Brigadeiro a 1,50 €.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), price: 1.5, original_price: 1.5 })],
      menu: [menuEdit(32, 132, { price: 1.5, original_price: 1.5 })],
      reply: ['1[,.]5'],
    })),

  scenario('mix-owner-analytics-margins-plus-price-update', 'owner', ['backoffice', 'menu', 'long'],
    t('Mostra as margens por produto de 1 a 7 de novembro de 2026 e aumenta o Pastel de Carne para 5,60 €.', {
      calls: [call('get_product_margins', { start_date: '2026-11-01', end_date: '2026-11-07' })],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), price: 5.6 })],
      menu: [menuEdit(11, 111, { price: 5.6, original_price: 5.6 })],
      reply: ['pastel de carne', '5[,.]6'],
    }),
    t('Repõe o preço e preço original do Pastel de Carne para 5,20 €.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), price: 5.2, original_price: 5.2 })],
      menu: [menuEdit(11, 111, { price: 5.2, original_price: 5.2 })],
      reply: ['5[,.]2'],
    })),

  scenarioWithFixture('mix-owner-takeaway-order-blocked-rider-plus-valid-coupon', 'owner', ['orders', 'delivery', 'promotions', 'short'],
    {
      orders: [{
        id: id(301), public_id: 'PT-EVAL101', daily_id: 1, service_type: 'TAKEAWAY', status: 'PREPARING',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 15.0,
        payments: [], discounts: [],
      }],
    },
    t('No pedido PT-EVAL101, atribui o estafeta Rui Lopes e aplica o cupão BALCAO10.', {
      forbidCalls: ['assign_rider'],
      writes: [call('apply_order_coupon', { id: id(301), coupon_code: 'BALCAO10' })],
      reply: ['takeaway|levant|entrega', 'balcao10'],
    })),

  scenarioWithFixture('mix-delivery-distance-pricing-mode', 'customer', ['delivery', 'maps', 'short'],
    {
      pricing: { mode: 'DISTANCE', pricing_type: 'DISTANCE', type: 'DISTANCE', price_per_km: 0.8, base_price: 1.5 },
    },
    t('Quanto custa a entrega para a Av. Cristo Rei, 47, Corroios?', {
      calls: [call('get_delivery_pricing'), call('get_delivery_quote')],
      reply: ['2[,.]5|€|entrega'],
    })),

  scenarioWithFixture('mix-clients-pagination-over-25', 'owner', ['clients', 'short'],
    {
      clients: Array.from({ length: 27 }, (_, idx) => ({
        id: id(220 + idx),
        name: `Cliente Teste ${idx + 1}`,
        phone_number: `910001${String(idx).padStart(3, '0')}`,
        country_calling_code: '351',
        email: `cliente${idx + 1}@example.test`,
      })),
    },
    t('Quantos clientes temos registados no total? Verifica as páginas se for preciso.', {
      calls: [call('get_clients')],
      reply: ['27'],
    })),

  scenario('mix-offer-allergen-filter-and-draft', 'customer', ['menu', 'offers', 'allergens', 'long'],
    t('Mostra-me as sobremesas numa lista numerada e diz-me se alguma tem leite.', {
      calls: [call('get_menu')],
      offer: [31, 32],
      reply: ['pudim', 'brigadeiro', 'leite'],
    }),
    t('Quero 1 da segunda opção para levar, ainda não envies.', {
      draft: draft([item(32, 1)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['brigadeiro', '1[,.]5'],
    })),

  scenario('mix-two-variants-same-product-plus-menu-student', 'customer', ['draft', 'menu', 'long'],
    t('Quero um Menu Estudante com carne, alho e Guaraná, mais 1 lata de Guaraná e 1 garrafa de 1 L de Guaraná à parte, para levar. Ainda não envies.', {
      draft: draft([item(41, 1), item(21, 1, 121), item(21, 1, 127)], [], {
        service: 'TAKEAWAY', exactMissing: true, selections: ['Carne', 'Alho', 'Guaraná'],
      }),
      reply: ['8[,.]5', '2[,.]1', '3[,.]7'],
    })),

  scenario('mix-category-expansion-payment-check-and-checkout', 'customer', ['draft', 'payments', 'orders', 'long'],
    t('Quero uma unidade de cada sobremesa disponível para levar, e que formas de pagamento aceitam ao levantar?', {
      calls: [call('get_menu'), call('list_payment_methods')],
      draft: draft([item(31, 1), item(32, 1)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['pudim', 'brigadeiro', 'numerário|dinheiro', 'cartão'],
      exclude: ['mb[ -]*way'],
    }),
    t('Confirmo, envia já o pedido e pago com cartão no balcão.', {
      operations: [op('create_order', completed)],
      writes: [
        call('create_order', { service_type: 'TAKEAWAY' }),
        call('add_order_combos', { combos: [{ variant_id: id(131), quantity: 1 }, { variant_id: id(132), quantity: 1 }] }),
        call('update_order_status', { status: 'PENDING' }),
      ],
      reply: ['pt-eval105'],
    })),

  scenario('mix-maps-poi-payment-methods-and-draft', 'customer', ['maps', 'delivery', 'payments', 'draft', 'short'],
    t('Quero 2 Pastéis de Carne para entregar na Estação de Corroios. Aceitam MB WAY e quanto custa a entrega? Ainda não envies.', {
      calls: [call('list_payment_methods')],
      reply: ['estação|corroios', 'mb[ -]*way', '2[,.]5'],
      exclude: ['pedido (confirmado|enviado)'],
    })),

  scenario('mix-maps-missing-door-then-complete-then-quote', 'customer', ['maps', 'delivery', 'long'],
    t('Quanto custa a entrega para a Avenida Cristo Rei em Corroios?', {
      ...question('número|porta'),
    }),
    t('É o número 47.', {
      reply: ['47', 'cristo rei', '2[,.]5'],
    })),

  scenario('mix-maps-subpremise-cash-change-delivery-checkout', 'customer', ['maps', 'delivery', 'payments', 'orders', 'short'],
    t('Envia já 1 Pastel de Carne para a Av. Cristo Rei, 47, 3º Esq, campainha Silva, Corroios, pago em dinheiro com troco para 20 €.', {
      operations: [op('create_order', completed)],
      writes: [
        call('create_order', { service_type: 'DELIVERY' }),
        call('add_order_combos', { combos: [{ variant_id: id(111), quantity: 1 }] }),
        call('update_order_status', { status: 'PENDING' }),
      ],
      reply: ['pt-eval105', '20'],
    })),

  scenario('mix-delivery-out-of-coverage-switch-to-takeaway', 'customer', ['delivery', 'draft', 'orders', 'long'],
    t('Quero 2 Pastéis de Carne para entrega no distrito de Amora.', {
      calls: [call('get_delivery_pricing')],
      reply: ['fora|cobertura|não entreg'],
      exclude: ['grátis|gratuit'],
    }),
    t('Então passo aí para levantar, envia já o pedido.', {
      operations: [op('create_order', completed)],
      writes: [
        call('create_order', { service_type: 'TAKEAWAY' }),
        call('add_order_combos', { combos: [{ variant_id: id(111), quantity: 2 }] }),
        call('update_order_status', { status: 'PENDING' }),
      ],
      reply: ['pt-eval105'],
    })),

  scenario('mix-schedule-weekend-menu-student-switch-weekday', 'customer', ['draft', 'dates', 'long'],
    t('Quero um Menu Estudante com carne, alho e Guaraná para domingo 29 de novembro de 2026.', {
      reply: ['segunda|sexta|disponível|domingo'],
    }),
    t('Então marca para segunda-feira 30 de novembro de 2026, para levar, ainda não envies.', {
      draft: draft([item(41, 1)], [], { service: 'TAKEAWAY', exactMissing: true, selections: ['Carne', 'Alho', 'Guaraná'] }),
      reply: ['30', 'segunda'],
    })),

  scenario('mix-allergy-milk-remove-pudim-keep-agua', 'customer', ['draft', 'allergens', 'long'],
    t('Quero 1 Pudim e 1 Água para levar.', {
      draft: draft([item(31, 1), item(23, 1)], [], { service: 'TAKEAWAY', exactMissing: true }),
      reply: ['pudim', 'água'],
    }),
    t('Atenção, tenho alergia ao leite! Tira o que tiver leite e mantém o resto em rascunho.', {
      draft: draft([item(23, 1)], ['allergy_review'], { service: 'TAKEAWAY' }),
      reply: ['pudim', 'leite', 'água'],
    })),

  scenario('mix-owner-order-lookup-add-combo-and-advance', 'owner', ['orders', 'long'],
    t('Vê o estado do pedido PT-EVAL101.', {
      operations: [op('check_order_status', completed)],
      calls: [call('get_order', { id: id(301) })],
      reply: ['prepar'],
    }),
    t('Adiciona 1 Água ao pedido PT-EVAL101 e marca-o como pronto.', {
      writes: [
        call('add_order_combos', { id: id(301), combos: [{ variant_id: id(123), quantity: 1 }] }),
        call('update_order_status', { id: id(301), status: 'READY' }),
      ],
      reply: ['água', 'pronto'],
    })),

  scenario('mix-owner-order-discount-add-and-remove', 'owner', ['orders', 'long'],
    t('Aplica um desconto manual de 2,00 € no pedido PT-EVAL101.', {
      writes: [call('add_order_discount', { id: id(301) })],
      reply: ['desconto|2'],
    }),
    t('Remove esse desconto do pedido PT-EVAL101.', {
      writes: [call('remove_order_discount', { id: id(301) })],
      reply: ['remov|desconto'],
    })),

  scenario('mix-owner-payment-add-remove-and-cancel', 'owner', ['orders', 'payments', 'long'],
    t('Regista um pagamento de 5,00 € em numerário no pedido PT-EVAL101.', {
      operations: [op('register_payment', completed)],
      writes: [call('add_order_payment', { id: id(301), amount: 5 })],
      reply: ['5'],
    }),
    t('Remove esse pagamento e cancela o pedido PT-EVAL101 por erro de registo.', {
      writes: [
        call('remove_order_payment', { id: id(301) }),
        call('cancel_order', { id: id(301) }),
      ],
      reply: ['cancelad'],
    })),

  scenario('mix-owner-client-create-address-and-orders', 'owner', ['clients', 'backoffice', 'short'],
    t('Cria o cliente João Mendes (+351 913334445), guarda-lhe a morada Rua Nova 5, Corroios, e lista os pedidos prontos.', {
      calls: [call('get_orders')],
      writes: [
        call('create_client', { name: 'João Mendes', phone_number: '913334445', country_calling_code: '351' }),
        call('create_address'),
      ],
      reply: ['joão mendes', 'rua nova', 'pt-eval102'],
    })),

  scenario('mix-owner-client-disambiguate-then-add-address', 'owner', ['clients', 'backoffice', 'long'],
    t('Procura a cliente Ana para lhe guardar uma morada.', {
      calls: [call('get_clients', { filter_name: 'Ana' })],
      ...question('silva', 'sousa'),
    }),
    t('É a Ana Sousa. Guarda a morada Rua Central 12, Corroios.', {
      writes: [call('create_address', { client_id: id(212) })],
      reply: ['ana sousa', 'rua central'],
    })),

  scenario('mix-owner-promo-product-specific-and-pause', 'owner', ['promotions', 'menu', 'long'],
    t('Cria o cupão CARNE10 de 10% só para o Pastel de Carne, mínimo 5 €, limite 10 usos, de 2026-11-01 a 2026-12-31, ativo.', {
      calls: [call('get_menu')],
      writes: [call('create_promotion', { coupon_code: 'CARNE10', discount_value: 10 })],
      reply: ['carne10', 'pastel de carne'],
    }),
    t('Pausa o cupão CARNE10.', {
      writes: [call('update_promotion', { published: false })],
      reply: ['pausad|desativad'],
    })),

  scenario('mix-owner-promo-update-discount-and-date', 'owner', ['promotions', 'short'],
    t('Muda o desconto do BALCAO10 para 20% e estende a validade até 2031-12-31.', {
      operations: [op('manage_promotions', completed, { operation: 'update', promotion_id: id(501) })],
      writes: [call('update_promotion', { id: id(501), discount_value: 20, valid_until: '2031-12-31' })],
      reply: ['20', '2031'],
    })),

  scenario('mix-owner-bulk-category-price-and-hide-restore', 'owner', ['menu', 'batch', 'long'],
    t('Aumenta todas as Sobremesas em 0,50 € e esconde a categoria Sobremesas.', {
      writes: [
        call('update_product_variant', { id: id(31), variantId: id(131), price: 3.75 }),
        call('update_product_variant', { id: id(32), variantId: id(132), price: 2 }),
        call('update_category', { id: id(3), visible: false }),
      ],
      menu: [
        menuEdit(31, 131, { price: 3.75, original_price: 3.75 }),
        menuEdit(32, 132, { price: 2, original_price: 2 }),
        { category: 3, patch: { visible: false } },
      ],
      reply: ['sobremesas', 'escondid'],
    }),
    t('Volta a mostrar Sobremesas e repõe o Pudim a 3,25 € e o Brigadeiro a 1,50 € (preço e preço original).', {
      writes: [
        call('update_category', { id: id(3), visible: true }),
        call('update_product_variant', { id: id(31), variantId: id(131), price: 3.25, original_price: 3.25 }),
        call('update_product_variant', { id: id(32), variantId: id(132), price: 1.5, original_price: 1.5 }),
      ],
      menu: [
        { category: 3, patch: { visible: true } },
        menuEdit(31, 131, { price: 3.25, original_price: 3.25 }),
        menuEdit(32, 132, { price: 1.5, original_price: 1.5 }),
      ],
      reply: ['3[,.]25', '1[,.]5'],
    })),

  scenario('mix-owner-promo-price-and-oos-same-item-restore', 'owner', ['menu', 'stock', 'long'],
    t('Mete o Pastel de Carne em promoção a 4,50 € e marca-o como esgotado.', {
      writes: [
        call('update_product_variant', { id: id(11), variantId: id(111), price: 4.5 }),
        call('update_product_variant', { id: id(11), variantId: id(111), stock: 0 }),
      ],
      menu: [menuEdit(11, 111, { price: 4.5, stock: 0 })],
      reply: ['4[,.]5', 'esgotad'],
    }),
    t('Repõe o stock do Pastel de Carne para 13 e termina a promoção para voltar a 5,20 €.', {
      writes: [
        call('update_product_variant', { id: id(11), variantId: id(111), stock: 13 }),
        call('update_product_variant', { id: id(11), variantId: id(111), price: 5.2 }),
      ],
      menu: [menuEdit(11, 111, { price: 5.2, stock: 13 })],
      reply: ['13', '5[,.]2'],
    })),

  scenario('mix-owner-rider-assign-unassign-reassign', 'owner', ['delivery', 'long'],
    t('Remove o estafeta do pedido PT-EVAL102.', {
      writes: [call('unassign_rider', { id: id(302) })],
      reply: ['remov|desatribu'],
    }),
    t('Volta a atribuir o Rui Lopes ao pedido PT-EVAL102.', {
      calls: [call('list_users', { role: 'rider', active: true })],
      writes: [call('assign_rider', { id: id(302), user_id: id(411) })],
      reply: ['rui lopes'],
    })),

  scenario('mix-owner-delivery-status-full-progression', 'owner', ['delivery', 'long'],
    t('Marca o pedido PT-EVAL102 como a caminho para entrega.', {
      writes: [call('update_delivery_status', { id: id(302), delivery_status: 'DELIVERING' })],
      reply: ['caminho|entrega'],
    }),
    t('Agora marca o PT-EVAL102 como chegou ao destino e depois como entregue.', {
      orderedWrites: true,
      writes: [
        call('update_delivery_status', { id: id(302), delivery_status: 'ARRIVED_AT_DELIVERY' }),
        call('update_delivery_status', { id: id(302), delivery_status: 'DELIVERED' }),
      ],
      reply: ['chegou|chegad', 'entregue'],
    })),

  scenario('mix-owner-sales-source-payments-conversion', 'owner', ['backoffice', 'short'],
    t('Dá-me as vendas por origem, top meios de pagamento e conversão do menu de 1 a 7 de novembro de 2026.', {
      calls: [
        call('get_orders_by_source', { start_date: '2026-11-01', end_date: '2026-11-07' }),
        call('get_top_payment_methods', { start_date: '2026-11-01', end_date: '2026-11-07' }),
        call('get_menu_conversion', { start_date: '2026-11-01', end_date: '2026-11-07' }),
      ],
      reply: ['numerário|api|100'],
    })),

  scenario('mix-owner-ops-dashboard-hours-apps-riders', 'owner', ['company', 'delivery', 'short'],
    t('Diz-me se a loja e a Uber Eats estão abertas e quais os estafetas ativos.', {
      calls: [call('get_company'), call('get_store_status'), call('list_users', { role: 'rider', active: true })],
      reply: ['abert', 'uber eats', 'fechad', 'rui lopes'],
    })),

  scenario('mix-owner-blocked-sales-plus-ready-orders', 'owner', ['backoffice', 'orders', 'batch', 'short'],
    t('Dá-me as vendas de 2026-11-10 até 2026-11-01 e lista os pedidos prontos para entrega.', {
      forbidCalls: ['get_orders_summary'],
      calls: [call('get_orders')],
      reply: ['data|anterior|posterior', 'pt-eval102'],
    })),
];

