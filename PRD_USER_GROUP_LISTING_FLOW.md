# Product Requirements Document (PRD)
## Padly User -> Group -> Listing Flow (v3)

Last updated: 2026-03-21  
Status: Draft v3 (neural cutover plan added)

## 1) Objective

Build an end-to-end flow where:
1. A user registers and provides profile + housing preferences.
2. The user discovers and joins a compatible roommate group.
3. The group receives listing recommendations that pass hard constraints first, then are ranked by a neural-first recommender with rule/behavior fallback.

## 2) Product Principle

Padly is a two-stage matching product:
- Stage A/B: match a **single user** to a **group**.
- Stage C/D: match a **group** to **listings**.

This is the correct architecture for the intended user experience and data model.

## 3) Scope

### In Scope (v1-v3)
- User onboarding and preference capture.
- User -> Group ranking and join workflow.
- Group preference aggregation.
- Group -> Listing hard-filter + neural ranking feed.
- Swipe event collection and ranking features.
- Deterministic fallback when neural model is unavailable.
- Sunset of legacy stable matching for Group -> Listing path.

### Out of Scope (for now)
- Fully ML-driven user -> group ranking.
- Replacing current User -> Group matching service (keep existing logic for now).
- Real-time chat and collaborative decision workflows.
- Landlord-side personalization.

## 4) Canonical Preference Model

## 4.1 Hard Preferences (filter only)
- `target_city`
- `target_state_province`
- `budget_min`
- `budget_max`
- `required_bedrooms`
- `move_in_date`
- `target_lease_type`
- `target_lease_duration_months`

## 4.2 Soft Preferences (ranking only)
- `target_bathrooms`
- `target_furnished`
- `target_utilities_included`
- `target_deposit_amount`
- `target_house_rules`
- `lifestyle_preferences` (JSON)
- `preferred_neighborhoods` (array)

Rule: hard constraints are never used as tie-breakers. They are pass/fail gates.

## 5) End-to-End Flow

### Stage A: User Onboarding
- User registers.
- User completes profile.
- User saves hard + soft preferences.
- Optional onboarding swipes to initialize behavior vectors.

### Stage B: User -> Group Discovery
- Hard-filter groups by user hard constraints.
- Rank eligible groups by compatibility.
- User requests to join group.
- Group owner/admin accepts or rejects.

### Stage C: Group Preference Formation
- On join/leave/accept events, recompute group profile.
- Group profile becomes source-of-truth for listing discovery.

### Stage D: Group -> Listing Discovery
- Hard-filter listings by group constraints.
- Rank eligible listings with neural-first scoring + rule/behavior fallback.
- Expose top-N ranked feed and explanation to group.
- No one-to-one stable assignment step in this stage.

### Stage E: Feedback Loop
- Persist every swipe event.
- Build user behavior features continuously.
- Build group behavior features from member aggregates.

## 6) Group Aggregation Rules (Required)

These rules remove ambiguity and must be implemented exactly unless revised.

### 6.1 Hard Fields Aggregation
- City/state: exact consensus required.
  - If conflict: mark `group_hard_conflict.city_state = true`; block listing ranking until resolved.
- Budget range:
  - `group_budget_min = max(member_budget_min)`
  - `group_budget_max = min(member_budget_max)`
  - If `group_budget_min > group_budget_max`: conflict state, block listing ranking.
- Required bedrooms:
  - `group_required_bedrooms = max(member_required_bedrooms, member_count)`
- Move-in date:
  - `group_move_in_date = median(member_move_in_date)`
  - Hard window check uses `abs(member_date - group_move_in_date) <= 45 days` for all members.
  - If violated: conflict state.
- Lease type:
  - If all set and not equal: conflict state.
  - If some unset: use set value if unanimous among set members.
- Lease duration:
  - Use median if all within +/-3 months; else conflict state.

