# Chat output

Use one folder per chat and one folder inside it per incoming message. Allocate the message folder before routing, including for greetings and other messages handled without an ICM.

```text
output/<chat_folder>/<message_folder>/
├── message.json
├── summary.md
├── maps/
│   └── orientation.json
├── ola_click/
│   └── 01_batch/
│       ├── stage01_intent.json
│       └── orientation.json
└── geolocation_eval/
```

`message.json` records the folder's chat ID, message ID, timestamp, and Codex turn ID when available. `raw_input` holds the original message text, including line breaks and whitespace. The hook writes the summary at the end of the message. Create ICM folders as they are used.

Chat and generated message folders sort by their UTC timestamps to the second, for example `2026-11-19_16-26-33Z`. If multiple folders are created in the same second under the same parent, the next folders use `-002`, `-003`, and so on. The stable chat ID stays in the chat folder's `.chat.json`.

## Allocate the message directory

In Codex, use the directory supplied by the `UserPromptSubmit` hook. That hook gives each message a separate folder, including when more than one prompt arrives in the same turn. The `SessionStart` hook creates the chat folder.

If the hook did not supply a path, run this once for the incoming message from `Restaurante/`:

```sh
printf '%s' "$message_text" | node .codex/chat-output.cjs message --stdin
```

Set `message_text` to the incoming text as received. The command uses the current Codex session ID. A caller with its own stable IDs can run `node .codex/chat-output.cjs session <chat_id>` at chat start and pass its IDs after `message --stdin` when piping the text. If the caller has no chat ID, use `node .codex/chat-output.cjs session` once and reuse the returned directory's basename. Omit the message ID to generate a new one. Reuse the exact directory for retries of the same message.

## Pass it to every ICM

- Treat the allocated path as `message_dir`. Pass it to each selected ICM and delegated stage, along with the exact subfolder assigned to that work.
- Use `<message_dir>/maps/` for Maps. Use numbered run directories under `<message_dir>/ola_click/`, such as `01_batch/` or `01_menu_read/`. Each parallel or dependent run gets its own directory. Both OlaClick stages in a run share it.
- Start a geolocation evaluation under `<message_dir>/geolocation_eval/`. Evaluation workers use their explicit per-case paths under that evaluation, including any supplied `--maps` path.
- Supply the output flags in the ICM's tool rules on every call. Use the output from the assigned directory when replying.
