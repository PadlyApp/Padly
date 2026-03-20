# Padly (full-stack)

Padly is a housing and roommate matching platform for students, interns, and early-career professionals.  
This branch contains an actively developed full-stack app:

- Frontend: Next.js + Mantine (`frontend/`)
- Backend: FastAPI + Supabase (`backend/`)
- Matching stack: user-to-group compatibility + stable group-to-listing matching

## What Is Implemented Now

### Frontend Product Flows

- Auth and session management (signup, signin, signout, token refresh, protected routes)
- Onboarding flow and profile completion
- Group discovery, creation, editing, and detail management
- Group invitations and join-request review/approval flows
- Preferences form (housing constraints + soft preferences)
- Discover swipe experience for listing recommendations
- Matches page (liked listings from Discover)
- Listing detail page and account/profile editing

Main route files are under `frontend/src/app/`, including:

- `page.jsx` (home)
- `login/page.jsx`, `signup/page.jsx`
- `onboarding/page.jsx`
- `groups/page.jsx`, `groups/create/page.jsx`, `groups/[id]/page.jsx`, `groups/[id]/edit/page.jsx`
- `invitations/page.jsx`
- `preferences/page.jsx`
- `discover/page.jsx`
- `matches/page.jsx`
- `listings/[id]/page.jsx`
- `account/page.jsx`

### Backend API Domains

The FastAPI app mounts routers in `backend/app/main.py`:

- `auth` (`/api/auth/*`)
- `users` (`/api/users*`)
- `listings` (`/api/listings*`)
- `roommates` (`/api/roommate-posts*`)
- `roommate-groups` (`/api/roommate-groups*`)
- `preferences` (`/api/preferences*`)
- `matches` (`/api/matches*`)
- `stable-matches` (`/api/stable-matches*`)
- `recommendations` (`/api/recommendations`)
- `admin` (`/api/admin/*`)

## Matching and Recommendation System

### 1) User -> Group Compatibility

`backend/app/services/user_group_matching.py` ranks groups for a user using:

- Hard filters: city, budget overlap, move-in date window, open group slots
- Soft scoring (0-100): budget fit, date fit, lease prefs, amenities, affiliation, verification, lifestyle

Used by:

- `GET /api/matches/groups`
- `GET /api/roommate-groups/discover`

### 2) Group -> Listing Stable Matching

`POST /api/stable-matches/run` executes a multi-phase pipeline:

1. Filter eligible groups/listings (`services/stable_matching/filters.py`)
2. Build feasible pairs (`services/stable_matching/feasible_pairs.py`)
3. Score and build preference lists (`services/stable_matching/scoring.py`)
4. Run Gale-Shapley deferred acceptance (`services/stable_matching/deferred_acceptance.py`)
5. Run LNS optimization (`services/lns_optimizer.py`)
6. Persist matches/diagnostics (`services/stable_matching/persistence.py`)

The run preserves already confirmed matches and re-matches only unconfirmed candidates.

### 3) Listing Recommendations Endpoint

`POST /api/recommendations` (in `backend/app/routes/recommendations.py`) scores active listings and returns ranked recommendations for the Discover UI.

## Tech Stack (Current)

### Frontend (`frontend/package.json`)

- Next.js `15.5.4`
- React `19.1.0`
- Mantine `7.17.8`
- TanStack Query `5.90.x`
- Supabase JS `2.58.0`
- TypeScript + ESLint

### Backend (`backend/requirements.txt`)

- FastAPI `0.118.0`
- Uvicorn `0.37.0`
- Supabase Python client `2.21.1`
- Pydantic `2.12.3`
- python-dotenv `1.0.0`
- TensorFlow `2.20.0` (for AI/recommender experiments under `backend/app/ai/`)

## Project Structure

