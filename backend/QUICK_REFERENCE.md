# Quick Reference: Data Parser & Algorithm Integration

## 🚀 Quick Start

### 1. Fetch All Data
```python
from app.services.data_parser import fetch_parsed_data_for_algorithms

data = await fetch_parsed_data_for_algorithms()
listings = data['listings']  # List of listing dicts
groups = data['groups']      # List of group dicts
```

### 2. Use in API Endpoint
```python
from app.services.matching_algorithm import get_matches_for_user

matches = await get_matches_for_user(user_id="...", limit=20)
```

### 3. Test from Command Line
```bash
cd backend
python -m app.scripts.test_data_parser
```

### 4. Access via HTTP
```bash
# Get all listings (parsed)
curl http://localhost:8000/api/matches/data/listings

# Get all groups (parsed)
curl http://localhost:8000/api/matches/data/groups

# Get both
curl http://localhost:8000/api/matches/data/all

# Get user matches
curl http://localhost:8000/api/matches/{user_id}/v2?limit=20

# Get group matches
curl http://localhost:8000/api/matches/{user_id}/groups?limit=20
```

## 📦 Available Functions

### Data Parser (`app.services.data_parser`)

| Function | Description | Returns |
|----------|-------------|---------|
| `fetch_and_parse_listings()` | Get all active listings | `List[Dict]` |
| `fetch_and_parse_groups()` | Get all active groups | `List[Dict]` |
| `fetch_parsed_data_for_algorithms()` | Get both listings & groups | `Dict{'listings': [], 'groups': []}` |
| `fetch_user_preferences(user_id)` | Get user's preferences | `Dict` or `None` |
| `fetch_roommate_post(user_id)` | Get user's roommate post | `Dict` or `None` |

### Matching Algorithm (`app.services.matching_algorithm`)

| Function | Description | Returns |
|----------|-------------|---------|
| `get_matches_for_user(user_id, limit)` | Fetch data & match listings | `Dict` with matches |
| `get_group_matches_for_user(user_id, limit)` | Fetch data & match groups | `Dict` with matches |
| `get_all_algorithm_data()` | Fetch all parsed data | `Dict{'listings': [], 'groups': []}` |

## 🔑 Key Data Fields

### Listing Object
```python
{
    'id': str,                      # UUID
    'title': str,                   # "Cozy Studio in Downtown SF"
    'city': str,                    # "San Francisco"
    'price_per_month': float,       # 2200.0
    'property_type': str,           # "entire_place" | "private_room" | "shared_room"
    'number_of_bedrooms': int,      # 1
    'number_of_bathrooms': float,   # 1.0
    'furnished': bool,              # true
    'amenities': dict,              # {"wifi": true, "laundry": true, ...}
    'available_from': str,          # "2025-05-01" (ISO date)
    'available_to': str | None,     # "2025-08-31" or null
    'status': str,                  # "active"
    # ... many more fields
}
```

### Group Object
```python
{
    'id': str,                         # UUID
    'group_name': str,                 # "Tech Professionals Group"
    'target_city': str,                # "San Francisco"
    'budget_per_person_min': float,    # 1200.0
    'budget_per_person_max': float,    # 2000.0
    'target_group_size': int,          # 3
    'current_size': int,               # 2 (when include_members=True)
    'members': list,                   # [{user_id, is_creator, joined_at}]
    'status': str,                     # "active"
    # ... more fields
}
```

## 💡 Common Patterns

### Filter by Price
```python
listings = await fetch_and_parse_listings()
affordable = [l for l in listings if l['price_per_month'] <= 2500]
```

### Filter by City
```python
listings = await fetch_and_parse_listings()
sf_listings = [l for l in listings if l['city'] == 'San Francisco']
```

### Check Amenities
```python
listing = listings[0]
has_wifi = listing['amenities'].get('wifi', False)
has_parking = listing['amenities'].get('parking', False)
```

### Score Listings
```python
def calculate_score(listing, user_prefs):
    score = 0
    if listing['city'] == user_prefs['city']:
        score += 30
    if listing['price_per_month'] <= user_prefs['budget_max']:
        score += 25
    # Add more criteria...
    return score

scores = [(l, calculate_score(l, prefs)) for l in listings]
scores.sort(key=lambda x: x[1], reverse=True)
```

### Get Available Groups
```python
groups = await fetch_and_parse_groups(include_members=True)
available = [
    g for g in groups 
    if g.get('current_size', 0) < g['target_group_size']
]
```

## 🎯 API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/matches/data/listings` | GET | All parsed listings |
| `/api/matches/data/groups` | GET | All parsed groups |
| `/api/matches/data/all` | GET | Both listings & groups |
| `/api/matches/{user_id}/v2` | GET | User matches (uses parser) |
| `/api/matches/{user_id}/groups` | GET | Group matches for user |

## 📝 Example Workflow

### For Algorithm Development
```python
# 1. Fetch data
data = await fetch_parsed_data_for_algorithms()
listings = data['listings']

# 2. Implement your matching logic
def my_matching_algorithm(listings, user_prefs):
    matches = []
    for listing in listings:
        score = calculate_match_score(listing, user_prefs)
        if score >= 70:
            matches.append({
                'listing': listing,
                'score': score
            })
    return sorted(matches, key=lambda x: x['score'], reverse=True)

# 3. Get user preferences
user_prefs = await fetch_user_preferences(user_id)

# 4. Run matching
matches = my_matching_algorithm(listings, user_prefs)

# 5. Return results
return {
    'user_id': user_id,
    'matches': matches[:20],
    'total': len(matches)
}
```

## 🧪 Testing

### Test Data Parsing
```bash
python -m app.scripts.test_data_parser
```

### Run Examples
```bash
python -m app.scripts.example_usage
```

### Test API
```bash
# Start the backend
uvicorn app.main:app --reload

# In another terminal
curl http://localhost:8000/api/matches/data/all | python -m json.tool
```

## 🔧 Troubleshooting

### No data returned
- Check Supabase connection (`.env` file)
- Verify mock data is loaded (`mock_data.sql`)
- Check status filter (only returns "active" by default)

### Type errors
- All values are JSON-serializable (no Decimal, datetime objects)
- Use `serialize_value()` for custom objects

### Performance issues
- Use `limit` parameter to reduce data
- Consider caching for frequently accessed data
- Use specific filters instead of fetching all data

## 📚 More Information

- See `DATA_PARSER_README.md` for detailed documentation
- Check `example_usage.py` for 8 complete examples
- Review `data_parser.py` for implementation details
