# Product requirements


## Scope and principles

cricAI combines an Android cricket auction with later explainable squad analysis.
Financial correctness, real-data provenance and premium mobile UX are independent
requirements. Infrastructure budget is INR 0. No publishing, commits, accounts
with external providers, purchases or deployment without explicit approval.

## Requirements by phase

| Requirement | Delivery |
| --- | --- |
| Flutter Android, shared server auction engine, PostgreSQL migrations | Phase 1 |
| Versioned rules, 15-second reset, valid sold/unsold, budgets, ownership | Phase 1 |
| Original brand, home/auction screens, accessible states, visual review | Phase 1 |
| Source register, verified import, immutable snapshot, local manual rivals | Phase 1 |
| Three bot difficulties/personalities, curated pool, up to two marquees | Phase 2 |
| Six-dimension deterministic scoring, scenarios, XI/report explanations | Phase 2 |
| Scheduled provider refresh, richer source coverage | Phase 2 |
| Email auth/verification/reset, profiles, saved history/account recovery | Phase 3 |
| Private rooms, host controls, 30-second disconnect grace, reconnect | Phase 4 |
| Security/performance hardening, physical-phone APK release testing | Phase 5 |

## Foundation rules

The local development profile is not the finished compact solo mode. Manual rival
participants send commands through the same server path as the Android user.
No arbitrary client may assume another participant's identity.

Version `foundation-v1`: 15-second no-accepted-bid deadline, INR 100 crore purse,
12-player squad cap, at most four overseas players, INR 20 lakh default base price,
INR 10 lakh increment. All monetary defaults are **game-configured**, not official
IPL values. A bid must equal the current next price; no jump/self-outbids.
At the exact server deadline a bid is late. No offline bid queue.

Ten verified franchise identities belong to the standard selected season. No
season is selected until required records and rights pass validation. Test-only
profiles may have fewer teams/players, prominently labeled as test data.
Marquee selection UI/cost deduction is Phase 2; foundation starts with empty squads.

## Compact mode design target

Future `compact-v1` targets 100-120 candidates, adjusted to unfilled squad slots,
domestic/overseas and role supply. Up to two verified franchise marquees count
toward squad limits and budget, and are excluded from the pool. Prices have
explicit official or game-configured provenance. Proposed marquee game cost is
INR 5 crore per player, subject to Phase 2 rule review, not a historical salary.
Standard settings stay fixed; custom tournaments are future configuration.
120 no-bid lots already take 30 minutes, before presentations and bids; test
actual pacing before describing the full mode as a short session.

Completion can have incomplete squads after unsold lots. Report those shortfalls;
never fabricate players or a valid playing XI. No forthcoming official-auction
eligibility claim without a verified list. Available candidates are game-curated.

## Deferred scope

No match simulator, management seasons, LLM numerical authority, monetization,
website, Play publishing, or pay-to-win mechanics. Future auth must use secure
hashing, expiring/revocable credentials, rate limits, local email delivery and
OS-backed mobile storage. Multiplayer must preserve actions after disconnect,
use server grace timing and transactionally reconcile host-requested re-auctions.