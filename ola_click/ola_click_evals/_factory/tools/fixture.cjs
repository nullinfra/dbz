const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const os = require('node:os');
const { randomUUID } = require('node:crypto');
const { execFileSync } = require('node:child_process');

const id = number => `00000000-0000-4000-8000-${String(number).padStart(12, '0')}`;
const category = (number, name) => ({ id: id(number), name, position: number, visible: true, type: 'PRODUCT' });
const variant = (number, price, stock, name = 'Única') => ({
  id: id(number), name, price, original_price: price, currency: 'EUR', sku: `EVAL-${number}`,
  stock, stock_threshold: 2, packaging_price: 0, position: number, visible: true,
});
const product = (number, name, description, categoryNumber, variants, stock_enabled = true) => ({
  id: id(number), category_id: id(categoryNumber), name, description, variants, stock_enabled,
  position: number, visible: true, modifier_category_ids: [], modifier_categories: [],
});

const menu = {
  categories: [category(1, 'Pastéis'), category(2, 'Bebidas'), category(3, 'Sobremesas'), category(4, 'Menus'), category(5, 'Congelados')],
  products: [
    product(11, 'Pastel de Carne', 'Pastel frito com recheio de carne de vaca.', 1, [variant(111, 5.2, 13)]),
    product(12, 'Pastel de Queijo', 'Vegetariano. Recheio de queijo. Contém leite e trigo.', 1, [variant(112, 4.8, 14)]),
    product(13, 'Pastel de Camarão', 'Recheio de camarão. Contém crustáceos e trigo.', 1, [variant(113, 6.5, 0)]),
    product(14, 'Pastel de Frango', 'Recheio de frango.', 1, [variant(114, 5.4, 11)]),
    product(21, 'Guaraná', 'O formato lata de 330 ml é elegível nos menus.', 2,
      [variant(121, 2.1, 24, 'Lata 330 ml'), variant(127, 3.7, 9, 'Garrafa 1 L')]),
    product(22, 'Coca-Cola', 'Lata de 330 ml, elegível nos menus.', 2, [variant(122, 2.2, 18, 'Lata 330 ml')]),
    product(23, 'Água', 'Garrafa de água de 500 ml.', 2, [variant(123, 1.2, 20)]),
    product(31, 'Pudim', 'Pudim de leite.', 3, [variant(131, 3.25, 5)], false),
    product(32, 'Brigadeiro', 'Chocolate e leite condensado.', 3, [variant(132, 1.5, 17)]),
    product(41, 'Menu Estudante', 'Inclui uma porção de batatas. Escolhe 1 pastel (Carne ou Queijo), 1 molho (Alho ou Picante) e 1 lata de 330 ml (Guaraná ou Coca-Cola). Disponível de segunda a sexta.', 4, [variant(141, 8.5, 16)]),
    product(51, 'Pastel de Carne Congelado', 'Vendido congelado, para fritar em casa.', 5, [variant(151, 4, 12)]),
    { ...product(52, 'Rascunho Interno', 'Produto escondido.', 5, [variant(152, 99, 1)]), visible: false },
  ],
};

const clients = [
  { id: id(211), name: 'Ana Silva', phone_number: '910000101', country_calling_code: '351', email: 'ana.silva@example.test' },
  { id: id(212), name: 'Ana Sousa', phone_number: '910000102', country_calling_code: '351', email: 'ana.sousa@example.test' },
];
const order = (number, public_id, service_type, status) => ({
  id: id(number), public_id, daily_id: number - 300, service_type, status, source: 'api',
  client_id: id(211), customer_name: 'Ana Silva', combos: [], items: [], total: 0, payments: [], discounts: [],
});
const paymentMethods = [
  { id: id(401), name: 'Numerário', type: 'CASH', service_types: ['TAKEAWAY', 'DELIVERY', 'ONSITE'], active: true },
  { id: id(402), name: 'Cartão no balcão', type: 'CARD', service_types: ['TAKEAWAY', 'ONSITE'], active: true },
  { id: id(403), name: 'MB WAY', type: 'OTHER', service_types: ['DELIVERY'], active: true },
];
const users = [
  { id: id(411), name: 'Rui Lopes', role: 'rider', active: true },
  { id: id(412), name: 'Sara Reis', role: 'rider', active: false },
];
const promotions = [{
  id: id(501), name: 'Balcão 10', code: 'BALCAO10', coupon_code: 'BALCAO10', discount_type: 'PERCENTAGE',
  discount_value: 10, minimum_order_amount: 10, published: true, usage_limit: 30,
  valid_from: '2026-01-01', valid_until: '2029-12-31', service_types: ['TAKEAWAY'],
}];
const orders = [
  order(301, 'PT-EVAL101', 'TAKEAWAY', 'PREPARING'),
  { ...order(302, 'PT-EVAL102', 'DELIVERY', 'READY'), rider: { id: id(411), name: 'Rui Lopes', provider: 'olaclick' } },
];
const byId = (records, key) => records.find(record => record.id === key);
const paginate = (records, args, defaultSize = 25) => {
  const page = args.page ?? 1;
  const size = args.per_page ?? defaultSize;
  const end = page * size;
  return { data: records.slice(end - size, end), pagination: {
    current_page: page, per_page: size, total: records.length, has_more: end < records.length,
  } };
};

