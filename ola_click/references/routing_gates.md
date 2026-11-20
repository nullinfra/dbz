# OlaClick routing gates

Use the actor known from the caller's context. Give the applicable gate to the [OlaClick coordinator](../CONTEXT.md#coordinate-the-selected-icms) as an operation.

## `non_actionable`

Use this for greetings, small talk, thanks, or a standalone delivery address with no OlaClick request. Set `entities` to `{}`. At the WhatsApp entry point, [the restaurant router](../../AGENTS.md) handles general chat directly and sends standalone delivery addresses to Maps.

## `unsupported_request`

Set `entities` to `{"requested_action":"<short description>","reason":"<why it is unsupported>"}`.

- Customer requests outside the available workflows include reservations, bank or MB Way refunds, off-menu dishes, and splitting a delivery payment across multiple links.
- For a customer requesting an owner-only action, use the reason `Apenas o gerente/dono pode realizar esta operação.` Examples include menu or stock changes, kitchen status updates, recording cash payments, rider assignment, and viewing sales or cashier balances.
- Platform limitations include deleting an individual product, uploading product images, creating or deleting modifier categories, changing store hours, and creating or editing staff users. Consult the selected ICM's references for limits specific to that workflow.
- Use the selected module’s tool rules from the [router read set](../CONTEXT.md#read-set-read-all-docs-for-the-selected-icms-in-one-cat-command) to distinguish an upstream limitation from an operation that exists in MCP but has no route in this ICM. For example, route variant renames to `update_product_variant`, and use the panel for category deletion when operating through this ICM.
