# Data Parser Architecture

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        SUPABASE DATABASE                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ listings │  │  groups  │  │  users   │  │  prefs   │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              SUPABASE HTTP CLIENT (httpx)                       │
│                   app/services/supabase_client.py               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PARSER SERVICE                          │
│                 app/services/data_parser.py                     │
│                                                                 │
│  • fetch_and_parse_listings()                                  │
│  • fetch_and_parse_groups()                                    │
│  • fetch_parsed_data_for_algorithms()                          │
│  • serialize_value() - Decimal → float, datetime → ISO string  │
│  • parse_listing() - Clean & format listing data               │
│  • parse_group() - Clean & format group data                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                                           ↓
┌──────────────────┐                    ┌──────────────────────┐
│  JSON OBJECTS    │                    │  MATCHING ALGORITHM  │
│                  │                    │    app/services/     │
│  • listings[]    │                    │  matching_algorithm  │
│  • groups[]      │                    │       .py            │
└──────────────────┘                    └──────────────────────┘
        ↓                                           ↓
        ├──────────────┬────────────────────────────┤
        ↓              ↓                            ↓
┌──────────┐  ┌──────────────┐         ┌────────────────────┐
│   API    │  │  TEST SCRIPT │         │   ALGORITHM CODE   │
│ ENDPOINTS│  │              │         │                    │
│          │  │ test_data_   │         │ Your matching      │
│ /api/    │  │ parser.py    │         │ logic using the    │
│ matches  │  │              │         │ parsed JSON data   │
└──────────┘  └──────────────┘         └────────────────────┘
```

## Component Breakdown

### 1. Supabase Database
- **Tables**: listings, roommate_groups, group_members, users, personal_preferences
- **Mock Data**: Loaded from `mock_data.sql`
- **Access**: Via PostgREST API

### 2. Supabase HTTP Client
- **File**: `app/services/supabase_client.py`
- **Purpose**: Direct HTTP calls to Supabase PostgREST API
- **Features**: 
  - Admin access (service role key)
  - User access (JWT tokens)
  - SELECT, INSERT, UPDATE, DELETE operations

### 3. Data Parser Service
- **File**: `app/services/data_parser.py`
- **Purpose**: Fetch and parse data into JSON-ready objects
- **Key Functions**:
  ```python
  # Fetch all data
  data = await fetch_parsed_data_for_algorithms()
  
  # Access parsed objects
  listings = data['listings']  # List[Dict]
  groups = data['groups']      # List[Dict]
  ```

### 4. Matching Algorithm
- **File**: `app/services/matching_algorithm.py`
- **Purpose**: Match users with listings and groups
- **Integration**:
  ```python
  # Automatically fetches and parses data
  matches = await get_matches_for_user(user_id, limit=20)
  ```

### 5. API Layer
- **File**: `app/routes/matches.py`
- **Endpoints**:
  - `GET /api/matches/data/listings` → All parsed listings
  - `GET /api/matches/data/groups` → All parsed groups
  - `GET /api/matches/data/all` → Both listings & groups
  - `GET /api/matches/{user_id}/v2` → User matches
  - `GET /api/matches/{user_id}/groups` → Group matches

### 6. Test & Examples
- **Test Script**: `app/scripts/test_data_parser.py`
  - Fetches data
  - Saves JSON files
  - Displays summary
- **Examples**: `app/scripts/example_usage.py`
  - 8 usage examples
  - Filtering patterns
  - Scoring examples

## Data Transformation Flow

```
Raw Supabase Data (PostgreSQL types)
         ↓
┌────────────────────────────┐
│   Decimal("2200.00")      │
│   datetime(2025, 11, 10)  │
│   {"wifi": true}          │
└────────────────────────────┘
         ↓
    serialize_value()
         ↓
┌────────────────────────────┐
│   2200.0 (float)          │
│   "2025-11-10T12:00:00"   │
│   {"wifi": true}          │
└────────────────────────────┘
         ↓
   parse_listing() or
   parse_group()
         ↓
┌────────────────────────────┐
│  Clean JSON Object        │
│  - All fields mapped      │
│  - Proper types           │
│  - Nested structures OK   │
└────────────────────────────┘
         ↓
   Algorithm Ready! ✅
```

## Usage Patterns

### Pattern 1: Direct Function Call
```python
from app.services.data_parser import fetch_and_parse_listings

listings = await fetch_and_parse_listings()
for listing in listings:
    print(listing['title'], listing['price_per_month'])
```

### Pattern 2: Via Matching Algorithm
```python
from app.services.matching_algorithm import get_matches_for_user

matches = await get_matches_for_user(user_id="...", limit=20)
```

### Pattern 3: Via API
```bash
curl http://localhost:8000/api/matches/data/all
```

### Pattern 4: Test Script
```bash
python -m app.scripts.test_data_parser
# Creates: parsed_listings.json, parsed_groups.json
```

## Key Benefits

### ✅ Type Safety
- No `Decimal` objects (converted to `float`)
- No `datetime` objects (converted to ISO strings)
- All values are JSON-serializable

### ✅ Clean Structure
- Consistent field names
- Proper nesting
- Missing fields handled gracefully

### ✅ Easy to Use
- Simple async functions
- Multiple access methods
- Well documented

### ✅ Algorithm Ready
- Designed specifically for matching algorithms
- Includes all necessary fields
- Optimized structure

## File Locations

```
backend/
├── app/
│   ├── services/
│   │   ├── data_parser.py              ← Main parser service
│   │   ├── matching_algorithm.py        ← Uses parser
│   │   ├── supabase_client.py          ← HTTP client
│   │   └── DATA_PARSER_README.md       ← Detailed docs
│   ├── routes/
│   │   └── matches.py                  ← API endpoints
│   └── scripts/
│       ├── test_data_parser.py         ← Test script
│       └── example_usage.py            ← Examples
├── QUICK_REFERENCE.md                  ← Quick start
├── IMPLEMENTATION_SUMMARY.md           ← Overview
├── CHECKLIST.md                        ← Verification
└── ARCHITECTURE.md                     ← This file
```

## Next Steps

1. **Test**: Run `python -m app.scripts.test_data_parser`
2. **Inspect**: Check generated JSON files
3. **Use**: Import functions in your code
4. **Develop**: Build matching algorithms with clean data

See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for more details!
