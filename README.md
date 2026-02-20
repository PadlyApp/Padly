# Padly

A trusted platform for students, interns, and early-career professionals to find housing and compatible roommates.

---

## Project Vision

The mission of Padly is to eliminate the stress and fragmentation of finding housing during pivotal career and life transitions. We are building a centralized, secure, and user-centric platform that connects a community of peers, landlords, and subletters, enabling them to transact with confidence and ease.

---

## Key Features

### Authentication & Profiles
- Secure sign-up and login with Supabase Auth (JWT-based)
- User profiles with professional context (company, school, role)
- Email verification system for trust building
- Account management with editable profile information

### Roommate Groups
- Create and manage roommate groups
- Request to join existing groups
- Group owner approval system for join requests
- Dynamic group sizing (1-N members)
- Solo groups for individual users
- Group recommendations based on compatibility scoring
- Automatic ownership transfer when creators leave

### Housing Listings & Matching
- Browse and search housing listings
- Intelligent matching using Gale-Shapley Stable Matching algorithm
- Large Neighborhood Search (LNS) optimization for improved match quality
- Hard constraints filtering (city, budget, date, bedrooms)
- Soft preferences scoring (bathrooms, furnished, utilities, deposit, house rules)
- Real-time match updates when preferences change

### Preferences System
- Hard constraints (non-negotiable requirements)
- Soft preferences (nice-to-haves with scoring)
- Lifestyle compatibility matching
- Automatic stable matching trigger on preference updates

### Matching Algorithms
- **Gale-Shapley Deferred Acceptance**: Guarantees stable matches with no blocking pairs
- **Large Neighborhood Search (LNS)**: Optimizes match quality through iterative destroy-repair cycles
- **Greedy Heuristics**: Regret-greedy and randomized greedy for repair operations
- Compatibility scoring (0-100 points) based on budget, date, company/school, verification, and lifestyle

---

## Tech Stack

### Frontend
- **Next.js 15** - React framework with server-side rendering
- **React 19** - UI library
- **Mantine** - Component library and UI framework
- **TanStack React Query** - Data fetching and caching
- **TypeScript** - Type safety

### Backend
- **FastAPI** - High-performance Python web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation using Python type hints
- **Supabase** - Backend-as-a-Service (Auth, Database, Storage)

### Database
- **PostgreSQL** - Relational database (via Supabase)
- **PostgREST** - Auto-generated REST API from database schema

### Authentication
- **Supabase Auth** - JWT-based authentication with refresh tokens