```text
Padly/
├── frontend/
│   ├── src/app/                 # Next.js App Router pages/components/providers
│   ├── lib/                     # API + auth clients
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── routes/              # API route modules
│   │   ├── services/            # Matching/business services
│   │   ├── ai/                  # Recommender + model artifacts/docs
│   │   ├── schemas/             # SQL schema + ERD
│   │   └── db.py                # Supabase env + clients
│   ├── migrations/              # SQL migrations
│   └── requirements.txt
└── run-dev.sh                   # Starts backend + frontend
```

## Local Setup

### Prerequisites

- Node.js 18+
- npm
- Python 3.10+
- Supabase project (URL + keys)

### 1) Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp app/.env.example app/.env
```

Update `backend/app/.env` with:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- Optional: `VERIFY_JWT` (`true`/`false`)
- Optional: `SUPABASE_JWT_SECRET`

Then run:

```bash
uvicorn app.main:app --reload
```

Backend URLs:

- API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 2) Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- App: `http://localhost:3000`

### 3) Start Both Services (Recommended)

From repo root:

```bash
chmod +x run-dev.sh
./run-dev.sh
```

## Database and Schema Artifacts

- Main schema SQL: `backend/app/schemas/padly_schema.sql`
- ERD: `backend/app/schemas/padly_erd.pdf` and `.drawio`
- Migrations:
  - `backend/migrations/001_dynamic_group_sizing.sql`
  - `backend/migrations/002_solo_user_groups.sql`
  - `backend/migrations/003_expand_personal_preferences.sql`
  - `backend/migrations/003_match_confirmation.sql`
  - `backend/migrations/add_group_members_status.sql`

## Useful API Surface (Quick Reference)

### Auth

- `POST /api/auth/signup`
- `POST /api/auth/signin`
- `POST /api/auth/refresh`
- `POST /api/auth/signout`
- `GET /api/auth/me`

### Preferences / Matching

- `GET /api/preferences/{user_id}`
- `PUT /api/preferences/{user_id}` (also triggers stable matching for target city)
- `GET /api/matches/groups`
- `POST /api/stable-matches/run`
- `GET /api/stable-matches/active`
- `GET /api/stable-matches/stats`

### Groups

- `GET /api/roommate-groups`
- `POST /api/roommate-groups`
- `GET /api/roommate-groups/{group_id}`
- `PUT /api/roommate-groups/{group_id}`
- `DELETE /api/roommate-groups/{group_id}`
- `POST /api/roommate-groups/{group_id}/request-join`
- `POST /api/roommate-groups/{group_id}/join`
- `POST /api/roommate-groups/{group_id}/reject`
- `POST /api/roommate-groups/{group_id}/accept-request/{user_id}`
- `POST /api/roommate-groups/{group_id}/reject-request/{user_id}`

### Listings / Recommendations

- `GET /api/listings`
- `GET /api/listings/{listing_id}`
- `POST /api/listings`
- `PUT /api/listings/{listing_id}`
- `DELETE /api/listings/{listing_id}`
- `POST /api/recommendations`

## Notes for Contributors

- Frontend currently uses `http://localhost:8000` directly in many pages; `NEXT_PUBLIC_API_URL` is only used in `frontend/lib/api.js`.
- `backend/app/.env.example` currently includes `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`; add `SUPABASE_ANON_KEY` manually because backend startup requires it (`backend/app/db.py`).
- Legacy mock auth pages/routes still exist under `frontend/src/app/auth/*` and `frontend/src/app/api/auth/*`; primary app auth flow uses `frontend/src/app/login/page.jsx` and `frontend/src/app/signup/page.jsx` with backend `/api/auth/*`.
- `GET /api/preferences/me` is currently a placeholder returning `501` by design.

## Additional Docs In Repo

- `backend/MATCHING_ALGORITHM.md`
- `TWO_TOWER_EXPLAINER.md`
- `DATASET_REQUIREMENTS.md`
- `SOURCE_OF_TRUTH.md`
- `COMPLETION_SUMMARY.md`

