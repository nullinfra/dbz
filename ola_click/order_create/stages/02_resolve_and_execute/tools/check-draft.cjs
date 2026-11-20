const fs = require('node:fs');
const path = require('node:path');
const { dateTime, integer, nonblank, record, uuid } = require('../../../../_shared/tools/preflight-values.cjs');

function checkItem(item, add) {
  if (!nonblank(item?.name)) add('name');
  if (!uuid(item?.product_id)) add('product_id');
  if (!integer(item?.quantity, 1)) add('quantity');
  if (item?.variant_id != null && !uuid(item.variant_id)) add('variant_id');
  const review = item?.catalog_review;
  const expectedShape = '{ category_id: "<uuid>", description: "<string|null>", groups: [], issues: [] }';
  if (!record(review)) {
    add('catalog_review', { expected: expectedShape });
    return;
  }
  const missingFields = [];
  if (!uuid(review.category_id)) missingFields.push('category_id (uuid)');
  if (!(review.description === null || typeof review.description === 'string')) missingFields.push('description (string|null)');
  if (!Array.isArray(review.groups)) missingFields.push('groups (array)');
  if (!Array.isArray(review.issues)) missingFields.push('issues (array)');
  if (missingFields.length) {
    add('catalog_review', { missing_fields: missingFields, expected: expectedShape });
    return;
  }

  for (const issue of review.issues) {
    if (!record(issue) || !nonblank(issue.question)) add('catalog_review.issues');
    else add('catalog_review.issue', { question: issue.question });
  }
  for (const group of review.groups) {
    if (!record(group) || !nonblank(group.label) || !integer(group.min) ||
        (group.max != null && !integer(group.max, group.min)) || !Array.isArray(group.selections)) {
      add('catalog_review.groups');
      continue;
    }
    const valid = group.selections.every(selection => nonblank(selection?.name) &&
      integer(selection.quantity, 1) && (selection.product_id == null || uuid(selection.product_id)));
    const selected = valid ? group.selections.reduce((sum, entry) => sum + entry.quantity, 0) : null;
    if (selected === null || selected < group.min || (group.max != null && selected > group.max)) {
      add('catalog_review.selection', {
        label: group.label, min: group.min, max: group.max ?? null, selected,
        ...(nonblank(group.question) ? { question: group.question } : {}),
      });
    }
  }
}

function inspectDraft(intent) {
  const operations = intent.operations ?? [intent];
  const missing = [];
  for (const [index, operation] of operations.entries()) {
    if (operation.intent !== 'create_order') continue;
    const fields = operation.entities;
    const report = (field, details = {}) => missing.push({ operation: index + 1, field, ...details });
    const items = Array.isArray(fields.items) ? fields.items : [];
    if (!items.length) report(fields.repeat_last_order ? 'repeat_order_review' : 'items');
    for (const field of ['ambiguous_notes', 'ambiguous_quantities']) {
      if (fields[field]?.length) report(field, { values: fields[field] });
    }
    if (!['DELIVERY', 'TABLE', 'ONSITE', 'TAKEAWAY'].includes(fields.service_type)) report('service_type');
    if (fields.service_type === 'DELIVERY' && !nonblank(fields.delivery_address)) report('delivery_address');
    if (fields.service_type === 'TABLE' && !nonblank(fields.table_name) && !uuid(fields.table_id)) report('table');
    if (fields.scheduled_delivery_date != null && !dateTime(fields.scheduled_delivery_date)) report('scheduled_delivery_date');
    if (fields.allergy_notes?.length && (fields.allergy_review?.confirmed !== true ||
        !nonblank(fields.allergy_review.source))) {
      report('allergy_review', { question: 'É preciso confirmar os alergénios deste pedido com o restaurante.' });
    }
    for (const [itemIndex, item] of items.entries()) {
      checkItem(item, (field, details) => report(field, { item: itemIndex + 1, name: item?.name, ...details }));
    }
  }
  return { status: missing.length ? 'DRAFT' : 'READY', missing };
}

module.exports = { inspectDraft, checkItem };

if (require.main === module) {
  try {
    const run = process.argv[2];
    if (!run) throw new Error('Use check-draft.cjs <run-directory>.');
    const intent = JSON.parse(fs.readFileSync(path.join(run, 'stage01_intent.json'), 'utf8'));
    const report = inspectDraft(intent);
    console.log(JSON.stringify(report));
    if (report.missing.length) process.exitCode = 1;
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