function publicMenu(state) {
  return state.categories.filter(group => group.visible).map(group => ({
    ...group,
    products: state.products.filter(item => item.visible && item.category_id === group.id).map(item => ({
      ...item, available: !item.stock_enabled || item.variants.some(option => option.stock > 0),
      price: Math.min(...item.variants.map(option => option.price)),
      is_available: !item.stock_enabled || item.variants.some(option => option.stock > 0),
    })),
  }));
}

function handler(state, name, args) {
  const item = byId(state.menu.products, args.product_id ?? args.id);
  const option = item && byId(item.variants, args.variant_id ?? args.variantId);
  const group = byId(state.menu.categories, args.category_id ?? args.id);
  const client = byId(state.clients, args.id);
  const currentOrder = byId(state.orders, args.id);
  const promotion = byId(state.promotions, args.id ?? args.promotion_id);
  const patch = (resource, fields) => {
    if (!resource) return undefined;
    for (const field of fields) {
      if (Object.hasOwn(args, field)) resource[field] = args[field];
    }
    return resource;
  };
  const result = (data, extra) => data === undefined ? undefined : { data, ...extra };
  switch (name) {
    case 'get_menu': {
      const categories = publicMenu(state.menu);
      return { data: categories, categories };
    }
    case 'list_categories': return result(state.menu.categories);
    case 'get_category': return result(group);
    case 'list_products': return paginate(state.menu.products.filter(entry =>
      !args.category_id || entry.category_id === args.category_id), args);
    case 'get_product': return result(item);
    case 'list_product_variants': return result(item?.variants);
    case 'list_modifier_categories': return result([]);
    case 'update_product': return result(patch(item, ['name', 'description']));
    case 'update_product_variant': return result(patch(option,
      ['price', 'original_price', 'stock', 'stock_threshold', 'packaging_price', 'name', 'position']));
    case 'update_product_position': return result(patch(item, ['position']));
    case 'create_category': {
      if (state.menu.categories.some(entry => entry.name.toLowerCase() === String(args.name ?? '').toLowerCase())) {
        throw { type: 'category_already_exists', status: 422, detail: 'Já existe uma categoria com este nome.' };
      }
      const created = category(state.menu.categories.length + 10, args.name);
      state.menu.categories.push(created);
      return result(created);
    }
    case 'delete_category': {
      const catId = args.categoryId ?? args.id;
      const idx = state.menu.categories.findIndex(entry => entry.id === catId);
      if (idx < 0) return undefined;
      if (state.menu.products.some(entry => entry.category_id === catId)) {
        throw { type: 'category_not_empty', status: 422, detail: 'A categoria ainda tem produtos.' };
      }
      const [removed] = state.menu.categories.splice(idx, 1);
      return result(removed);
    }
    case 'create_product': {
      if (state.menu.products.some(entry => entry.name.toLowerCase() === String(args.name ?? '').toLowerCase())) {
        throw { type: 'product_already_exists', status: 422, detail: 'Já existe um produto com este nome.' };
      }
      const num = state.menu.products.length + 60;
      const catNum = Number(String(args.category_id ?? '').slice(-4)) || 1;
      const created = product(num, args.name, args.description ?? '', catNum,
        [variant(num + 100, Number(args.price ?? 0), 10)], true);
      created.category_id = args.category_id ?? id(1);
      state.menu.products.push(created);
      return result(created);
    }
    case 'create_product_variant': {
      if (!item) return undefined;
      const vNum = item.variants.length + 200;
      const created = variant(vNum, Number(args.price ?? 0), Number(args.stock ?? 10), args.name ?? 'Nova');
      item.variants.push(created);
      return result(created);
    }
    case 'list_kitchens': return result([{ id: id(441), name: 'Cozinha Principal' }]);
    case 'list_tables': return result(state.tables);
    case 'list_webhooks': return result([]);
    case 'list_cashiers': return result([{ id: id(451), name: 'Caixa Principal', active: true }]);
    case 'list_cashier_balances': return result([{ cashier_id: id(451), total_cash: 28.4, total_card: 0 }]);
    case 'update_category': return result(patch(group, ['name', 'visible', 'position']));
    case 'get_company': return result(state.company);
    case 'get_store_status': return result(state.storeStatus);
    case 'list_payment_methods': return result(state.paymentMethods);
    case 'list_users': return paginate(users.filter(user =>
      (!args.role || args.role.split(',').includes(user.role)) &&
      (args.active === undefined || user.active === args.active)), args);
    case 'get_clients': return paginate(state.clients.filter(entry =>
      (!args.filter_name || entry.name.toLowerCase().includes(args.filter_name.toLowerCase())) &&
      (!args.filter_phone_number || entry.phone_number.startsWith(args.filter_phone_number)) &&
      (!args.filter_country_calling_code || entry.country_calling_code === args.filter_country_calling_code)), args);
    case 'get_client': return result(client);
    case 'update_client': {
      if (!client) return undefined;
      const nextPhone = args.phone_number ?? client.phone_number;
      const nextCode = args.country_calling_code ?? client.country_calling_code;
      if (state.clients.some(entry => entry.id !== client.id && entry.phone_number === nextPhone &&
          entry.country_calling_code === nextCode)) {
        throw { type: 'client_already_exists', status: 422, detail: 'Já existe outro cliente com este telefone.' };
      }
      return result(patch(client, ['name', 'phone_number', 'country_calling_code', 'email']));
    }
    case 'create_client': {
      if (state.clients.some(entry => entry.phone_number === args.phone_number &&
          entry.country_calling_code === args.country_calling_code)) {
        throw { type: 'client_already_exists', status: 422, detail: 'Já existe um cliente com este telefone.' };
      }
      const entry = { ...args, id: id(state.clients.length + 220) };
      state.clients.push(entry);
      return result(entry);
    }
    case 'create_address': {
      const targetClient = byId(state.clients, args.client_id);
      if (!targetClient) return undefined;
      const addr = { id: id(700 + (targetClient.addresses?.length ?? 0)), ...args };
      targetClient.addresses = [...(targetClient.addresses ?? []), addr];
      return result(addr);
    }
    case 'get_orders': return paginate(state.orders.filter(entry =>
      (!args.public_id || entry.public_id === args.public_id) &&
      (!args.status || args.status.includes(entry.status)) &&
      (!args.service_types || args.service_types.includes(entry.service_type)) &&
      (!args.service_type || args.service_type.includes(entry.service_type)) &&
      (!args.payment_status || entry.payment_status === args.payment_status)), args);
    case 'get_order': return result(currentOrder);
    case 'create_order': {
      if (args.idempotency_key && state.orderKeys.has(args.idempotency_key)) {
        return result(state.orderKeys.get(args.idempotency_key));
      }
      const number = state.orders.length + 303;
      const created = { ...order(number, `PT-EVAL${number - 200}`, args.service_type, args.status ?? 'INITIATED'), ...args };
      state.orders.push(created);
      if (args.idempotency_key) state.orderKeys.set(args.idempotency_key, created);
      return result(created);
    }
    case 'add_order_combos': {
      if (!currentOrder || !Array.isArray(args.combos)) return undefined;
      const lines = args.combos.map((line, index) => {
        const match = state.menu.products.find(entry => byId(entry.variants, line.variant_id));
        const choice = match && byId(match.variants, line.variant_id);
        if (!match || !Number.isInteger(line.quantity) || line.quantity < 1 ||
            !match.visible || (match.stock_enabled && choice.stock < line.quantity)) {
          throw { type: 'unavailable_or_invalid_combo', status: 422, detail: 'Artigo indisponível ou quantidade inválida.' };
        }
        return { ...line, id: id(601 + currentOrder.combos.length + index), name: match.name, price: choice.price };
      });
      currentOrder.combos.push(...lines);
      currentOrder.items = currentOrder.combos;
      currentOrder.total = Number(currentOrder.combos.reduce((total, line) => total + line.price * line.quantity, 0).toFixed(2));
      return result(currentOrder);
    }
    case 'remove_order_combo': {
      if (!currentOrder) return undefined;
      const idx = currentOrder.combos.findIndex(line => line.id === args.comboId);
      if (idx < 0) return undefined;
      currentOrder.combos.splice(idx, 1);
      currentOrder.items = currentOrder.combos;
      currentOrder.total = Number(currentOrder.combos.reduce((total, line) => total + line.price * line.quantity, 0).toFixed(2));
      return result(currentOrder);
    }
    case 'update_order': return result(patch(currentOrder, ['comment', 'order_title', 'service_type', 'delivery_address', 'scheduled_delivery_date']));
    case 'update_order_status': {
      if (!currentOrder) return undefined;
      if (['CANCELLED', 'FINALIZED'].includes(currentOrder.status)) {
        throw { type: 'invalid_status_transition', status: 422, detail: 'Não é possível alterar o estado de um pedido finalizado ou cancelado.' };
      }
      return result(patch(currentOrder, ['status']));
    }
    case 'cancel_order':
      if (!currentOrder || currentOrder.payments.length) return undefined;
      return result(Object.assign(currentOrder, { status: 'CANCELLED', cancelation_reason: args.reason }));
    case 'add_order_payment': {
      if (!currentOrder) return undefined;
      const amt = Number(args.amount ?? 0);
      if (amt <= 0) throw { type: 'invalid_payment', status: 422, detail: 'Valor de pagamento inválido.' };
      const pay = { id: id(800 + currentOrder.payments.length), ...args, amount: amt };
      currentOrder.payments.push(pay);
      return result(currentOrder);
    }
    case 'remove_order_payment': {
      if (!currentOrder) return undefined;
      const idx = currentOrder.payments.findIndex(p => p.id === args.paymentId);
      if (idx < 0) return undefined;
      currentOrder.payments.splice(idx, 1);
      return result(currentOrder);
    }
    case 'apply_order_coupon': {
      if (!currentOrder) return undefined;
      const promo = state.promotions.find(p => p.published && (p.coupon_code === args.coupon_code || p.code === args.coupon_code));
      if (!promo) throw { type: 'invalid_coupon', status: 422, detail: 'Cupão inválido ou inativo.' };
      if (promo.service_types?.length && !promo.service_types.includes(currentOrder.service_type)) {
        throw { type: 'coupon_service_mismatch', status: 422, detail: 'Cupão não aplicável a este tipo de serviço.' };
      }
      if (promo.minimum_order_amount && currentOrder.total < promo.minimum_order_amount) {
        throw { type: 'coupon_minimum_not_met', status: 422, detail: 'Valor mínimo do cupão não atingido.' };
      }
      const disc = { id: id(850 + currentOrder.discounts.length), promotion_id: promo.id, code: promo.coupon_code, amount: promo.discount_value };
      currentOrder.discounts.push(disc);
      return result(currentOrder);
    }
    case 'add_order_discount': {
      if (!currentOrder) return undefined;
      const disc = { id: id(860 + currentOrder.discounts.length), ...args };
      currentOrder.discounts.push(disc);
      return result(currentOrder);
    }
    case 'remove_order_discount': {
      if (!currentOrder) return undefined;
      const idx = currentOrder.discounts.findIndex(d => d.id === args.discountId);
      if (idx < 0) return undefined;
      currentOrder.discounts.splice(idx, 1);
      return result(currentOrder);
    }
    case 'get_orders_summary': return result({ total_orders: 2, total_sales: 28.4 });
    case 'get_sales_by_hour': return result([{ hour: 13, total_orders: 2, total_sales: 28.4 }]);
    case 'get_sales_by_day': return result([{ day: '2026-11-01', total_orders: 2, total_sales: 28.4 }]);
    case 'get_orders_by_service_type': return result([{ service_type: 'TAKEAWAY', total_orders: 2, total_sales: 28.4 }]);
    case 'get_orders_by_source': return result([{ source: 'api', total_orders: 2, total_sales: 28.4 }]);
    case 'get_top_payment_methods': return result([{ name: 'Numerário', total: 28.4 }]);
    case 'get_margins_summary': return result({ total_sales: 28.4, total_cost: 12.0, margin: 16.4 });
    case 'get_product_margins': return result([{ product_id: id(11), name: 'Pastel de Carne', margin: 10.2 }]);
    case 'get_menu_conversion': return result({ views: 100, orders: 2 });
    case 'get_products_sold': return paginate([{ product_id: id(11), product_name: 'Pastel de Carne', product_quantity: 4 }], args);
    case 'get_delivery_pricing': return result(state.pricing);
    case 'get_delivery_quote': {
      if (args.district_id) {
        const match = state.pricing.districts?.find(d => d.id === args.district_id);
        return result({ price: match ? match.price : 0, area: match ? { id: match.id, name: match.name } : null });
      }
      if (typeof args.latitude === 'number' && typeof args.longitude === 'number') {
        const inside = args.latitude >= 38.60 && args.latitude <= 38.67 && args.longitude >= -9.18 && args.longitude <= -9.12;
        return result({ price: inside ? 2.5 : 0, area: inside ? { id: id(421), name: 'Corroios' } : null });
      }
      return result({ price: 0, area: null });
    }
    case 'assign_rider': {
      if (!currentOrder) return undefined;
      currentOrder.rider = { id: args.user_id ?? id(411), name: args.name, provider: args.provider ?? 'olaclick', phone_number: args.phone_number ?? null };
      return result(currentOrder);
    }
    case 'unassign_rider': {
      if (!currentOrder) return undefined;
      currentOrder.rider = null;
      return result(currentOrder);
    }
    case 'update_delivery_status': return result(patch(currentOrder, ['delivery_status']));
    case 'report_rider_position': {
      if (!currentOrder) return undefined;
      currentOrder.rider_position = { latitude: args.latitude, longitude: args.longitude, name: args.name };
      return result(currentOrder);
    }
    case 'list_promotions':
    case 'get_promotions':
    case 'get_active_promotions': return paginate(state.promotions, args);
    case 'get_promotion': return result(promotion);
    case 'create_promotion': {
      if (state.promotions.some(p => p.coupon_code === args.coupon_code)) {
        throw { type: 'duplicate_coupon_code', status: 422, detail: 'Já existe uma promoção com este código.' };
      }
      const created = { id: id(501 + state.promotions.length), ...args };
      state.promotions.push(created);
      return result(created);
    }
    case 'update_promotion': return result(patch(promotion, [
      'name', 'code', 'coupon_code', 'discount_type', 'discount_value', 'minimum_order_amount',
      'valid_from', 'valid_until', 'usage_limit', 'published', 'service_types',
    ]));
    case 'delete_promotion': {
      const idx = state.promotions.findIndex(p => p.id === (args.id ?? args.promotion_id));
      if (idx < 0) return undefined;
      const [removed] = state.promotions.splice(idx, 1);
      return result(removed);
    }
    default: return undefined;
  }
}

