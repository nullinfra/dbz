# 01_extract_and_resolve — stage context

This stage processes the customer message supplied in the caller's query.

## Inputs

- Working input: the customer message supplied in the caller's query.
- Output assignment: the current [chat message directory](../../../../tools/chat-output.md) or the evaluation case paths supplied by the caller.
- Decision rules: [extraction and resolution rules](references/extraction_and_maps_rules.md).
- Tool and command rules: [tool rules](tools/rules.md).

## Process

Read both reference files and follow their instructions together. Apply the decision rules to the working input and use the tools as specified by the tool rules. Never read any `.py` file or `_config/*` source files.

Run all commands from the project root. Never create `stages/*/output/` or copy stage files.

- **Chat run**: use `<message_dir>/maps/` for the whole run. Pass its path to each tool as documented and clean up the intermediate Maps file when finalizing.
- **Eval case**: use the output directory and Maps response path assigned in the case prompt. Retain the Maps response for scoring.

## Outputs

- Chat run: `<message_dir>/maps/orientation.json`.
- Eval case: `orientation.json` and `maps_raw_output.json` at the assigned paths.

## Check

Use the finalizer's exit status and output check specified in the tool rules. This stage uses the exit check instead of a separate `check.md` to avoid a redundant artifact.