### 6.2 Soft Fields Aggregation
- Numeric fields (bathrooms/deposit): median.
- Boolean fields (furnished/utilities): majority vote with confidence score.
- Text (`target_house_rules`): normalized keyword merge + conflict tags.
- Lifestyle JSON: key-wise majority/median depending on value type.

## 7) Ranking Specifications

## 7.1 User -> Group

Hard gates:
- city/state compatible
- budget overlap
- move-in window
- group has open spot

If hard pass:
`user_group_score = w_lease*lease + w_amenity*amenity + w_lifestyle*lifestyle + w_trust*trust + w_behavior*behavior`

Default weights:
- `w_lease = 0.20`
- `w_amenity = 0.15`
- `w_lifestyle = 0.35`
- `w_trust = 0.15`
- `w_behavior = 0.15`

## 7.2 Group -> Listing (Neural Ranker, No Stable Matching)

Hard gates:
- city/state
- budget feasibility for group size
- bedrooms >= group size
- availability window
- lease compatibility

If hard pass:
`final_score = w_rule*rule_score + w_behavior*behavior_score + w_ml*ml_score`

Where:
- `rule_score` in [0,1] from soft preference scoring.
- `behavior_score` in [0,1] from swipe-derived features.
- `ml_score` in [0,1] from two-tower model.

Default weights by data maturity:
- Cold start (<20 group swipes): `w_rule=0.80`, `w_behavior=0.20`, `w_ml=0.00`
- Warm start (20-99 swipes): `w_rule=0.50`, `w_behavior=0.25`, `w_ml=0.25`
- Mature (>=100 swipes): `w_rule=0.35`, `w_behavior=0.20`, `w_ml=0.45`

If ML unavailable:
- Force `w_ml=0` and re-normalize rule/behavior weights.
- System must still return 200 with deterministic ranking.

Operational rule:
- Group -> Listing uses direct ranking only.
- Deferred-acceptance/Gale-Shapley is not part of this path.

## 8) Swipe Event Contract (Required)

Every swipe must persist:
- `event_id` (UUID)
- `actor_type` (`user`)
- `actor_user_id`
- `group_id_at_time` (nullable)
- `listing_id`
- `action` (`like` | `pass` | `super_like` optional)
- `surface` (`discover`, `onboarding_discover`, etc.)
- `session_id`
- `position_in_feed`
- `algorithm_version`
- `model_version` (nullable)
- `created_at` (UTC)

Optional context:
- city filter
- active preference snapshot hash
- latency_ms

Idempotency key:
- `actor_user_id + listing_id + session_id + position_in_feed`

## 9) Recompute Triggers and SLOs

## 9.1 Triggers
- Recompute user -> group ranking on:
  - user preference update
  - group membership change
  - group preference conflict resolution
- Recompute group -> listing ranking on:
  - group composition change
  - group preference update
  - new/updated listing in target city
  - swipe batch ingestion (every 15 minutes)

## 9.2 Latency SLOs
- User -> Group ranking API:
  - p50 < 200ms
  - p95 < 700ms
- Group -> Listing ranking API:
  - p50 < 300ms
  - p95 < 900ms
- Hard-filter eligibility correctness: 100% (no violations in output set).

## 10) Explainability Requirements

For each recommendation return:
- `hard_pass=true`
- top 3 positive contributors
- top 1 negative contributor
- score breakdown:
  - rule
  - behavior
  - ml
  - final

For excluded candidates return a rejection code:
- `CITY_MISMATCH`
- `BUDGET_MISMATCH`
- `DATE_MISMATCH`
- `BEDROOM_MISMATCH`
- `LEASE_MISMATCH`
- `GROUP_CONFLICT`

## 11) Fairness, Safety, and Quality Guardrails

- Do not rank on protected attributes directly.
- Prevent single-member dominance in group behavior:
  - per-member contribution cap (max 40% of group behavior vector weight).
- Add audit logs for ranking inputs and outputs.
- Run weekly drift checks:
  - hard-pass rate
  - like-rate by city
  - model score calibration

## 12) Lifecycle Edge Cases

