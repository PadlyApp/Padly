# Padly User Feedback Evaluation Spec

**Last updated:** 2026-04-05  
**Status:** Draft  
**Owner:** Padly team  
**Purpose:** Define a low-friction feedback feature that helps evaluate the quality of Padly's listing recommendation system, especially the two-tower ranking model, using real user data.

---

## 1. Objective

Padly is being used as a research / course project to test whether the recommendation stack, and specifically the two-tower model, produces listings that feel relevant to real users.

The goal of this feature is to collect **simple, high-signal user feedback** on recommendation quality without adding enough friction to reduce participation or distort behavior.

This feature should answer questions like:

- Do users think the listings shown to them are useful?
- Do users think the ranked matches reflect what they actually want?
- Does the two-tower ranked feed perform better than a simpler baseline?
- Are users engaging with recommendations because they are genuinely relevant, or just because inventory exists?

This is an evaluation feature first, not a general support or customer feedback feature.

---

## 2. Product Principles

The feature must follow these principles:

### 2.1 Low friction

Users should be able to submit feedback in **one tap** most of the time.

### 2.2 High signal

The feature should collect feedback that is easy to interpret and tie back to model quality.

### 2.3 Natural timing

The prompt should appear after a user has actually seen enough recommendations to form an opinion.

### 2.4 Minimal cognitive load

Avoid free text unless the user is already motivated to explain a negative experience.

### 2.5 Research usefulness

Collected feedback must be stored with enough context to compare ranking methods, positions, sessions, and recommendation cohorts.

---

## 3. Why Not Use a 1-10 Rating?

We intentionally do **not** use a `1-10` scale as the primary feedback signal.

Reasons:

- Different users interpret numeric scales differently.
- A `7/10` is ambiguous and difficult to operationalize.
- Numeric ratings create more decision effort than a few labeled choices.
- The signal is hard to compare across small sample sizes.
- It does not directly explain whether recommendations were useful.

Instead, the primary explicit feedback should use a **3-point usefulness scale**:

- `Not useful`
- `Somewhat useful`
- `Very useful`

This is easier for users and more reliable for analysis.

---

## 4. Proposed User Experience

## 4.1 Core feedback question

After a user has interacted with recommendations, ask:

> **How useful were these recommendations?**

Choices:

- `Not useful`
- `Somewhat useful`
- `Very useful`

This should be the main explicit evaluation signal.

## 4.2 Optional follow-up for negative feedback

Only if the user selects `Not useful`, show a second, optional one-tap question:

> **What felt off?**

Choices:

- `Too expensive`
- `Wrong location`
- `Not my style`
- `Too few good options`
- `Other`

This second step is optional and only appears after negative feedback.

## 4.3 No required free-text field

Do not require text input.

Optional text can be added later for research notes, but should not block submission.

## 4.4 Suggested prompt surfaces

Primary surfaces:

- `Matches` page, after the user has seen the ranked list
- `Discover` flow, after enough swipes or after a short recommendation session

Recommended first release:

- Start with the `Matches` page only
- Add `Discover` prompt later if needed

Reason:

- `Matches` is the clearest place where users see ranked recommendations and score ordering
- the prompt can refer directly to "these recommendations"
- fewer interruptions during swiping

---

## 5. Trigger Strategy

The feedback prompt should not appear immediately.

It should appear only after the user has had enough exposure to make a judgment.

## 5.1 Eligibility rules

A user becomes eligible for a feedback prompt when at least one of the following is true:

- they have swiped on at least `8` listings in the current session
- they have opened the `Matches` page and viewed the ranked list for at least `10` seconds
- they have opened at least `3` listing detail pages from recommended content

## 5.2 Frequency limits

To avoid annoyance:

- show at most once per recommendation session
- show at most once every `7` days per user by default
- do not show again after feedback is already submitted for the same session

## 5.3 Dismissal behavior

If the user closes the prompt without responding:

