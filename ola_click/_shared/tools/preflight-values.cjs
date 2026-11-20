const present = value => value !== null && value !== undefined;
const nonblank = value => typeof value === 'string' && value.trim().length > 0;
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const list = value => Array.isArray(value) ? value : [];
const uuid = value => typeof value === 'string' && /^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(value);
const integer = (value, min = 0, max = Number.MAX_SAFE_INTEGER) =>
  Number.isSafeInteger(value) && value >= min && value <= max;
const number = (value, min = 0, max = Infinity) => Number.isFinite(value) && value >= min && value <= max;
const coordinates = (latitude, longitude) => number(latitude, -90, 90) && number(longitude, -180, 180);
const csvMatches = (value, options) => nonblank(value) && value.split(',').every(token => options.includes(token.trim()));

function checkPagination({ page, per_page: perPage }, add) {
  if (present(page) && !integer(page, 1)) add('page', 'Indica uma página a partir de 1.');
  if (present(perPage) && !integer(perPage, 1, 100)) add('per_page', 'Indica entre 1 e 100 resultados por página.');
}

function date(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(value);
  return Number.isFinite(+parsed) && parsed.toISOString().slice(0, 10) === value;
}

const dateTime = value => typeof value === 'string' && date(value.slice(0, 10)) &&
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/i.test(value) &&
  Number.isFinite(Date.parse(value));

module.exports = { present, nonblank, record, list, uuid, integer, number, coordinates, date, dateTime, csvMatches, checkPagination };
