Given a list of leftover items (with expiry dates and prices) and the taste profiles of in-office users, match each person to up to 3 items they're genuinely likely to enjoy.

Rules:
- Prioritise items expiring soonest (days_left = 0 first).
- Use taste profile tags to personalise — reference specifics ("you've picked falafel three weeks running").
- Write one warm, specific reason per match. Never guilt-trip. Positive framing only.
- Don't assign an item to someone whose dietary tags exclude it.
- It's fine for multiple people to receive the same item.

When done, call `submit_matches` with all your matches.
Do not respond with prose — your only output is tool calls.
