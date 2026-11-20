const { id, completed, clarify, unsupported, op, call, question, t, scenario } = require('./helpers.cjs');

module.exports = [
  scenario('owner-create-promo-success', 'owner', ['promotions', 'short'],
    t('Cria o cupão NATAL15 de 15% desconto, mínimo 10 €, limite 20 usos, válido de 2026-12-01 até 2026-12-31, ativo.', {
      operations: [op('manage_promotions', completed, { operation: 'create' })],
      writes: [call('create_promotion', { coupon_code: 'NATAL15', discount_value: 15 })],
      reply: ['natal15', '15'],
    })),

  scenario('owner-create-promo-invalid-dates', 'owner', ['promotions', 'validation', 'short'],
    t('Cria o cupão NATAL20 de 20% desconto, mínimo 10 €, limite 50 usos, válido de 2026-12-25 até 2026-12-01, ativo.', {
      operations: [op('manage_promotions', clarify)],
      forbidCalls: ['create_promotion'],
      reply: ['data|valid|anterior|posterior|inválid'],
    })),

  scenario('owner-create-promo-invalid-percentage', 'owner', ['promotions', 'validation', 'short'],
    t('Cria o cupão ERRO150 de 150% desconto, mínimo 10 €, limite 10 usos, válido de 2026-12-01 até 2026-12-31, ativo.', {
      forbidCalls: ['create_promotion'],
      reply: ['100|percent|inválid'],
    })),

  scenario('owner-create-promo-missing-details', 'owner', ['promotions', 'short'],
    t('Cria um cupão chamado VERAO10 com 10% de desconto.', {
      operations: [op('manage_promotions', clarify)],
      forbidCalls: ['create_promotion'],
      ...question('data|valid|mínimo|limite'),
    })),

  scenario('owner-create-promo-duplicate-code', 'owner', ['promotions', 'short'],
    t('Cria um cupão com código BALCAO10 de 15% desconto, mínimo 5 €, limite 10 usos, de 2026-11-01 a 2026-12-31, ativo.', {
      forbidCalls: ['create_promotion'],
      reply: ['já existe|duplicad|balcao10'],
    })),

  scenario('owner-create-promo-missing-product', 'owner', ['promotions', 'menu', 'short'],
    t('Cria um cupão BACALHAU10 de 10% só para o Pastel de Bacalhau, mínimo 5 €, limite 10 usos, de 2026-11-01 a 2026-12-31, ativo.', {
      forbidCalls: ['create_promotion'],
      reply: ['bacalhau|não encontr|catálogo'],
    })),

  scenario('owner-pause-promotion', 'owner', ['promotions', 'short'],
    t('Pausa o cupão BALCAO10 sem o apagar.', {
      operations: [op('manage_promotions', completed, { operation: 'update', promotion_id: id(501) })],
      writes: [call('update_promotion', { id: id(501), published: false })],
      reply: ['pausad|desativad|balcao10'],
    })),

  scenario('owner-update-promo-extend-valid-until', 'owner', ['promotions', 'short'],
    t('Estende a validade do cupão BALCAO10 até 2030-12-31.', {
      operations: [op('manage_promotions', completed, { operation: 'update', promotion_id: id(501) })],
      writes: [call('update_promotion', { id: id(501), valid_until: '2030-12-31' })],
      reply: ['2030', 'balcao10'],
    })),

  scenario('owner-delete-promotion-destructive-gate', 'owner', ['promotions', 'gates', 'short'],
    t('Apaga permanentemente o cupão BALCAO10.', {
      forbidCalls: ['delete_promotion'],
      ...question('confirm|certeza|apagar'),
    })),

  scenario('owner-delete-promotion-confirmed', 'owner', ['promotions', 'gates', 'long'],
    t('Apaga permanentemente o cupão BALCAO10.', {
      forbidCalls: ['delete_promotion'],
      ...question('confirm|certeza|apagar'),
    }),
    t('Sim, confirmo que podes apagar o cupão BALCAO10.', {
      operations: [op('manage_promotions', completed, { operation: 'delete', promotion_id: id(501) })],
      writes: [call('delete_promotion', { id: id(501) })],
      reply: ['apagad|eliminad|balcao10'],
    })),

  scenario('owner-filter-promos-service-type', 'owner', ['promotions', 'short'],
    t('Que cupões ativos temos para takeaway?', {
      operations: [op('manage_promotions', completed)],
      calls: [call('get_active_promotions')],
      reply: ['balcao10'],
    })),

  scenario('owner-sales-invalid-date-range', 'owner', ['backoffice', 'validation', 'short'],
    t('Mostra o resumo de vendas de 2026-11-10 até 2026-11-01.', {
      operations: [op('sales_summary', clarify)],
      forbidCalls: ['get_orders_summary'],
      reply: ['data|anterior|posterior|intervalo'],
    })),

  scenario('owner-sales-by-hour-and-margins', 'owner', ['backoffice', 'short'],
    t('Dá-me as vendas por hora e as margens de 1 a 7 de novembro de 2026.', {
      calls: [
        call('get_sales_by_hour', { start_date: '2026-11-01', end_date: '2026-11-07' }),
        call('get_margins_summary', { start_date: '2026-11-01', end_date: '2026-11-07' }),
      ],
      reply: ['28[,.]4|16[,.]4'],
    })),

  scenario('owner-sales-by-day-and-service-type', 'owner', ['backoffice', 'short'],
    t('Dá-me as vendas por dia e por tipo de serviço de 1 a 7 de novembro de 2026.', {
      calls: [
        call('get_sales_by_day', { start_date: '2026-11-01', end_date: '2026-11-07' }),
        call('get_orders_by_service_type', { start_date: '2026-11-01', end_date: '2026-11-07' }),
      ],
      reply: ['takeaway|28[,.]4'],
    })),

  scenario('owner-sales-cashier-balances', 'owner', ['backoffice', 'short'],
    t('Mostra o saldo dos caixas de 1 a 7 de novembro de 2026.', {
      operations: [op('sales_summary', completed)],
      calls: [call('list_cashiers'), call('list_cashier_balances')],
      reply: ['caixa|28[,.]4'],
    })),

  scenario('owner-list-active-orders-filtered', 'owner', ['backoffice', 'orders', 'short'],
    t('Lista os pedidos de entrega que estão prontos.', {
      operations: [op('list_active_orders', completed)],
      calls: [call('get_orders')],
      reply: ['pt-eval102'],
    })),

  scenario('owner-manage-customer-address', 'owner', ['backoffice', 'clients', 'short'],
    t('Guarda a morada Rua da Liberdade 10, Corroios para a cliente Ana Silva.', {
      operations: [op('manage_customer_address', completed)],
      writes: [call('create_address', { client_id: id(211) })],
      reply: ['ana silva|morada|guardad|registad'],
    })),

  scenario('company-full-hours-and-address', 'customer', ['company', 'short'],
    t('Qual é a vossa morada e o horário de sexta-feira?', {
      operations: [op('get_company', completed)],
      calls: [call('get_company')],
      reply: ['corroios', '12:00', '22:00'],
    })),

  scenario('company-payment-methods-takeaway', 'customer', ['company', 'payments', 'short'],
    t('Para levantamento no balcão, que formas de pagamento aceitam?', {
      operations: [op('list_payment_methods', completed, { service_type: 'TAKEAWAY' })],
      calls: [call('list_payment_methods')],
      reply: ['numerário|dinheiro', 'cartão'],
      exclude: ['mb[ -]*way'],
    })),

  scenario('owner-inactive-riders', 'owner', ['company', 'delivery', 'short'],
    t('Quais são os estafetas inativos?', {
      operations: [op('list_users', completed, { role: 'rider', active: false })],
      calls: [call('list_users', { role: 'rider', active: false })],
      reply: ['sara reis'],
      exclude: ['rui lopes'],
    })),

  scenario('owner-create-staff-unsupported', 'owner', ['company', 'gates', 'short'],
    t('Cria uma conta de estafeta para o João Costa.', {
      operations: [op('unsupported_request', unsupported)],
      reply: ['painel|não|ger|utilizador'],
    })),

  scenario('owner-client-not-found', 'owner', ['clients', 'short'],
    t('Procura o cliente Zé Ninguém.', {
      calls: [call('get_clients', { filter_name: 'Zé Ninguém' })],
      reply: ['não encontr|nenhum'],
    })),

  scenario('owner-client-search-by-phone', 'owner', ['clients', 'short'],
    t('Quem tem o telefone 910000102?', {
      calls: [call('get_clients', { filter_phone_number: '910000102' })],
      reply: ['ana sousa'],
    })),

  scenario('owner-create-client-success', 'owner', ['clients', 'short'],
    t('Cria um cliente chamado Pedro Lima com telefone +351 912345678 e email pedro.lima@example.test.', {
      operations: [op('create_client', completed)],
      writes: [call('create_client', { name: 'Pedro Lima', phone_number: '912345678', country_calling_code: '351' })],
      reply: ['pedro lima', 'criad|registad'],
    })),

  scenario('owner-update-client-duplicate-phone', 'owner', ['clients', 'short'],
    t('Muda o telefone da Ana Sousa para +351 910000101.', {
      reply: ['já existe|duplicad|ana silva|910[ ]*000[ ]*101'],
    })),
];