const readTools = new Set([
  'get_menu', 'list_categories', 'get_category', 'list_products', 'get_product', 'list_product_variants',
  'list_modifier_categories', 'list_kitchens', 'list_tables', 'list_webhooks', 'list_cashiers', 'list_cashier_balances',
  'get_company', 'get_store_status', 'list_payment_methods', 'list_users',
  'get_clients', 'get_client', 'get_orders', 'get_order', 'get_orders_summary', 'get_products_sold',
  'get_sales_by_hour', 'get_sales_by_day', 'get_orders_by_service_type', 'get_orders_by_source',
  'get_top_payment_methods', 'get_margins_summary', 'get_product_margins', 'get_menu_conversion',
  'get_delivery_pricing', 'get_delivery_quote', 'list_promotions', 'get_promotions', 'get_active_promotions', 'get_promotion',
]);

function newFixture(overrides = {}) {
  const defaultCompany = {
    id: id(400), name: 'DoBrasil Pastéis', currently_open: true, timezone: 'Europe/Lisbon',
    currency: 'EUR', address: 'Corroios', business_hours: [{ day: 'friday', open: '12:00', close: '22:00' }],
  };
  const defaultPricing = {
    mode: 'DISTRICT', pricing_type: 'DISTRICT', type: 'DISTRICT',
    districts: [{ id: id(421), name: 'Corroios', price: 2.5 }],
  };
  const state = structuredClone({
    menu,
    clients: overrides.clients ?? clients,
    orders: overrides.orders ?? orders,
    promotions: overrides.promotions ?? promotions,
    paymentMethods: overrides.paymentMethods ?? paymentMethods,
    company: { ...defaultCompany, ...(overrides.company ?? {}) },
    storeStatus: overrides.storeStatus ?? [{ name: 'Uber Eats', open: false }],
    pricing: overrides.pricing ?? defaultPricing,
    tables: overrides.tables ?? [{ id: id(431), name: 'Mesa 1', capacity: 4 }, { id: id(432), name: 'Mesa 4', capacity: 6 }],
    orderKeys: new Map(),
  });
  const calls = [];
  return {
    calls,
    menu: () => structuredClone(state.menu),
    call(turn, name, args) {
      const entry = { turn, name, args, write: !readTools.has(name) };
      calls.push(entry);
      try {
        const reply = handler(state, name, args);
        if (reply === undefined) throw { type: 'fixture_unsupported_or_missing', status: 404, detail: `No fixture result for ${name}.` };
        entry.ok = true;
        return reply;
      } catch (error) {
        entry.ok = false;
        entry.error = error.type ?? 'fixture_error';
        throw error;
      }
    },
    resetMenu() { state.menu = structuredClone(menu); },
  };
}

