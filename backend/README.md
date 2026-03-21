# Padly Backend

> A roommate and housing matching platform using Gale-Shapley stable matching with LNS optimization.

## Quick Start

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Mac/Linux:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp app/.env.example app/.env
# Edit app/.env with your Supabase credentials

# Run the server
uvicorn app.main:app --reload
```

Server runs at: http://localhost:8000  
API docs at: http://localhost:8000/docs

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── routes/                    # API endpoints
│   │   ├── groups.py              # Group management
│   │   ├── matches.py             # Matching endpoints
│   │   ├── listings.py            # Listing management
│   │   └── stable_matching.py     # Gale-Shapley + LNS
│   └── services/                  # Business logic
│       ├── user_group_matching.py # User→Group scoring
│       ├── lns_optimizer.py       # LNS optimization
│       └── stable_matching/       # Stable matching algorithms
├── migrations/                    # Database migrations
└── MATCHING_ALGORITHM.md          # Full algorithm documentation
```

---

## Documentation

📖 **[MATCHING_ALGORITHM.md](MATCHING_ALGORITHM.md)** - Complete documentation of:
- User-to-Group matching (compatibility scoring)
- Gale-Shapley stable matching algorithm
- LNS optimization (+13.8% quality improvement)
- API reference
- Code file reference

---

## Key Features

| Feature | Description |
|---------|-------------|
| **User→Group Matching** | Solo users find compatible groups (0-100 score) |
| **Gale-Shapley** | Stable matching guaranteeing no blocking pairs |
| **LNS Optimization** | Improves match quality by 13.8% |
| **Auto Re-matching** | Triggers on group changes, rejections |

---

## API Endpoints

### Matching
- `GET /api/matches/groups` - Discover compatible groups
- `POST /api/stable-matches/run` - Run matching algorithm
- `GET /api/stable-matches/active` - Get active matches

### Groups
- `POST /api/roommate-groups` - Create group
- `POST /api/roommate-groups/{id}/join` - Request to join
- `POST /api/roommate-groups/{id}/confirm-match` - Confirm match

### Listings
- `GET /api/listings` - List all listings
- `POST /api/listings/{id}/confirm-match` - Confirm match

### Interactions (Phase 2A)
- `POST /api/interactions/swipes` - Persist Discover swipe events
- `GET /api/interactions/swipes/me` - Inspect current user swipe history
- `GET /api/interactions/behavior/me` - Build authenticated user behavior vector
- `GET /api/interactions/behavior/groups/{group_id}` - Build group behavior vector (member-only access)
- `GET /api/interactions/behavior/health` - Swipe event quality/freshness summary

Full API documentation available at `/docs` when server is running.

---

## Test Results (Oakland)

| Metric | Result |
|--------|--------|
| Groups Matched | 96% |
| LNS Improvement | +13.8% |
| Execution Time | 1.37s |
| Stable | ✅ Yes |

---

## Technologies

- **Python 3.10** + FastAPI
- **PostgreSQL** (Supabase)
- **Gale-Shapley Algorithm** (stable matching)
- **LNS** (Large Neighborhood Search optimization)
