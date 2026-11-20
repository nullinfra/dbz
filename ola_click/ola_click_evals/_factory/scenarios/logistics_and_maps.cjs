const { id, completed, clarify, unsupported, op, call, question, t, scenario, scenarioWithFixture } = require('./helpers.cjs');

module.exports = [
  scenario('delivery-out-of-coverage-trap', 'customer', ['delivery', 'short'],
    t('Quanto custa a entrega para o distrito de Amora?', {
      operations: [op('quote_delivery', completed)],
      orderedCalls: [call('get_delivery_pricing')],
      reply: ['fora|cobertura|não entreg|não cobr'],
      exclude: ['grátis|gratuit|0[,.]00'],
    })),

  scenario('delivery-quote-missing-location', 'customer', ['delivery', 'short'],
    t('Quanto custa a entrega?', {
      ...question('morada|distrito|zona|onde'),
    })),

  scenario('delivery-quote-typo-district', 'customer', ['delivery', 'short'],
    t('Quanto custa a entrega para o distrito de Coroios?', {
      operations: [op('quote_delivery', completed)],
      calls: [call('get_delivery_pricing'), call('get_delivery_quote', { district_id: id(421) })],
      reply: ['corroios', '2[,.]5'],
    })),

  scenario('owner-assign-active-rider', 'owner', ['delivery', 'short'],
    t('Atribui o estafeta Rui Lopes ao pedido PT-EVAL102.', {
      operations: [op('assign_rider', completed)],
      calls: [call('list_users', { role: 'rider', active: true })],
      writes: [call('assign_rider', { id: id(302), user_id: id(411) })],
      reply: ['rui lopes', 'pt-eval102'],
    })),

  scenario('owner-assign-rider-first-name', 'owner', ['delivery', 'short'],
    t('Atribui o Rui ao pedido PT-EVAL102.', {
      operations: [op('assign_rider', completed)],
      calls: [call('list_users', { role: 'rider', active: true })],
      writes: [call('assign_rider', { id: id(302), user_id: id(411) })],
      reply: ['rui lopes', 'pt-eval102'],
    })),

  scenario('owner-assign-inactive-rider-blocked', 'owner', ['delivery', 'short'],
    t('Atribui a estafeta Sara Reis ao pedido PT-EVAL102.', {
      calls: [call('list_users')],
      forbidCalls: ['assign_rider'],
      reply: ['inativ|sara reis|não'],
    })),

  scenario('owner-assign-unknown-rider-blocked', 'owner', ['delivery', 'short'],
    t('Atribui o estafeta da OlaClick Carlos Silva ao pedido PT-EVAL102.', {
      calls: [call('list_users')],
      forbidCalls: ['assign_rider'],
      reply: ['não encontr|carlos silva'],
    })),

  scenarioWithFixture('owner-assign-olaclick-rider-pending-blocked', 'owner', ['delivery', 'short'],
    {
      orders: [{
        id: id(302), public_id: 'PT-EVAL102', daily_id: 2, service_type: 'DELIVERY', status: 'PENDING',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 10,
        payments: [], discounts: [],
      }],
    },
    t('Atribui o estafeta Rui Lopes ao pedido PT-EVAL102.', {
      forbidCalls: ['assign_rider'],
      reply: ['pending|pendente|não'],
    })),

  scenario('owner-assign-rider-takeaway-blocked', 'owner', ['delivery', 'short'],
    t('Atribui o estafeta Rui Lopes ao pedido PT-EVAL101.', {
      operations: [op('assign_rider', unsupported)],
      forbidCalls: ['assign_rider'],
      reply: ['takeaway|levant|entrega'],
    })),

  scenario('owner-unassign-rider', 'owner', ['delivery', 'short'],
    t('Remove o estafeta do pedido PT-EVAL102.', {
      operations: [op('assign_rider', completed)],
      writes: [call('unassign_rider', { id: id(302) })],
      reply: ['remov|desatribu|pt-eval102'],
    })),

  scenario('owner-delivery-status-arrived', 'owner', ['delivery', 'short'],
    t('Marca o pedido PT-EVAL102 como chegou ao destino.', {
      operations: [op('update_delivery_status', completed)],
      writes: [call('update_delivery_status', { id: id(302), delivery_status: 'ARRIVED_AT_DELIVERY' })],
      reply: ['chegou|destino|pt-eval102'],
    })),

  scenario('owner-delivery-status-delivered', 'owner', ['delivery', 'short'],
    t('Marca o pedido PT-EVAL102 como entregue.', {
      operations: [op('update_delivery_status', completed)],
      writes: [call('update_delivery_status', { id: id(302), delivery_status: 'DELIVERED' })],
      reply: ['entregue|pt-eval102'],
    })),

  scenarioWithFixture('owner-delivery-already-completed-guard', 'owner', ['delivery', 'short'],
    {
      orders: [{
        id: id(302), public_id: 'PT-EVAL102', daily_id: 2, service_type: 'DELIVERY', status: 'READY',
        delivery_status: 'DELIVERED', rider: { id: id(411), name: 'Rui Lopes', provider: 'olaclick' },
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 10,
        payments: [], discounts: [],
      }],
    },
    t('Volta a pôr o pedido PT-EVAL102 como a caminho para entrega.', {
      operations: [op('update_delivery_status', unsupported)],
      forbidCalls: ['update_delivery_status'],
      reply: ['entregue|delivered|já'],
    })),

  scenario('owner-report-rider-position-valid', 'owner', ['delivery', 'short'],
    t('Atualiza a posição do estafeta do pedido PT-EVAL102 para latitude 38.635 e longitude -9.152.', {
      operations: [op('report_rider_position', completed)],
      writes: [call('report_rider_position', { id: id(302), latitude: 38.635, longitude: -9.152 })],
      reply: ['posição|38[,.]635|pt-eval102'],
    })),

  scenario('owner-report-rider-position-invalid-coords', 'owner', ['delivery', 'short'],
    t('Atualiza a posição do estafeta do pedido PT-EVAL102 para latitude 95.0 e longitude -9.15.', {
      operations: [op('report_rider_position', clarify)],
      forbidCalls: ['report_rider_position'],
      reply: ['inválid|coordenadas|intervalo'],
    })),

  scenarioWithFixture('owner-report-rider-position-no-rider', 'owner', ['delivery', 'short'],
    {
      orders: [{
        id: id(302), public_id: 'PT-EVAL102', daily_id: 2, service_type: 'DELIVERY', status: 'READY',
        source: 'api', client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 10,
        payments: [], discounts: [],
      }],
    },
    t('Atualiza a posição do estafeta do pedido PT-EVAL102 para latitude 38.635 e longitude -9.152.', {
      operations: [op('report_rider_position', clarify)],
      forbidCalls: ['report_rider_position'],
      reply: ['estafeta|não tem'],
    })),
];
