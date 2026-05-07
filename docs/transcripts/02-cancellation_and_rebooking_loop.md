# Sample thread — reschedule loop firing **N ≥ 3** times

This is the Scrini-required stress case: the prospect confirms, then backs out repeatedly. The perception layer must flag cancellations, deterministic state bookkeeping flips concrete holds to **`cancelled`**, and planner prompts always carry full transcript memory so continuity never resets.

## Loop walkthrough

1. **First booking** (`slot A` stub ISO) → `BOOKED`.
2. **Cancellation #1**: “Emergency — cannot make tomorrow’s slot.” → Perception emits `is_cancellation_of_scheduled_call = true`; state machine cancels newest active booking (`confirmed|proposed` → `cancelled`), increments `reschedule_count`, phase `RESCHEDULE_OFFERED`.
3. **Re-offer**: Agent empathizes briefly, summarizes prior agreement, proposes fresh **`slot B`** and **`slot C`** from stub inventory.
4. **Second booking**: Prospect confirms `slot B` → bookings append new `BookingRecord(confirmed)` while cancelled rows remain immutable evidence.
5. **Cancellation #2**: “Kick moved my afternoon — reschedule?” Repeat cancellation pipeline; **`reschedule_count`** ticks again **without wiping history**.
6. **Third booking**: Prospect grabs `slot C`. Optional fourth cancellation behaves identically—the loop never depends on branching depth.

## Why reviewers care

- **`booking_history` is append-only truth** rather than overwriting prior commits.
- **Prompt construction always replays chronological transcript + serialized state**, guaranteeing the persona cannot “forget” earlier promises.
- **Stub calendar intentionally narrow** — production swaps for Google Calendar CRUD via the same orchestration seam.
