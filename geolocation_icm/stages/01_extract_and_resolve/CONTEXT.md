# 01_extract_and_resolve — stage context

This stage processes the customer message supplied in the caller's query.

## Inputs

- Working input: the customer message supplied in the caller's query.
- Decision rules: [extraction and resolution rules](references/extraction_and_maps_rules.md).
- Tool and command rules: [tool rules](tools/rules.md).

## Process

Read both reference files and follow their instructions together. Apply the decision rules to the working input and use the tools as specified by the tool rules. Never read any `.py` file or `_config/*` source files.

Run all commands from the `maps/` workspace root. Never create `stages/*/output/` or copy stage files.

- **Normal run**: invoke `write_stage01.py` and `google_maps.py` without `--out-dir` or `--out`; they automatically write `output/runs/<run_id>/orientation.json` and clean up intermediate Maps files.
- **Eval run**: when the prompt specifies an explicit output directory, pass `--out-dir "<out_dir>"` to `write_stage01.py` and `--out "<out_dir>/maps_raw_output.json"` to `google_maps.py`.

## Outputs

- Normal run: `output/runs/<run_id>/orientation.json` (plus `summary.md` written by the observer hook).
- Eval run: `<out_dir>/orientation.json` and `<out_dir>/maps_raw_output.json`.

## Check

Use the finalizer's exit status and output check specified in the tool rules. This stage uses the exit check instead of a separate `check.md` to avoid a redundant artifact.