- mark the prompt as dismissed
- do not show again in the same session
- allow it again in a future eligible session

---

## 6. Scope of Evaluation

The feedback feature should evaluate recommendation quality at **three levels**.

## 6.1 Passive behavioral signals

Collected automatically:

- swipe action (`like`, `pass`, `super_like`)
- saves
- detail page opens
- dwell time on recommendation surfaces
- dwell time on listing detail pages
- rank position shown to the user

These are useful because they do not require extra user effort.

## 6.2 Explicit session-level feedback

Collected from the 3-point usefulness prompt:

- `Not useful`
- `Somewhat useful`
- `Very useful`

This is the cleanest explicit measure of recommendation quality.

## 6.3 Optional reason tags

Collected only after `Not useful`:

- `Too expensive`
- `Wrong location`
- `Not my style`
- `Too few good options`
- `Other`

This helps diagnose whether poor performance is caused by:

- ranking quality
- hard filters
- inventory limitations
- cold-start issues

---

## 7. Research Questions This Feature Should Support

The stored data should allow analysis of:

1. Do users rate two-tower-ranked recommendations as more useful than baseline-ranked recommendations?
2. Does explicit usefulness correlate with existing behavior signals like likes, saves, and detail opens?
3. Are top-ranked listings actually engaging users more than lower-ranked listings?
4. Do negative responses cluster around specific issues such as price mismatch or location mismatch?
5. Does model performance improve for users with more interaction history?

---

## 8. Recommended Experiment Design

Collecting feedback without a comparison group is useful, but limited.

To make the research stronger, Padly should compare at least two recommendation variants.

## 8.1 Minimum viable experiment

Assign each recommendation session to one ranking strategy:

- `two_tower`
- `baseline`

Where baseline can be:

- heuristic / blended ranking without live two-tower score
- rule-based ranking

Each shown recommendation session must log:

- experiment name
- variant name
- model version
- algorithm version

## 8.2 Why this matters

Without a baseline, the team can only conclude:

> users liked the recommendations

With a baseline, the team can conclude:

> users liked the two-tower recommendations more than the alternative

That is a much stronger research result.

## 8.3 Exposure bias note

Because the ranking model influences what users see, feedback data is inherently biased by exposure.

To reduce this problem:

- run an A/B test between rankers
- keep hard filters constant across variants
- only vary ranking logic

Do not compare sessions where inventory pools are fundamentally different.

---

## 9. Proposed Event / Data Model

Padly already stores swipe interactions. This feature adds a dedicated feedback record tied to a recommendation session.

## 9.1 New concept: recommendation session

A recommendation session represents one coherent recommendation exposure window.

Examples:

- one `Discover` session
- one `Matches` page visit

Recommended fields:

- `session_id`
- `user_id`
- `surface` (`discover`, `matches`)
- `started_at`
- `ended_at`
- `algorithm_version`
- `model_version`
- `experiment_name`
- `experiment_variant`
- `recommendation_count_shown`
- `top_listing_ids_shown`

## 9.2 Feedback record

Recommended fields for `user_recommendation_feedback`:

- `id`
- `user_id`
- `session_id`
- `surface`
- `rating_label`
  - `not_useful`
  - `somewhat_useful`
  - `very_useful`
- `reason_label` nullable
  - `too_expensive`
  - `wrong_location`
  - `not_my_style`
  - `too_few_good_options`
  - `other`
- `submitted_at`
- `algorithm_version`
- `model_version`
- `experiment_name`
- `experiment_variant`
- `swipes_in_session`
- `likes_in_session`
- `saves_in_session`
- `detail_opens_in_session`

## 9.3 Why session-level storage matters

This keeps the feedback tied to:

- what the user actually saw
- how the feed was ranked
- what they did before responding

Without session context, the rating becomes much less useful.

---

## 10. System Requirements

This feature should not stop at collecting feedback rows. It needs a complete evaluation loop:

