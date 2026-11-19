# Promotions — Resolution policy

Resolve promotion names and codes to verified IDs before get, update or delete. Check scopes, dates, discount value and eligibility from the request. For a product-specific promotion, verify every target against the live catalogue before constructing the API request and preserve the selected product IDs and names. A missing target requires a new selection.

Use the write gate for creation or updates and both write and destructive gates for deletion. The preview reports the payload that would be sent. An existing promotion may have terms that affect a partial update. Read those terms before deciding whether an edited field is valid in context.
