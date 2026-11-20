# OlaClick evaluation pipeline

Run short requests and multi-turn WhatsApp conversations through the restaurant's normal OlaClick tools. Publish the report and one folder per test at `<message_dir>/ola_click_eval/`.

| Stage | Job |
|---|---|
| [00_prepare](stages/00_prepare/CONTEXT.md) | Freeze customer and owner scenarios and validate the planned menu restoration |
| [01_spawn](stages/01_spawn/CONTEXT.md) | Run one cold Codex (batches of 10) or Claude (batches of 50) session per conversation, send one turn at a time, and capture each case's isolated store state |
| [02_score](stages/02_score/CONTEXT.md) | Check the outputs, actual tool calls, replies, and full menu state deterministically |

The [README](README.md) lists commands and coverage. The [scenarios](_factory/scenarios.cjs) define messages and their checks.
