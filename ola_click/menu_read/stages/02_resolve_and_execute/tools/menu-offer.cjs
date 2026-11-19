const fs = require('node:fs');
const path = require('node:path');

const output = path.resolve(__dirname, '../../../../../output');
const basename = 'menu_offer.json';

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function outputParts(file) {
  const parts = path.relative(output, fs.realpathSync(file)).split(path.sep);
  if (parts[0] === '..' || path.isAbsolute(parts.join(path.sep))) {
    throw new Error('Use an artifact inside the chat output directory.');
  }
  return parts;
}

function requireArtifact(file, filename) {
  const parts = outputParts(file);
  if (parts.length !== 5 || parts[2] !== 'ola_click' || parts[4] !== filename) {
    throw new Error(`Expected ${filename} inside an OlaClick message run.`);
  }
  return parts;
}

function recordOffer(orientationFile, productIds) {
  orientationFile = fs.realpathSync(orientationFile);
  requireArtifact(orientationFile, 'orientation.json');
  if (!Array.isArray(productIds) || productIds.length === 0 ||
      new Set(productIds).size !== productIds.length || productIds.some(id => typeof id !== 'string' || !id)) {
    throw new Error('Supply unique OlaClick product IDs in the order shown.');
  }
  const { results } = readJson(orientationFile);
  const matches = new Map();
  for (const result of results ?? []) {
    if (result.pipeline !== 'menu_read' || result.status !== 'COMPLETED') continue;
    for (const product of result.mcp_result?.menu_matches ?? []) {
      if (product.available === true && typeof product.name === 'string' && product.name.trim()) {
        matches.set(product.id, product);
      }
    }
  }
  const products = productIds.map(id => {
    const product = matches.get(id);
    if (!product) throw new Error(`Product ${id} is missing or unavailable in the verified result.`);
    return { id, name: product.name };
  });
  const file = path.join(path.dirname(orientationFile), basename);
  const temporary = `${file}.${process.pid}.tmp`;
  try {
    fs.writeFileSync(temporary, JSON.stringify({ products }, null, 2) + '\n');
    fs.renameSync(temporary, file);
  } finally {
    fs.rmSync(temporary, { force: true });
  }
  return file;
}

function selectOffer(messageDirectory, offerFile, selection) {
  const [chat, message, ...other] = outputParts(messageDirectory);
  const [offerChat] = requireArtifact(offerFile, basename);
  if (!chat || !message || other.length || chat !== offerChat) {
    throw new Error('Use a saved menu offer from this chat.');
  }
  const { products } = readJson(offerFile);
  if (!Array.isArray(products) || !products.length ||
      products.some(product => typeof product?.name !== 'string' || !product.name.trim())) {
    throw new Error('The saved offer contains no selectable products.');
  }
  const positions = selection === 'all' ? products.map((_, index) => index + 1) : JSON.parse(selection);
  if (!Array.isArray(positions) || !positions.length || new Set(positions).size !== positions.length ||
      positions.some(position => !Number.isInteger(position) || position < 1 || position > products.length)) {
    throw new Error('Choose valid, distinct positions from the list shown.');
  }
  return positions.map(position => {
    const { id: product_id, name } = products[position - 1];
    return { product_id, name, quantity: 1 };
  });
}

function selectCatalog(messageDirectory, orientationFile) {
  const [chat, message, ...other] = outputParts(messageDirectory);
  const [lookupChat, lookupMessage] = requireArtifact(orientationFile, 'orientation.json');
  if (!chat || !message || other.length || chat !== lookupChat || message !== lookupMessage) {
    throw new Error('Use the full catalog lookup from this message.');
  }
  const { results } = readJson(orientationFile);
  const lookup = results?.find(result =>
    result.pipeline === 'menu_read' && result.intent === 'get_menu_category' &&
    result.status === 'COMPLETED' && result.entities?.include_details === true &&
    Object.entries(result.entities).every(([key, value]) =>
      key === 'include_details' || value === null || value === '' ||
      (key === 'cheapest' && value === false)));
  const products = lookup?.mcp_result?.menu_matches;
  if (!Array.isArray(products) || !products.length ||
      products.some(product => typeof product.id !== 'string' || !product.id ||
        typeof product.name !== 'string' || !product.name) ||
      new Set(products.map(product => product.id)).size !== products.length) {
    throw new Error('Use a complete detailed catalog result with distinct product IDs.');
  }
  return products.filter(product => product.available === true)
    .map(({ id: product_id, name }) => ({ product_id, name, quantity: 1 }));
}

try {
  const [command, first, second, third] = process.argv.slice(2);
  if (command === 'record') {
    console.log(recordOffer(first, JSON.parse(second)));
  } else if (command === 'select') {
    console.log(JSON.stringify(selectOffer(first, second, third)));
  } else if (command === 'catalog') {
    console.log(JSON.stringify(selectCatalog(first, second)));
  } else {
    throw new Error('Use record <orientation> <product_ids_json>, select <message_directory> <offer> <all|positions_json>, or catalog <message_directory> <orientation>.');
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
