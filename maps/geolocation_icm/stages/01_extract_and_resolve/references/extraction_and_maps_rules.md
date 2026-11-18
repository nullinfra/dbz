# Extraction, resolution loop, and Maps rules

Decision rules for Stage 01. Follow the [tool rules](../tools/rules.md) for commands and tool behavior.

## Classification (`is_address`)

- This is a yes/no gate, not address parsing. Read the original message and decide only whether it contains or represents a navigable destination.
- Do not populate `extracted_query` or `sub_premise_notes` while making this decision. Produce them only after `is_address` is `true`.
- `true` only when the text contains or represents an address, street, postal code, or navigable location.
- An address may be incomplete; a street or postal code without a premise number still classifies `is_address=true`.
- A place name is address-like only when it clearly identifies a navigable destination, not merely a product or topic in conversation.
- When `false`, stop Stage 01 immediately: write `orientation.json` with `is_address: false`; do not run extraction, query building, or `google_maps.py`.

## Extraction

- Run this step only after classification has set `is_address: true`. It transforms the original customer message into the two distinct fields below; it does not decide whether the message is an address and does not call Maps.
- `raw_text` is the customer's message, verbatim.
- Identify whether the destination is a named place (`poi`) or a street address (`address`). A named place used only as a landmark remains a note, not a POI destination.
- Identify separate alternative delivery addresses before searching. Preserve each address exactly as supplied, including its number, in `address_alternatives`. Alternatives are distinct from a nearby landmark, a pickup and delivery pair, or several Maps matches for one address. For alternatives, search the first address alone and ask which delivery address is intended; do not select one or provide a final ETA. Preserve every alternative even if the lookup fails.
- A POI destination needs confirmation of the place and proposed address even when Maps returns an exact street address. If multiple places match, ask which one; if none matches, request more detail.
- `extracted_query` holds street, door number, customer-supplied locality, and postal code. Strip greetings, thanks, requests, and delivery prose.
- `sub_premise_notes` holds apartment, floor, doorbell, block, unit, gate, landmark ("ao lado do café"), and access instructions. A landmark never goes into the Maps query.
- Never inject `Corroios`, a municipality, or a country that the customer did not state.
- `locality_stated` is `true` only when the message names a locality, municipality, or postal code; otherwise `false`.

## Attempt 1

Build the query from the customer's address text exactly as written, stripping only greetings and prose. Do not expand abbreviations, restore spaces, or correct spelling yet.

## Judging an attempt

**The tool reports, the model judges.** `google_maps.py` never filters, corrects or scores candidates. For every attempt the model gives one verdict:

- `accepted`: a candidate is clearly the customer's street/place (same name after ignoring case, accents, abbreviations).
- `uncertain`: a candidate is plausibly what the customer meant but is not certain (typo corrected by Google, one-letter difference, similar-sounding street). The deterministic policy will require customer confirmation.
- `rejected`: `ZERO_RESULTS`, or nothing resembles what the customer wrote (country/region/road-code fallback, unrelated street or locality).

**Signals to read** (all raw Google facts): `partial_match`, candidate `types`, `location_type`, `has_street_number`, `premise_verified` (`true` only for a `ROOFTOP` geocode, `null` without a street number), `address_validation.verdict.*` and `address_validation.components[]` (`spell_corrected`, `replaced`, `inferred`, `unexpected`, `confirmation_level`; `hasReplacedComponents` can be null while a component is `spell_corrected`, so read the components), and `other_search_candidates` (results of the search that was not used when the service-area bias applied).

## Resolution loop

- On `rejected`, re-read `raw_text` and retry with a new hypothesis. Every query is distinct; never repeat one.
- Stop as soon as an attempt is `accepted` or `uncertain`, an API error occurs, or no plausible hypothesis supported by `raw_text` remains (never force extra retries on clearly non-existent words).
- Record every query once, with verdict and note, in `attempts`.
- Hypotheses, best first:
  0. Normalize the text: expand street-type abbreviations (`tv` → `Travessa`, `pct` → `Praceta`, `r.` → `Rua`) and restore obviously missing spaces. Do this first on the second attempt, with no spelling changes.
  1. Google's own correction, only when supported by the original customer text: the `route` component text of `address_validation` when it is `spell_corrected`/`replaced`, combined with the customer's door number and locality.
  2. Fix likely typos, phonetic or keyboard slips in the street words, toward a real Portuguese street name that the letters in `raw_text` support.
  3. Different token boundary between filler and street name (e.g. trailing `obrigado`, fused access words).
  4. Alternative street type (`Rua`/`Travessa`/`Avenida`/`Praceta`/`Alameda`), numerals (`XVII`, `25 de Abril`), restored diacritics.
  5. Drop the door number or the locality if either may be causing the mismatch.
- Compare every proposed correction to the original customer text, not merely the previous query. A locality such as Corroios is never a street match. Reject unrelated suggestions and do not treat them as customer options.
- **Corrections must be supported by the customer's letters.** A retry may fix typos, phonetics, abbreviations, numerals or token boundaries. It must not swap in a street the message does not support letter by letter, and never invents geography the customer did not state. Any result reached through a correction is at best `uncertain`, so the deterministic policy requires customer confirmation.

## Fallback

If every attempt is `rejected`, save the attempt with the most plausible candidates (or the last attempt when none had any). The deterministic policy returns the failure and the question. `extracted_query` is that attempt's query.

## Store and service area

The Maps and policy tools read this configuration:

```json
{"origin_name": "DoBrasil Pastéis, Corroios, Portugal", "origin_place_id": "place_id:ChIJc54Vp1_LHg0RYKhoEVjLJE4", "locality": "Corroios", "driving_distance_meters": 50000}
```
