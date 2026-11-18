# golden.json — case schema and deterministic checks

Each entry in `evals/_factory/golden.json` is one test case:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique case identifier (e.g., `1001_non_address_greeting`) |
| `kind` | yes | Category slice: `non_address`, `exact_within_50km`, `exact_outside_50km`, `multiple_matches`, `not_found`, `missing_door_number`, `partial_match`, `adversarial_profanity`, `multilingual` |
| `split` | yes | `dev` or `test` |
| `input` | yes | Raw WhatsApp message written verbatim to `input/whatsapp_payload.md` |
| `notes` | yes | Human intent description for audit (never sent to the case agent) |
| `expected_input` | yes | Expected Stage 01 fields (`is_address`, optional `extracted_query` / `sub_premise_notes`) |
| `expected_orientation` | yes | `null` when Stage 01 halts, or object of expected Stage 03 fields (`is_address`, `within_50km`, `has_multiple_matches`, `needs_clarification`, `clarification_reason`, `resolution_status`) |
| `exp_message_must_contain` | no | List of case-insensitive regexes that `suggested_customer_message` must match |
| `exp_message_must_not` | no | List of case-insensitive regexes that `suggested_customer_message` must NOT match |

## Always-run deterministic checks

1. `run.complete`: `orientation.json` exists and parses, and address cases also have `maps_raw_output.json`. Historical artifacts are scored using their original checks.
2. `run.no_eval_leak`: no generated output file mentions `evals/`, `golden.json`, or `exp_stage`.
3. `input.fields`: Stage 01 matches `expected_input`.
4. `input.trace`: the final selected Maps query matches a recorded attempt (when Stage 01 continued).
5. `policy.fields`: `orientation.json` matches `expected_orientation` (or contains `is_address: false` when `expected_orientation` is `null`).
6. `policy.grounded_facts`: when `orientation.json` exists, `eta` matches the single candidate's `driving_eta_text` (or is `null` for multiple/unresolved), and `within_50km` matches the measured `driving_distance_meters` against the service-area configuration in the extraction rules.
7. `policy.message_regex`: `suggested_customer_message` satisfies `exp_message_must_contain` and `exp_message_must_not`.