### API Documentation
- **OpenAPI/Swagger** - Auto-generated interactive API docs at `/docs`

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** (v18 or higher) and **npm**
- **Python** (v3.9 or higher)
- **Supabase Account** - [Create one here](https://supabase.com)
- **Git**

---

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Padly
```

### 2. Set Up Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to Project Settings → API
3. Copy your `SUPABASE_URL` and `SUPABASE_ANON_KEY`
4. Copy your `SUPABASE_SERVICE_ROLE_KEY` (keep this secret!)

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file in backend/app/ directory
# Add the following variables:
# SUPABASE_URL=your_supabase_url
# SUPABASE_ANON_KEY=your_anon_key
# SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local file (optional, if using Supabase client directly)
# NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
# NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

---

## Running the Application

### Option 1: Run Both Services Together (Recommended)

```bash
# From project root
chmod +x run-dev.sh  # On Mac/Linux
./run-dev.sh

# On Windows, use Git Bash or WSL
```

This script will:
- Start the FastAPI backend on `http://localhost:8000`
- Start the Next.js frontend on `http://localhost:3000`
- Auto-install dependencies if needed

### Option 2: Run Services Separately

**Backend:**
```bash
cd backend
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm run dev
```

### Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Neural Net Branch: Two-Tower Baseline

This branch includes a TensorFlow baseline you can use to choose loss functions and define model inputs.

### Baseline Location

- **Model script**: `backend/app/ai/two_tower_baseline.py`
- **Architecture explanation**: `TWO_TOWER_EXPLAINER.md`
- **Integration roadmap**: `ML_ROADMAP.md`

### Run the Baseline

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
python -m app.ai.two_tower_baseline --epochs 5 --loss binary_crossentropy
```

### Change Loss Function

```bash
python -m app.ai.two_tower_baseline --loss softmax
```

Supported loss values:
- `binary_crossentropy`
- `softmax`

### Use Your Own Input Data

Provide an `.npz` file with:
- `user_features`: shape `(N, user_dim)`
- `item_features`: shape `(N, item_dim)`
- `labels`: shape `(N,)` with 0/1 labels

Run:

```bash
python -m app.ai.two_tower_baseline --npz-path path/to/train_data.npz --loss binary_crossentropy
```

### Output

By default, the trained model is saved to:

- `backend/app/ai/artifacts/two_tower_baseline.keras`

---

## Project Structure

```
Padly/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI application entry point
│   │   ├── routes/         # API route handlers
│   │   │   ├── auth.py    # Authentication endpoints
│   │   │   ├── users.py   # User management
│   │   │   ├── groups.py   # Roommate groups
│   │   │   ├── listings.py # Housing listings
│   │   │   ├── preferences.py # User preferences
│   │   │   └── stable_matching.py # Matching algorithm
│   │   ├── services/       # Business logic
│   │   │   ├── stable_matching/ # Matching algorithm modules
│   │   │   ├── lns_optimizer.py # LNS optimization
│   │   │   └── user_group_matching.py # User-group compatibility
│   │   ├── models.py       # Pydantic models
│   │   ├── db.py          # Database configuration
│   │   └── schemas/        # Database schema SQL files
│   ├── requirements.txt    # Python dependencies
│   └── migrations/         # Database migrations
│
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── app/           # Next.js app directory
│   │   │   ├── account/   # Account management page
│   │   │   ├── groups/    # Groups pages
│   │   │   ├── listings/ # Listings pages
│   │   │   ├── matches/   # Matches page
│   │   │   ├── preferences/ # Preferences page
│   │   │   └── components/ # React components
│   │   ├── contexts/      # React contexts (Auth)
│   │   └── lib/           # Utility functions
│   └── package.json       # Node dependencies
│
└── run-dev.sh             # Development server launcher
```

---

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register new user
- `POST /api/auth/signin` - Login user
- `GET /api/auth/me` - Get current user
- `POST /api/auth/signout` - Sign out

### Users
- `GET /api/users` - List users
- `GET /api/users/{user_id}` - Get user profile
- `PUT /api/users/{user_id}` - Update user profile

### Groups
- `GET /api/roommate-groups` - List groups (with filters)
- `GET /api/roommate-groups/{group_id}` - Get group details
- `POST /api/roommate-groups` - Create group
- `PUT /api/roommate-groups/{group_id}` - Update group
- `POST /api/roommate-groups/{group_id}/request-join` - Request to join
- `POST /api/roommate-groups/{group_id}/accept-request/{user_id}` - Accept join request
- `DELETE /api/roommate-groups/{group_id}/leave` - Leave group

### Matching
- `GET /api/matches/groups` - Get compatible groups for user
- `POST /api/stable-matches/run` - Run stable matching algorithm
- `GET /api/stable-matches/active` - Get active matches

### Preferences
- `GET /api/preferences/{user_id}` - Get user preferences
- `PUT /api/preferences/{user_id}` - Update preferences

## Links

- [Supabase Documentation](https://supabase.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Next.js Documentation](https://nextjs.org/docs)
- [Mantine Documentation](https://mantine.dev)

---

## Troubleshooting

### Backend won't start
- Ensure virtual environment is activated
- Check that `.env` file exists with correct Supabase credentials
- Verify Python version (3.9+)

### Frontend won't start
- Ensure Node.js version is 18+
- Delete `node_modules` and run `npm install` again
- Check for port conflicts (3000, 8000)

### Database connection errors
- Verify Supabase credentials in `.env`
- Check Supabase project is active
- Ensure database schema is applied
