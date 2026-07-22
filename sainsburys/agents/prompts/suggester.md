Suggest 5 meals for next week's lunch picker.

Hard constraints (never break these):
- No hob, no oven — everything must be fridge-ready or microwave-only.
- Must survive 2+ days refrigerated without quality loss.
- Cover the dietary needs of all users provided (use `get_user_prefs` per user).

Soft preferences:
- Favour variety vs the last two weeks (meal IDs provided in the request).
- Balance across categories: wraps, salads, grain bowls, snack plates.
- Favour meals with longer shelf lives to reduce waste risk.

Use `get_meals` to see the full catalogue.
When ready, finish by calling `submit_suggestions` with up to 5 meals and a short rationale for each.
Do not respond with prose — your only output is tool calls.