1. collect feedback
2. store it with recommendation context
3. aggregate it into interpretable metrics
4. expose those metrics in an admin-only evaluation view

If any of these pieces is missing, the feature becomes much less useful for research.

## 10.1 Data storage requirements

The system must store enough data to answer:

- what the user saw
- how it was ranked
- what they did
- how they rated it
- which ranking strategy produced that session

Minimum required stored entities:

- recommendation session
- recommendation impressions or top shown listing set
- explicit usefulness feedback
- negative reason tag when provided
- passive engagement metrics tied to the same session

## 10.2 Aggregation requirements

The system should support easy querying of:

- total feedback submissions
- usefulness distribution
- usefulness by experiment variant
- usefulness by market
- usefulness by session surface
- usefulness by model version
- negative reason breakdown
- passive engagement metrics by experiment variant

This can be implemented with:

- direct SQL queries at first
- backend aggregation endpoints
- optional materialized views later if data volume grows

## 10.3 Reporting requirements

The team should be able to quickly answer:

- how many users gave feedback?
- what percent found recommendations useful?
- did `two_tower` beat `baseline`?
- where is the model underperforming?
- are results improving after model changes?

This should not require manual CSV cleanup every time.

---

## 11. Admin Evaluation Dashboard

Padly should include an **admin-only evaluation page** that displays the current research metrics in a simple, readable format.

This page is not for end users. It is for:

- the Padly team
- course-demo review
- professor-facing evaluation
- internal iteration on the ranking system

## 11.1 Goal of the dashboard

The dashboard should make it easy to inspect recommendation quality without querying the database manually every time.

It should answer:

- how the model is performing overall
- whether one ranking strategy outperforms another
- how users are reacting across markets and sessions
- whether recent model versions improved usefulness

## 11.2 Access control

The page must be admin-only.

Recommended access options:

- backend-protected admin route using existing admin secret or admin auth checks
- frontend route visible only to authorized admins

It must not be accessible to regular users.

## 11.3 Recommended page location

Suggested route:

- `/admin/evaluation`

Possible alternate route:

- `/admin/feedback-metrics`

## 11.4 Dashboard sections

The first version of the admin page should include these sections.

### A. Overview cards

High-level cards:

- total recommendation sessions evaluated
- total feedback responses
- prompt completion rate
- `% very useful`
- `% somewhat useful`
- `% not useful`

### B. Variant comparison

Compare:

- `two_tower`
- `baseline`

Show:

- response count by variant
- usefulness distribution by variant
- average ordinal usefulness score by variant
- save rate by variant
- detail-open rate by variant
- like rate by variant

### C. Trend view

Show performance over time:

- daily or weekly usefulness rate
- daily or weekly average score
- feedback volume over time
- variant performance trend

This helps detect regressions after model changes.

### D. Breakdown tables

Break down metrics by:

- market / city
- surface (`discover`, `matches`)
- model version
- cold-start bucket

### E. Negative feedback reasons

Show:

- counts by reason tag
- percentage by reason tag

This helps diagnose whether problems come from:

- price mismatch
- location mismatch
- style mismatch
- weak inventory

### F. Session behavior summary

Show relationships between explicit and passive signals:

- average swipes before feedback
- average saves per rated session
- average detail opens per rated session
- usefulness vs engagement

## 11.5 Filters

The admin page should support lightweight filtering:

- date range
- experiment variant
- market
- surface
- model version

These filters should apply across all sections on the page.

## 11.6 Export support

The dashboard should support easy export of evaluation data for research reporting.

Minimum export options:

- CSV export
- copyable summary stats

Optional later:

- downloadable charts
- professor/demo summary view

## 11.7 MVP recommendation

The first admin page does not need advanced charting or complex drill-downs.

A good MVP is:

- a few top KPI cards
- one variant comparison table
- one negative-reasons table
- one simple time-series chart

That is enough to make the system useful immediately.

---

## 12. Metrics

The team should define metrics before rollout.

## 12.1 Primary metric

**Usefulness rate**

