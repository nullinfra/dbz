# Maps Workspace

- If the user asks for an eval, go to [geolocation_evals/CONTEXT.md](geolocation_evals/CONTEXT.md).
- Otherwise, resolve the caller's customer message and produce the stage's orientation output. This ICM does not communicate with the customer directly.
- Start by reading [the stage context](geolocation_icm/stages/01_extract_and_resolve/CONTEXT.md), [decision rules](geolocation_icm/stages/01_extract_and_resolve/references/extraction_and_maps_rules.md), and [tool rules](geolocation_icm/stages/01_extract_and_resolve/tools/rules.md) in one batch. Never read any `.py` file; invoke the documented tools as black-box commands.
- Treat the user's message as the input payload. If no payload is specified, use: `"Boa tarde! A entrega é na avenia do cristo rei, 47. É no 2.º esquerdo"`.
