# 01_extract_and_resolve — stage context

This stage processes the customer message supplied in the caller's query.

## Inputs

- Working input: the customer message supplied in the caller's query.
- Decision rules: [extraction and resolution rules](references/extraction_and_maps_rules.md).
- Tool and command rules: [tool rules](tools/rules.md).

## Process

Read both reference files and follow their instructions together. Apply the decision rules to the working input and use the tools as specified by the tool rules. Never read any `.py` file or `_config/*` source files.

## Outputs

The tool rules specify the output files and when each is produced.

## Check

Use the finalizer's exit status and output check specified in the tool rules. This stage uses the exit check instead of a separate `check.md` to avoid a redundant artifact.
