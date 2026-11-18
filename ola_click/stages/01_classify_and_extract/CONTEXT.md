# 01_classify_and_extract — stage context

Classifies any incoming text and extracts structured OlaClick intent and entities without calling the OlaClick MCP or API.

## Inputs

- Working input: the raw text supplied in the caller's query.
- Decision rules: [intent and extraction rules](references/intent_and_extraction_rules.md).
- Tool rules: [tool rules](tools/rules.md).

## Process

Read both reference files and follow them together. Run all commands from the project root (`Restaurante/`). Never read any `.py` file; invoke `ola_click/stages/01_classify_and_extract/tools/write_stage01.py` as a black-box command.

## Outputs

- `ola_click/output/runs/<run_id>/stage01_intent.json`

## Check

`write_stage01.py` validates the schema and exits `0` only when `stage01_intent.json` is valid. Proceed to Stage `02_resolve_and_execute` only when Stage 01 exits `0`.
