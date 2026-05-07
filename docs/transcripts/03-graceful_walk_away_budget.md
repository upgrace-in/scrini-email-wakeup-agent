# Sample thread — graceful walk-away on comp mismatch

Demonstrates Scrini expectation: never exceed **`budget_ceiling_usd_hour`**, and politely disengage rather than hallucinate concessions.

## Sequence

| Turn | Notes |
| --- | --- |
| Agent outreach | Mirrors tone preset (`friendly_professional`) with crisp CTA |
| Prospect | “Love the problem — minimum is \$150/h fixed.” (`quoted_rates_usd_hour` extracted by perception ≥ ceiling) |
| Deterministic shortcut | Orchestrator observes `budget_impossible` (`min(rate) > ceiling`) and bypasses speculative negotiation drift |
| Final agent email | Transparently cites ceiling constraint without sounding adversarial, closes thread under **`CLOSED_NO_FIT`** |

## Guardrail layering

1. **`PerceptionResult.quoted_rates_usd_hour`** surfaces numerics grounded in prose.
2. **`budget_impossible`** is *pure arithmetic* executed before hallucination-prone text generation expands scope.
3. Thread memory stores ceiling snapshot inside persisted gig JSON so reopened threads cannot contradict agreed finance bounds.
