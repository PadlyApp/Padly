# Padly

Padly is a roommate-first housing platform for students, interns, and early-career professionals.

Most rental apps start with listings. Padly starts with people.

## What The App Does

Padly helps users:

- define what they need in a home and roommate setup
- find compatible roommates and groups
- discover listings that fit the group, not just one person
- get recommendations that improve with usage

## Why Padly Is Different

Traditional marketplaces focus on individual renter -> listing matching.

Padly is built around:

- compatibility between people
- shared constraints across a household
- group-aware housing recommendations

This household-first approach reduces the common failure case where a listing looks good on paper but the roommate setup does not work in real life.

## Core Features

### 1) Personal Onboarding and Preferences

Users create a profile and set:

- hard requirements (must-have constraints)
- soft preferences (ranking signals and lifestyle preferences)

### 2) Roommate and Group Discovery

Padly helps users discover compatible groups and candidates using:

- hard compatibility gates
- lifestyle alignment
- trust and fit signals

### 3) Group Formation and Management

Groups can:

- accept members
- maintain shared preferences
- evolve as members join or leave

Padly continuously keeps the group profile aligned with member preferences.

### 4) Group-to-Listing Recommendations

Listings are shown only after feasibility checks, then ranked by blended intelligence:

- preference fit
- behavior patterns
- neural affinity

Users get an explainable ranking, not a black box.

### 5) Discover Feedback Loop

As users interact with recommendations, Padly learns from behavior and improves future ranking quality over time.

## End-to-End Product Flow

Padly follows a clear journey:

1. User onboarding and preference setup.
2. User discovers compatible roommates/groups.
3. User joins or forms a group.
4. Group preferences become the source of truth.
5. Group receives ranked listing recommendations.
6. Ongoing interactions improve recommendation quality.

## Matching Intelligence (In Plain Language)

Padly combines three layers:

- Rules: clear preference and constraint alignment.
- Behavior: learning from what users engage with.
- Neural modeling: deeper similarity and affinity scoring.

The same intelligence that improves listing recommendations is also used to strengthen roommate suggestions.

## Two-Tower Architecture (Technical Overview)

Padly’s neural layer uses a two-tower model:

- Preference tower: encodes a user (or group preference profile) into an embedding.
- Listing tower: encodes each listing into an embedding in the same vector space.

Recommendations are produced by comparing these embeddings:

- closer vectors = higher predicted affinity
- farther vectors = lower predicted affinity

Padly blends this neural affinity with rules and behavior signals, so ranking stays robust in both cold-start and mature-data scenarios.

For roommate suggestions, Padly reuses listing-taste embeddings from interaction history to estimate similarity between people with similar housing tastes.

## Who Padly Is For

- students moving for school terms
- interns relocating temporarily
- new grads and early-career professionals moving to new cities
- anyone who needs both a home and compatible roommates

## Product Direction

Padly is focused on making shared-living decisions faster, safer, and more compatible by solving both sides of the problem together:

- **Who should I live with?**
- **Where should we live?**
