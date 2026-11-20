# 02_score — verify decisions and store state

## Inputs

- Frozen manifest in the [preparation working directory](../00_prepare/CONTEXT.md#outputs).
- Case execution logs, per-turn replies and tool artifacts from [01_spawn](../01_spawn/CONTEXT.md).

## Process

```sh
node ola_click/ola_click_evals/_factory/tools/score.cjs "$eval_dir"
```

The scorer checks the expected routing, data and side effects, including stage artifacts, draft quantities and choices, exact write counts, and required or forbidden terms in replies. It compares the entire menu after each turn with the planned state and again at the end with the case's pre-test baseline. An edit cannot pass by skipping the change or relying on the harness cleanup.

## Outputs and check

Open `<eval_dir>/eval_report.md` for the conversations, expected behavior, pass/fail verdicts, and failure patterns. Each `TEST_<number>/` holds `summary.json`, `message.json` and `conversation.md`. The scorer publishes the complete folder before removing its temporary inputs. It exits nonzero when any test fails and reports incomplete turns in the published report.
