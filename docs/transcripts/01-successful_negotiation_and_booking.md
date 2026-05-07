# Sample thread — negotiation + stub booking success

Synthetic narrative consistent with preset `default_demo` (ceiling \$120/hr, stub ISO slots enumerated in config).

| Turn | Sender | Highlights |
| --- | --- | --- |
| 1 | Agent | Introduces the AI tooling gig, references role focus, proposes next step and available windows. |
| 2 | Prospect | “Interested — what’s realistic on rate? Could you stretch to \$90/h?” |
| 3 | Agent | Confirms fit within budget envelope, summarizes scope crisply, offers two RFC3339 slots from stub list (`2026-05-12T14:00:00+00:00`, `2026-05-13T16:30:00+00:00`). |
| 4 | Prospect | “Let’s lock `2026-05-13T16:30:00+00:00`. Send invite.” |
| 5 | Agent | Confirms stub calendar hold (`internal_action = confirm_booking`), mirrors agreed slot, proposes backup rescheduling path. Conversation phase moves to **`BOOKED`**. |

Operational notes demonstrated:
- Persisted **`ConversationState`** records negotiation facts + **`booking_history`** snapshots.
- Deterministic **`StubCalendar`** guardrails prevent phantom bookings outside configured ISO strings.
