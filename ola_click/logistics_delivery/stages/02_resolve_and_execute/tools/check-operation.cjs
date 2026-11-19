const { present, nonblank, uuid, coordinates } = require('../../../../_shared/tools/preflight-values.cjs');

const statuses = new Set([
  'DELIVERY_PENDING', 'REQUESTING_RIDER', 'RIDER_ASSIGNED', 'RIDER_NOT_FOUND', 'REQUEST_FAILED',
  'ON_THE_WAY_TO_PICK_UP', 'AT_PICK_UP_PLACE', 'DELIVERING', 'ARRIVED_AT_DELIVERY',
  'DELIVERED', 'CANCELED', 'DELIVERY_ISSUE',
]);

module.exports = function check({ intent, entities: e }, add) {
  if (intent === 'quote_delivery') {
    if (present(e.coordinates) && !coordinates(e.coordinates.lat, e.coordinates.lng)) {
      add('coordinates', 'Preciso de uma latitude e longitude válidas para calcular a entrega.');
    }
    if (present(e.district_id) && !uuid(e.district_id)) {
      add('district_id', 'Qual é a zona de entrega configurada?');
    }
    if (nonblank(e.delivery_address) && !present(e.coordinates) && !present(e.district_id)) {
      add('delivery_address', 'Preciso de confirmar a localização ou a zona de entrega para calcular o preço dessa morada.');
    }
  }
  if (intent === 'assign_rider') {
    if (e.unassign === true) {
      if ([e.rider_name, e.rider_id, e.rider_phone].some(present)) {
        add('rider', 'Queres retirar o estafeta atual ou atribuir outro?');
      }
      return;
    }
    if (!nonblank(e.rider_name)) add('rider_name', 'Qual é o nome do estafeta?');
    if (e.provider === 'olaclick' && !uuid(e.rider_id)) {
      add('rider_id', 'Qual é o estafeta ativo da OlaClick? Consulta a lista de estafetas antes de o atribuir.');
    }
    if (present(e.rider_id) && !uuid(e.rider_id) && e.provider !== 'olaclick') {
      add('rider_id', 'O identificador do estafeta tem de ser um UUID.');
    }
  }
  if (intent === 'update_delivery_status' && !statuses.has(e.delivery_status)) {
    add('delivery_status', 'Qual é o novo estado da entrega?');
  }
  if (intent === 'report_rider_position' && !coordinates(e.latitude, e.longitude)) {
    add('coordinates', 'Preciso da latitude e da longitude válidas da posição do estafeta.');
  }
};