async function serveFixtures() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'olaclick-eval-'));
  const certificate = path.join(directory, 'cert.pem');
  const keyFile = path.join(directory, 'key.pem');
  const instances = new Map();
  const token = `olk_eval_${randomUUID()}`;
  let server;
  try {
    execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
      '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
      '-keyout', keyFile, '-out', certificate], { stdio: 'ignore' });
    server = https.createServer({ key: fs.readFileSync(keyFile), cert: fs.readFileSync(certificate) },
      async (req, res) => {
        const scope = /^\/([a-f\d-]+)\/(\d+)\/mcp$/.exec(req.url);
        const fixture = scope && instances.get(scope[1]);
        if (req.method !== 'POST' || !fixture || req.headers.authorization !== `Bearer ${token}`) {
          res.writeHead(404).end();
          return;
        }
        try {
          const chunks = [];
          for await (const chunk of req) chunks.push(chunk);
          const { id: requestId, method, params } = JSON.parse(Buffer.concat(chunks));
          if (method.startsWith('notifications/')) {
            res.writeHead(202).end();
            return;
          }
          let result;
          if (method === 'initialize') {
            result = { protocolVersion: params.protocolVersion, capabilities: { tools: {} }, serverInfo: { name: 'ola-click-eval', version: '1' } };
          } else if (method === 'tools/list') {
            result = { tools: [] };
          } else if (method === 'tools/call') {
            let payload;
            let isError = false;
            try {
              payload = fixture.call(Number(scope[2]), params.name, params.arguments ?? {});
            } catch (error) {
              isError = true;
              payload = { type: error.type ?? 'fixture_error', status: error.status ?? 500, detail: error.detail ?? error.message };
            }
            result = { isError, content: [{ type: 'text', text: JSON.stringify(payload) }], structuredContent: payload };
          } else {
            res.writeHead(400).end();
            return;
          }
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ jsonrpc: '2.0', id: requestId, result }));
        } catch {
          res.writeHead(400).end();
        }
      });
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
  } catch (error) {
    fs.rmSync(directory, { recursive: true, force: true });
    throw error;
  }

  const origin = `https://127.0.0.1:${server.address().port}`;
  return {
    allocate(overrides) {
      const instance = randomUUID();
      const fixture = newFixture(overrides);
      instances.set(instance, fixture);
      return {
        ...fixture,
        env(turn, writes) {
          const base = `${origin}/${instance}/${turn}`;
          return {
            RESTAURANTE_EVAL_WORKER: '1',
            OLACLICK_API_KEY: token, OLACLICK_MCP_URL: `${base}/mcp`, OLACLICK_API_BASE_URL: `${base}/v1`,
            OLACLICK_ALLOW_WRITES: writes ? '1' : '0', OLACLICK_ALLOW_DESTRUCTIVE: writes ? '1' : '0',
            NODE_EXTRA_CA_CERTS: certificate, SSL_CERT_FILE: certificate,
            REQUESTS_CA_BUNDLE: certificate, CURL_CA_BUNDLE: certificate,
          };
        },
        release() { instances.delete(instance); },
      };
    },
    close() {
      server.close();
      server.closeAllConnections();
      fs.rmSync(directory, { recursive: true, force: true });
    },
  };
}

module.exports = { id, newFixture, serveFixtures };
