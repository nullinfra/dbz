const { writeIntent } = require('../../../../_shared/tools/write-mcp-intent.cjs');
const clients = require('../../02_resolve_and_execute/tools/client-operations.cjs');

writeIntent({ clients });
