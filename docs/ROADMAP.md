# Roadmap

0. Assess tooling, document requirements, architecture, sources, scoring, design
   tokens, local setup and decisions. Record blockers, not assumed capabilities.
1. Pure auction domain -> PostgreSQL transactions/API/import -> manual rival
   harness -> branded Flutter home/auction -> integration, build and visual gates.
   Each edit is followed by the smallest relevant test before extending scope.
2. Only after review: strategic bots, personalities, marquees, curated pool,
   deterministic scoring/scenarios and premium report UI.
3. Email authentication, local test mail, secure recovery, user profiles and saved
   histories. Core financial durability already belongs to Phase 1.
4. Private multiplayer, bots filling seats, shared state, host controls, server
   disconnect grace and controlled re-auction with compensating history.
5. Hardening, performance/accessibility, installable APK, actual physical Android
   wireless-debugging verification. No public release/deployment without approval.

Every phase has separate functional, data-rights, security and visual gates.
Completion requires exact command/results and explicit unverified items in build
progress. Never remove meaningful tests or replace PostgreSQL to obtain green tests.