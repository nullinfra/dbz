# 00_prepare — validate and freeze an eval run

Use the allocated [chat message directory](../../../../tools/chat-output.md) as `message_dir`. Run from the project root:

```sh
eval_dir="$(pwd -P)/$message_dir/geolocation_eval"
python3 maps/geolocation_evals/_factory/tools/prepare.py --eval-id "$eval_dir" &&
  node maps/geolocation_evals/stages/00_prepare/tools/bind-case-output.cjs "$eval_dir"
```

The preparer writes `eval.json`, `status.json`, and the blind prompts into `eval_dir`. The binder assigns `cases/<dir>/` for each case's orientation and Maps response while preserving its message verbatim. Proceed only if both commands exit zero. The default is `--streets 10 --scenarios 20`.

## Scenarios and door numbers

- Each street gets a random door number (1-160), shared by its three variants; expected outcomes come from what Google returns, not from a number-10 probe.
- On top of the 30 street cases, `--scenarios N` (default 20, `0` disables) adds N total cases sampled as evenly as possible across `missing_number`, `multiple_matches`, `postal_only`, `poi`, `poi_note`, `two_addresses`. They sample only inputs recorded by `python3 maps/geolocation_evals/_factory/tools/verify_scenarios.py` (re-run it to refresh `verified_scenarios.json`).
