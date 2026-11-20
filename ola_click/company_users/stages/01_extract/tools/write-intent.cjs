const { writeIntent } = require('../../../../_shared/tools/write-mcp-intent.cjs');
const company = require('../../02_resolve_and_execute/tools/company-operations.cjs');
const clients = require('../../../../clients/stages/02_resolve_and_execute/tools/client-operations.cjs');

// Accept client intents from older callers and assign them to their current module.
writeIntent({ company_users: company, clients });