- Group owner leaves:
  - auto-transfer ownership before ranking operations continue.
- Member leaves after shortlist:
  - invalidate shortlist if hard constraints change.
- Contradictory hard prefs in group:
  - set conflict state; block ranking; prompt resolution UI.
- Listing removed after ranking:
  - remove from feed and backfill next candidate.
- Sparse swipe history:
  - behavior score defaults to neutral prior.

## 13) Success Metrics (Numeric Targets)

Activation:
- >=80% of new users complete preferences in first session.

Group funnel:
- >=35% of onboarded users request to join at least one group in 7 days.
- >=20% join acceptance rate in 7 days.

Listing quality:
- 100% of presented listings satisfy hard constraints.
- +15% swipe-like rate vs rules-only baseline after ML rollout.

Outcome:
- +10% match confirmation rate (group + listing) in 60 days.

Reliability:
- recommendation 5xx rate <0.5%.

## 14) Rollout Plan With Gates

### Phase 1: Rules-First Flow (legacy)
Deliver:
- user -> group rules ranking
- group -> listing hard+soft rules baseline
- swipe event storage
- deterministic fallback

Exit gate:
- hard-pass correctness = 100%
- no blocker edge-case bugs
- API p95 within SLO

### Phase 2: Behavior Features
Deliver:
- user and group behavior vectors
- behavior score in production ranking
- explainability payload

Exit gate:
- +8% swipe-like rate over Phase 1
- no regression in hard-pass correctness

### Phase 3A: Neural Group -> Listing Foundation
Deliver:
- introduce dedicated Group -> Listing neural ranking endpoint
- two-tower inference in Group -> Listing ranking path
- dynamic weights by swipe volume (rule/behavior/ml blend)
- explainability payload and score breakdown in endpoint response
- hard-filter correctness guardrail before scoring (must-pass gate)
- shadow/parallel-read mode to compare neural-ranked output vs legacy output
- feature flag + rollback kill-switch (default OFF)

Exit gate:
- 100% hard-pass correctness in shadow mode
- Group -> Listing ranking p95 within SLO (<900ms)
- recommendation 5xx rate <0.5%
- no blocker regressions in explanation payload contract
- stable fallback proven (model unavailable still returns ranked list)

### Phase 3B: Neural Cutover + Stable Sunset
Deliver:
- switch Group page listing feed to neural endpoint as primary source
- gradual traffic ramp (for example 10% -> 25% -> 50% -> 100%)
- keep kill-switch for instant rollback to prior serving path
- stop creating new stable Group -> Listing assignments for live serving
- keep stable matching data read-only for historical/audit access
- update runbooks, alerting, and owner on-call procedures for neural serving

Exit gate:
- 100% production traffic served by neural Group -> Listing path
- +15% swipe-like rate vs Phase 1 baseline
- >=99.5% availability at full traffic
- no fairness guardrail violations
- zero dependency on stable matching for Group -> Listing serving path

## 15) Functional Acceptance Criteria

- New user can:
  - register
  - save preferences
  - see ranked groups
  - request group join
- Existing group can:
  - see only hard-eligible listings
  - receive neural-ranked listings with score explanations
- If ML model fails:
  - endpoint still returns ranked list using deterministic fallback
  - no 500 due to model load/inference failure

## 16) Architecture Decision Update (2026-03-21)

Decision:
- Keep User -> Group matching as currently implemented.
- Replace Group -> Listing stable matching with neural ranking.

What changes:
- Group listing feed is produced by neural/rules/behavior ranking after hard filters.
- Stable matching endpoints/tables become legacy for historical data only.

What stays the same:
- User onboarding and preferences flow.
- User -> Group discovery and join workflow.
- Swipe telemetry and behavior feature extraction.

Cutover requirements:
- Add a dedicated Group -> Listing neural endpoint and move group pages to it.
- Keep fallback scoring active when model inference is unavailable.
- Keep explainability payload for every returned listing.