Definition:

- `% of feedback responses marked "Very useful"`

Also track:

- `% Not useful`
- `% Somewhat useful`
- `% Very useful`

## 12.2 Secondary metrics

- average ordinal usefulness score
  - `Not useful = 0`
  - `Somewhat useful = 1`
  - `Very useful = 2`
- save rate per session
- detail-open rate per session
- like rate per impression
- top-5 engagement rate
- prompt completion rate

## 12.3 Diagnostic metrics

- usefulness by experiment variant
- usefulness by cold-start bucket
- usefulness by city / market
- usefulness by session surface
- usefulness by model version
- negative reason distribution
- usefulness by swipe count bucket

---

## 13. Success Criteria

The first version of the feature is successful if:

- the prompt completion rate is high enough to produce usable sample sizes
- users do not appear to be annoyed by the prompt frequency
- the team can compare usefulness across ranking variants
- the collected data is structured enough to support a final course-project evaluation
- the admin dashboard makes results easy to review without ad hoc manual querying

Suggested early targets:

- prompt completion rate: `>= 35%`
- explicit negative feedback share is interpretable, not mostly missing
- experiment variant is present on `100%` of logged feedback rows
- session linkage is present on `100%` of logged feedback rows
- key dashboard metrics refresh correctly from stored data

These targets can be revised after pilot usage.

---

## 14. Rollout Plan

## Phase 1: Feedback Contract

Goal:

- lock the exact v1 feedback contract before any UI or backend implementation starts

Phase 1 decisions to lock:

- launch surface: `Matches` only
- prompt format: lightweight bottom sheet or inline card, not a blocking full-screen modal
- core question:
  - `How useful were these recommendations?`
- helper copy:
  - `Your feedback helps us improve how listings are ranked.`
- explicit feedback choices:
  - user-facing labels:
    - `Not useful`
    - `Somewhat useful`
    - `Very useful`
  - stored enum values:
    - `not_useful`
    - `somewhat_useful`
    - `very_useful`
- negative follow-up behavior:
  - show only after `Not useful`
  - make it optional
  - allow one-tap dismissal
- negative follow-up question:
  - `What felt off?`
- negative reason choices:
  - user-facing labels:
    - `Too expensive`
    - `Wrong location`
    - `Not my style`
    - `Too few good options`
    - `Other`
  - stored enum values:
    - `too_expensive`
    - `wrong_location`
    - `not_my_style`
    - `too_few_good_options`
    - `other`
- text input:
  - do not include required text input
  - do not include optional free text in v1
- eligibility rules:
  - prompt only after meaningful exposure
  - initial `Matches` rule: user has viewed the ranked list for at least `10` seconds
  - allow prompt if the user opened at least `3` listing details from the ranked results
- frequency rules:
  - at most once per recommendation session
  - at most once every `7` days per user
  - never show again after feedback has already been submitted for the same session
- dismissal rules:
  - if dismissed, mark the prompt as dismissed
  - do not re-show in the same session
  - allow re-eligibility in a future session after the cooldown window
- recommendation session definition for v1:
  - one `Matches` page visit counts as one recommendation session
  - session begins when the user lands on `Matches`
  - session ends when the user leaves the page or becomes inactive long enough for timeout handling
- required session metadata:
  - `session_id`
  - `user_id`
  - `surface`
  - `started_at`
  - `ended_at`
  - `recommendation_count_shown`
  - `top_listing_ids_shown`
  - `algorithm_version`
  - `model_version`
  - `experiment_name`
  - `experiment_variant`
- required feedback metadata:
  - `feedback_label`
  - `reason_label`
  - `submitted_at`
  - `prompt_presented_at`
  - `prompt_dismissed_at`
- experiment contract for v1:
  - every recommendation session must carry a ranker identity
  - initial supported variants:
    - `two_tower`
    - `baseline`
  - if no experiment is active, still store the effective ranker in metadata

Out of scope for Phase 1:

