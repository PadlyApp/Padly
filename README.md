# Padly

Padly is a roommate-first housing platform for students, interns, and early-career professionals.

Most rental apps start with listings. Padly starts with people.

## The Problem

Finding housing with roommates is a two-sided problem: you need the right people *and* the right place. Traditional platforms only solve one side, leaving users to figure out the other on their own.

## How Padly Works

### 1. Set Your Preferences

New users go through onboarding to define their hard requirements (budget, location, move-in date) and soft preferences (lifestyle, cleanliness, schedule). These drive every recommendation that follows.

### 2. Find Compatible Roommates

Padly suggests roommates based on preference compatibility, lifestyle alignment, and behavioral signals. Users can express interest in each other through an intro system with mutual opt-in.

### 3. Form a Group

Compatible users form groups. Each group has shared preferences automatically aggregated from its members. As members join or leave, the group profile updates.

### 4. Discover Listings

The Discover page presents listings ranked for the group using a blend of:

- **Rule-based filtering** — hard constraints like budget, location, and bedroom count
- **Behavioral signals** — learned from swipe interactions (likes, passes, saves)
- **Neural ranking** — a two-tower model that embeds user preferences and listing features into the same vector space to score affinity

Users swipe through listings and can save favorites to their group.

### 5. Get Matched

Padly runs a stable matching algorithm that pairs groups with listings, producing ranked matches where both sides are considered. Groups see their matches with explainable scores.

### 6. Keep Improving

Every interaction feeds back into the system. Swipe behavior refines recommendations over time, so the more a group uses Padly, the better the suggestions get.

## Key Features

- **Guided onboarding** with a walkthrough tour for new users
- **Roommate suggestions** with compatibility scoring and intro requests
- **Group management** with invitations, join requests, and shared preferences
- **Swipe-based discover** for browsing recommended listings
- **Group saves** to bookmark listings for the whole group
- **Stable matching** between groups and listings
- **Metro-aware location matching** across cities and regions
- **Row-level security** on all database tables

## Tech Stack

- **Frontend:** Next.js 15, React 19, Mantine UI, TanStack Query
- **Backend:** FastAPI, Supabase (Postgres + Auth), Pydantic
- **AI/ML:** TensorFlow two-tower model, behavioral fingerprinting, embedding-based similarity
- **Infrastructure:** Supabase migrations, Git LFS for model artifacts

## Who It's For

- Students moving for school terms
- Interns relocating temporarily
- New grads and early-career professionals moving to new cities
- Anyone who needs both a home and compatible roommates
