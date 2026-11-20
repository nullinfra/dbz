# Review catalogue choices for orders

Review every line after expanding the basket. This applies to new orders and to new or replacement lines on an existing order. Read the latest catalogue description. For native options, fetch the product detail with `check_menu_item` and `include_details: true`.

## Interpret the current offer

- Identify what is included and what the customer chooses. Read variants, required modifier groups, quantity limits, eligible formats, and published restrictions. An included component needs no customer choice. For example, a menu description can provide a fixed side and ask the customer to choose a drink. Ask for the drink using the eligible options.
- For a box or other mixed item, calculate the breakdown using the currently advertised totals and conditions. If the description gives alternative compositions, resolve which alternative applies before setting the counts. Preserve the customer's picks across turns.
- Check restrictions for the requested service and date in Europe/Lisbon. Prefer an explicit term specific to the item when its scope is clear. If sources conflict or options are missing, ask the merchant for the current terms or offer a verified alternative to the customer. Record any remaining question in the review.
- For frozen items, state how the item is supplied and ask for acknowledgement when the customer hasn't already given it. One acknowledgement can cover all stated frozen items. For fixed products, check whether a requested change is an available variant, modifier or explicitly offered option. If a customer wants a different product, obtain their selection before substituting it.
- If an allergy is mentioned, use the merchant's verified allergen information, including applicable cross-contact information. Product names and brief descriptions are insufficient to clear an allergy. Leave the order pending until the suitability of the relevant selections is verified. Record the confirmed source in `allergy_review`.

## Record the evidence and selections

Copy the exact `product_id`, product `name`, catalogue `category_id`, and `description` from the live result. Capture the variant by `variant_id` when there is more than one. In `modifiers`, use `{"modifier_id":"<verified UUID>","quantity":1}` for each selected native modifier. The executor checks membership and limits against the current product details.

Each reviewed line requires `product_id`, `name`, a positive integer `quantity`, and `catalog_review` with all four keys from the [review schema](../../../../_shared/schemas/catalog_review.schema.json). Store the agent's interpretation of choices described in prose in `catalog_review`. Each group contains its label, minimum, maximum (or null), selected names and counts per unit. Include a natural `question` for incomplete groups. A selection that is also a catalogue product should include its verified `product_id`. Choices specific to a menu can use the published name or a name confirmed by the merchant. Include one `{"question":"..."}` per unresolved condition that falls outside the group counts.

```json
{
  "category_id": "<category UUID from the live result>",
  "description": "<exact catalogue description, or null>",
  "groups": [
    {
      "label": "Bebida",
      "min": 1,
      "max": 1,
      "selections": [],
      "question": "Qual é a bebida que preferes?"
    }
  ],
  "issues": []
}
```

A fully reviewed line without prose choices has empty `groups` and `issues`. Keep unresolved variant or modifier choices in `issues`. Review the line again if the service, schedule, product description, or options change. Split quantities into separate lines when customizations differ. A saved draft that only has `choices` strings needs a fresh review. Use its confirmed choices to populate the new fields.
