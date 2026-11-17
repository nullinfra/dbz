# Maps Workspace

- If the user asks for an eval, go to [geolocation_evals/CONTEXT.md](geolocation_evals/CONTEXT.md).
- Otherwise, resolve the caller's customer message and produce the stage's orientation output. This ICM does not communicate with the customer directly.
- Start with [the stage context](geolocation_icm/stages/01_extract_and_resolve/CONTEXT.md). Never read any `.py` file; invoke the documented tools as black-box commands.
- Treat the user's message as the input payload. If no payload is specified, use: `"Boa tarde! A entrega é na Rua da Liberdade, 10. É no 2.º esquerdo"`.