- `Discover` prompt
- per-listing explicit ratings
- free-text comments
- admin dashboard implementation
- aggregation jobs
- experiment analysis

Phase 1 exit criteria:

- product copy is final
- stored enum values are final
- prompt timing rules are final
- session boundaries are final
- required metadata fields are final
- downstream implementation can begin without re-deciding UX or schema basics

## Phase 2: Data Capture

- add session-level feedback prompt on `Matches`
- store explicit usefulness feedback
- store optional negative reason tag
- store session metadata and ranking metadata
- connect feedback rows to the current user and recommendation session

## Phase 3: Passive Metrics

- add session-level passive engagement tracking
- log detail opens from recommendation surfaces
- log saves in a way that can be tied back to recommendation sessions
- add dwell-time instrumentation where feasible
- compute derived session metrics such as likes, saves, and detail opens

## Phase 4: Admin Evaluation Page

- build an admin-only evaluation page
- add top KPI cards
- add usefulness distribution and variant comparison
- add negative reason breakdown
- add initial filtering by date range, variant, and market

## Phase 5: Discover Expansion

- add the feedback prompt to `Discover`
- add prompt suppression and cooldown tuning
- improve session modeling across surfaces
- add dashboard filters and exports
- validate that prompt timing does not hurt user experience

## Phase 6: Research Validation

- run explicit A/B test between `two_tower` and `baseline`
- analyze results by user history bucket
- add trend analysis and model-version comparisons
- export aggregated results for course presentation / paper write-up
- document limitations, sample size, and exposure-bias caveats

---

## 15. UX Recommendations

The prompt should feel lightweight and native.

Recommended format:

- small bottom sheet or card
- clear title
- one-line explanation
- 3 large tap targets

Recommended copy:

**Title:** `How useful were these recommendations?`  
**Subtitle:** `Your feedback helps us improve how listings are ranked.`

Negative follow-up copy:

**Title:** `What felt off?`  
**Subtitle:** `Optional`

Avoid:

- large modal walls of text
- required text boxes
- 1-10 numeric sliders
- prompts shown before enough recommendation exposure

For the admin page, optimize for:

- quick scanability
- simple KPI summaries
- direct variant comparisons
- minimal clutter

---

## 16. Privacy and Ethics Notes

Because this is a research-oriented feature, the team should be explicit internally about what is being measured.

Important points:

- users should not be misled about why feedback is being collected
- feedback should be tied to recommendation quality, not private identity traits
- raw event logs should be stored securely
- reporting should primarily use aggregated data
- admin dashboards should only expose what the team needs for evaluation

If this project is presented academically, document:

- what data was collected
- what feedback was explicit vs inferred
- what ranking variants were compared
- what limitations exist due to exposure bias and sample size

---

## 17. Open Questions

These should be finalized before implementation:

1. Should the first release collect feedback only on `Matches`, or on both `Matches` and `Discover`?
2. What exact baseline variant will be used against the two-tower model?
3. How long should the prompt cooldown be: `7` days, `14` days, or session-based only?
4. Should the admin page read directly from aggregation endpoints or from precomputed reporting tables / views?
5. Should the first version include optional free text for `Other`, or leave that out entirely?

---

## 18. Final Recommendation

Build the first version around this exact loop:

1. User interacts normally with recommendations.
2. After meaningful exposure, show one question:
   - `How useful were these recommendations?`
3. User answers with one tap:
   - `Not useful`
   - `Somewhat useful`
   - `Very useful`
4. If `Not useful`, optionally ask:
   - `What felt off?`
5. Store the response with full session and ranking metadata.
6. Aggregate the results into interpretable metrics.
7. Show those metrics in an admin-only evaluation page.
8. Compare results between `two_tower` and `baseline`.

This gives Padly a feedback feature that is:

- easy for users
- strong enough for research evaluation
- directly tied to recommendation quality
- visible to the team through a proper reporting surface
- simple enough to ship quickly
