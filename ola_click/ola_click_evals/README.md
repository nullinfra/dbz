# OlaClick WhatsApp conversation evaluations

Run from `Restaurante/` using Node.js with `process.loadEnvFile` (22.9 or newer), Python 3, OpenSSL and an authenticated Codex CLI. Use the current [allocated message directory](../../tools/chat-output.md) for `message_dir`.

```sh
node ola_click/ola_click_evals/_factory/tools/prepare.cjs "$message_dir"
node ola_click/ola_click_evals/_factory/tools/run.cjs "$message_dir/ola_click_eval"
node ola_click/ola_click_evals/_factory/tools/score.cjs "$message_dir/ola_click_eval"
```

Use `prepare.cjs --list` to list cases and `prepare.cjs "$message_dir" --case <id> --case <id>` to select a subset. The runner accepts `--jobs` (default 4), `--model` (default `gpt-6-luna`), `--effort` (default `medium`), and `--timeout` (default 240 seconds per message). Allocate a fresh message directory for a new execution.

| Coverage | Example |
|---|---|
| Short customer requests | Greeting, dietary preference, price and availability, English, payment methods, opening status, delivery quote |
| Long customer conversations | Multi-choice menu with a recommendation mid-draft, numbered offers, basket revisions, allergy and frozen item checks, checkout with a single confirmed submission |
| Owner and mixed requests | Read an independent branch when a price edit is invalid, handle active riders, client pagination and disambiguation, promotions and sales, order and delivery status |
| Menu edits | Disambiguate a variant, temporarily change stock, price, description or category visibility, then restore every field to its opening value |
| Boundaries | Untrusted claims of owner authority, private client data, unsupported requests, invalid prices, unavailable stock tracking |

The fixture models a synthetic DoBrasil catalog, using a separate copy for each case. The runner supplies only fixture credentials to normal tools. The local HTTPS endpoint implements the [OlaClick MCP contract](https://developers.olaclick.app/docs/mcp) for the tools exercised here. These results cover routing and tool behavior against that fixture. They do not measure production API availability or Maps address resolution.

A menu edit must produce the expected intermediate state. At the end, the scorer compares the entire catalog against the exact snapshot from the start of that case. The runner saves the final snapshot before resetting the fixture, including after a timeout or error. Cleanup cannot turn a failed restoration into a passing test.

The completed evaluation is published under the message that triggered it.

```text
ola_click_eval/
├── TEST_1/
│   ├── summary.json
│   ├── message.json
│   └── conversation.md
├── TEST_2/
│   └── ...
└── eval_report.md
```

`eval_report.md` includes every conversation, the per-turn expectations and verdicts, and a tally of failure patterns. Each test directory holds the structured verdict and the transcript in JSON and Markdown. The scorer uses temporary turn artifacts and menu snapshots, then removes its working directory after publishing.

To publish a report from a legacy evaluation that still has `eval.json` and the raw case artifacts, run `score.cjs "$message_dir/ola_click_eval" --from "$legacy_eval_dir"`. This command scores the stored messages and results without running the conversations again.
