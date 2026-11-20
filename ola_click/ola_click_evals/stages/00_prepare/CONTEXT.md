# 00_prepare — freeze the cases

## Inputs

- The exact `message_dir` from the [chat output contract](../../../../tools/chat-output.md).
- [Scenarios](../../_factory/scenarios.cjs) and, optionally, a list of selected case IDs.

## Process

Run from `Restaurante/`.

```sh
node ola_click/ola_click_evals/_factory/tools/prepare.cjs "$message_dir"
eval_dir="$message_dir/ola_click_eval"
```

## Outputs

`<message_dir>/.ola_click_eval_work/` holds `eval.json`, `status.json`, `check.md` and an empty `cases/` directory. The runner and scorer use this temporary directory while accepting `eval_dir` as the published destination.

## Check

Proceed to [01_spawn](../01_spawn/CONTEXT.md) after a zero exit. Preparation checks unique IDs, turn inputs and reply patterns. It applies every expected menu patch to a fresh baseline and rejects any scenario that would leave the menu altered.
