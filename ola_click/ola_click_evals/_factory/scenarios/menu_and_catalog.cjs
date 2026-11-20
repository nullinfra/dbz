const { id, completed, clarify, unsupported, op, call, question, menuEdit, t, scenario } = require('./helpers.cjs');

module.exports = [
  scenario('menu-external-app-status', 'customer', ['menu', 'short'],
    t('Estão abertos na Uber Eats agora?', {
      operations: [op('check_store_hours_or_open', completed)],
      calls: [call('get_company'), call('get_store_status')],
      reply: ['uber eats', 'fechad|indisponível|não'],
    })),

  scenario('menu-hidden-product-no-leak', 'customer', ['menu', 'short'],
    t('Têm Rascunho Interno no menu? Quanto custa?', {
      calls: [call('get_menu')],
      exclude: ['99', 'produto escondido'],
      reply: ['não|indisponível|encontr'],
    })),

  scenario('menu-hidden-category-no-leak', 'owner', ['menu', 'long'],
    t('Esconde temporariamente a categoria Sobremesas.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_category', { id: id(3), visible: false })],
      menu: [{ category: 3, patch: { visible: false } }],
      reply: ['escondid|ocult'],
    }),
    t('Têm Pudim ou Brigadeiro no menu?', {
      calls: [call('get_menu')],
      exclude: ['3[,.]25', '1[,.]5'],
      reply: ['não|indisponível|nenhum'],
    }),
    t('Volta a mostrar a categoria Sobremesas.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_category', { id: id(3), visible: true })],
      menu: [{ category: 3, patch: { visible: true } }],
      reply: ['visível|disponível|mostr|volt'],
    })),

  scenario('menu-cheapest-drink', 'customer', ['menu', 'short'],
    t('Qual é a bebida mais barata que têm?', {
      calls: [call('get_menu')],
      available: [23],
      reply: ['água', '1[,.]2'],
    })),

  scenario('menu-price-range-inclusive', 'customer', ['menu', 'short'],
    t('Que pastéis têm entre 5 € e 6 €?', {
      calls: [call('get_menu')],
      available: [11, 14],
      reply: ['carne', 'frango'],
      exclude: ['queijo', 'camarão'],
    })),

  scenario('menu-price-range-exact-boundary', 'customer', ['menu', 'short'],
    t('Há algum pastel exatamente a 4,80 €?', {
      calls: [call('get_menu')],
      available: [12],
      reply: ['queijo', '4[,.]8'],
    })),

  scenario('menu-only-unavailable', 'customer', ['menu', 'short'],
    t('O que é que está esgotado hoje?', {
      calls: [call('get_menu')],
      unavailable: [13],
      reply: ['camarão'],
    })),

  scenario('menu-multivariant-prices', 'customer', ['menu', 'short'],
    t('Quanto custa o Guaraná?', {
      calls: [call('get_menu')],
      available: [21],
      reply: ['2[,.]1', '3[,.]7', 'lata', 'garrafa'],
    })),

  scenario('menu-multivariant-partial-oos', 'owner', ['menu', 'stock', 'long'],
    t('Marca a garrafa de 1 litro de Guaraná como esgotada.', {
      operations: [op('set_item_out_of_stock', completed)],
      writes: [call('update_product_variant', { id: id(21), variantId: id(127), stock: 0 })],
      menu: [menuEdit(21, 127, { stock: 0 })],
      reply: ['garrafa|1[ ]*l', 'esgotad'],
    }),
    t('O Guaraná ainda está disponível?', {
      calls: [call('get_menu')],
      available: [21],
      reply: ['lata', 'disponível', 'garrafa', 'esgotad'],
    }),
    t('Repõe a garrafa de 1 litro com 9 unidades.', {
      operations: [op('restore_item_in_stock', completed)],
      writes: [call('update_product_variant', { id: id(21), variantId: id(127), stock: 9 })],
      menu: [menuEdit(21, 127, { stock: 9 })],
      reply: ['9'],
    })),

  scenario('menu-typos-no-accents', 'customer', ['menu', 'language', 'short'],
    t('tem pastel de camarao e guarana?', {
      calls: [call('get_menu')],
      unavailable: [13],
      available: [21],
      reply: ['camarão', 'guaraná'],
    })),

  scenario('menu-plurals-diminutives', 'customer', ['menu', 'language', 'short'],
    t('Têm pastéiszinhos de carne e uma aguinha?', {
      calls: [call('get_menu')],
      available: [11, 23],
      reply: ['pastel de carne', 'água'],
    })),

  scenario('menu-br-pt-slang', 'customer', ['menu', 'language', 'short'],
    t('Que refris têm? Têm coca zero?', {
      calls: [call('get_menu')],
      available: [21, 22],
      reply: ['guaraná', 'coca-cola', 'não|zero'],
    })),

  scenario('menu-sku-code-lookup', 'customer', ['menu', 'short'],
    t('Têm o produto EVAL-11?', {
      calls: [call('get_menu')],
      reply: ['pastel de carne', '5[,.]2'],
    })),

  scenario('menu-ingredient-inclusion', 'customer', ['menu', 'short'],
    t('Têm alguma coisa com chocolate?', {
      calls: [call('get_menu')],
      available: [32],
      reply: ['brigadeiro'],
    })),

  scenario('menu-allergen-crustaceans-honest', 'customer', ['menu', 'allergens', 'short'],
    t('Tenho alergia a crustáceos e amendoim. Que pastéis posso comer?', {
      calls: [call('get_menu')],
      reply: ['camarão|crustáceos', 'amendoim|alerg|confirm'],
      exclude: ['sem risco|garanto que não tem amendoim'],
    })),

  scenario('menu-vegan-honesty', 'customer', ['menu', 'allergens', 'short'],
    t('Têm alguma opção 100% vegan confirmada?', {
      calls: [call('get_menu')],
      reply: ['vegan|confirm|não'],
      exclude: ['pastel de queijo é vegan'],
    })),

  scenario('menu-off-menu-unsupported', 'customer', ['menu', 'gates', 'short'],
    t('Fazem pastel de bacalhau por encomenda?', {
      operations: [op('unsupported_request', unsupported)],
      reply: ['bacalhau|menu|não'],
    })),

  scenario('menu-spanish-query', 'customer', ['menu', 'language', 'short'],
    t('¿Tienen empanadas de queso?', {
      calls: [call('get_menu')],
      available: [12],
      reply: ['queijo|queso', '4[,.]8'],
    })),

  scenario('menu-stock-enabled-false-count', 'customer', ['menu', 'stock', 'short'],
    t('Quantos Pudins têm disponíveis?', {
      calls: [call('get_menu')],
      available: [31],
      reply: ['pudim|pudins', 'disponível|disponíveis'],
      exclude: ['apenas 5|só 5'],
    })),

  scenario('menu-offer-positional-single', 'customer', ['menu', 'offers', 'long'],
    t('Mostra-me as bebidas numa lista numerada.', {
      calls: [call('get_menu')],
      offer: [21, 22, 23],
      reply: ['guaraná', 'coca', 'água'],
    }),
    t('Quero uma unidade da opção 2 para levar.', {
      reply: ['coca-cola', '2[,.]2'],
    })),

  scenario('menu-offer-positional-last', 'customer', ['menu', 'offers', 'long'],
    t('Mostra-me os pastéis disponíveis numa lista numerada.', {
      calls: [call('get_menu')],
      offer: [11, 12, 14],
      reply: ['carne', 'queijo', 'frango'],
    }),
    t('Quero um do último da lista, para levar.', {
      reply: ['frango', '5[,.]4'],
    })),

  scenario('menu-offer-positional-quantities', 'customer', ['menu', 'offers', 'long'],
    t('Mostra-me as bebidas numa lista numerada.', {
      calls: [call('get_menu')],
      offer: [21, 22, 23],
      reply: ['guaraná', 'coca', 'água'],
    }),
    t('Quero 2 da terceira opção e 1 da segunda, para levar.', {
      reply: ['água', 'coca-cola'],
    })),

  scenario('menu-offer-negative-selection', 'customer', ['menu', 'offers', 'long'],
    t('Mostra-me as bebidas numa lista numerada.', {
      calls: [call('get_menu')],
      offer: [21, 22, 23],
      reply: ['guaraná', 'coca', 'água'],
    }),
    t('Quero uma de cada dessas bebidas, menos a água.', {
      reply: ['guaraná', 'coca-cola'],
      exclude: ['1[ ]*×[ ]*água|1 água'],
    })),

  scenario('menu-offer-out-of-range', 'customer', ['menu', 'offers', 'long'],
    t('Mostra-me só o Pudim e o Brigadeiro numa lista numerada.', {
      calls: [call('get_menu')],
      offer: [31, 32],
      reply: ['pudim', 'brigadeiro'],
    }),
    t('Quero a opção 4.', {
      ...question('1|2|pudim|brigadeiro|opção'),
    })),

  scenario('owner-ambiguous-product-stock', 'owner', ['menu', 'stock', 'short'],
    t('Marca o pastel como esgotado.', {
      operations: [op('set_item_out_of_stock', clarify)],
      calls: [call('get_menu')],
      ...question('carne|queijo|frango'),
    })),

  scenario('owner-item-not-found-stock', 'owner', ['menu', 'stock', 'short'],
    t('Marca o Pastel de Bacalhau como esgotado.', {
      operations: [op('set_item_out_of_stock', clarify)],
      calls: [call('get_menu')],
      reply: ['bacalhau|não encontr|catálogo'],
    })),

  scenario('owner-restore-stock-missing-qty', 'owner', ['menu', 'stock', 'short'],
    t('Repõe o Pastel de Camarão em stock.', {
      operations: [op('restore_item_in_stock', clarify)],
      ...question('quant|stock|unidades'),
    })),

  scenario('owner-restore-stock-zero-rejected', 'owner', ['menu', 'stock', 'short'],
    t('Repõe o Pastel de Camarão em stock com 0 unidades.', {
      forbidCalls: ['update_product_variant'],
      reply: ['positiv|maior que 0|esgotado|0'],
    })),

  scenario('owner-promo-price-and-end-promo', 'owner', ['menu', 'batch', 'long'],
    t('Mete o Pastel de Carne em promoção a 4,00 €, mantendo o preço original a 5,20 €.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), price: 4 })],
      menu: [menuEdit(11, 111, { price: 4 })],
      reply: ['4[,.]0'],
    }),
    t('Termina a promoção do Pastel de Carne para voltar ao preço original.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), price: 5.2 })],
      menu: [menuEdit(11, 111, { price: 5.2 })],
      reply: ['5[,.]2'],
    })),

  scenario('owner-price-delta-and-restore', 'owner', ['menu', 'long'],
    t('Sobe 0,30 € ao preço do Pastel de Carne.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), price: 5.5 })],
      menu: [menuEdit(11, 111, { price: 5.5, original_price: 5.5 })],
      reply: ['5[,.]5'],
    }),
    t('Volta a pôr o preço e o preço original do Pastel de Carne a 5,20 €.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(11), variantId: id(111), price: 5.2, original_price: 5.2 })],
      menu: [menuEdit(11, 111, { price: 5.2, original_price: 5.2 })],
      reply: ['5[,.]2'],
    })),

  scenario('owner-price-percent-single-and-restore', 'owner', ['menu', 'long'],
    t('Aumenta o preço do Brigadeiro em 20%.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), price: 1.8 })],
      menu: [menuEdit(32, 132, { price: 1.8, original_price: 1.8 })],
      reply: ['1[,.]8'],
    }),
    t('Volta a pôr o preço e preço original do Brigadeiro a 1,50 €.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), price: 1.5, original_price: 1.5 })],
      menu: [menuEdit(32, 132, { price: 1.5, original_price: 1.5 })],
      reply: ['1[,.]5'],
    })),

  scenario('owner-product-visibility-unsupported', 'owner', ['menu', 'gates', 'short'],
    t('Esconde só o produto Brigadeiro sem esconder a categoria Sobremesas.', {
      operations: [op('edit_menu', unsupported)],
      reply: ['painel|categoria'],
    })),

  scenario('owner-delete-nonempty-category', 'owner', ['menu', 'gates', 'short'],
    t('Apaga a categoria Sobremesas.', {
      operations: [op('edit_menu', unsupported)],
      reply: ['sobremesas|vazia|produtos|painel|não'],
    })),

  scenario('owner-create-duplicate-product-blocked', 'owner', ['menu', 'validation', 'short'],
    t('Cria um produto novo chamado Pastel de Carne na categoria Pastéis por 5,00 €.', {
      forbidCalls: ['create_product'],
      reply: ['já existe|duplicad|pastel de carne'],
    })),

  scenario('owner-bulk-price-category-negative-blocked', 'owner', ['menu', 'validation', 'short'],
    t('Baixa todas as Sobremesas em 2,00 €.', {
      forbidCalls: ['update_product_variant'],
      reply: ['negativ|brigadeiro|inválid|não'],
    })),

  scenario('owner-rename-category-and-restore', 'owner', ['menu', 'long'],
    t('Muda o nome da categoria Sobremesas para Doces.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_category', { id: id(3), name: 'Doces' })],
      menu: [{ category: 3, patch: { name: 'Doces' } }],
      reply: ['doces'],
    }),
    t('Volta a chamar Sobremesas à categoria Doces.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_category', { id: id(3), name: 'Sobremesas' })],
      menu: [{ category: 3, patch: { name: 'Sobremesas' } }],
      reply: ['sobremesas'],
    })),

  scenario('owner-update-product-position-and-restore', 'owner', ['menu', 'long'],
    t('Muda a posição do Pudim para 1.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_position', { id: id(31), position: 1 })],
      menu: [{ number: 31, patch: { position: 1 } }],
      reply: ['posição|1'],
    }),
    t('Repõe a posição do Pudim para 31.', {
      operations: [op('edit_menu', completed)],
      writes: [call('update_product_position', { id: id(31), position: 31 })],
      menu: [{ number: 31, patch: { position: 31 } }],
      reply: ['31'],
    })),

  scenario('owner-multi-product-stock-oos-and-restore', 'owner', ['menu', 'stock', 'long'],
    t('Marca o Pudim e o Brigadeiro como esgotados.', {
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), stock: 0 })],
      menu: [menuEdit(32, 132, { stock: 0 })],
      reply: ['pudim', 'stock|painel', 'brigadeiro'],
    }),
    t('Repõe o Brigadeiro com 17 unidades.', {
      operations: [op('restore_item_in_stock', completed)],
      writes: [call('update_product_variant', { id: id(32), variantId: id(132), stock: 17 })],
      menu: [menuEdit(32, 132, { stock: 17 })],
      reply: ['17'],
    })),
];
