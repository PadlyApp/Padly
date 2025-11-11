# Data Parser Service

This service fetches data from Supabase and parses it into JSON-ready objects for use in matching algorithms.

## Overview

The data parser provides:
1. **Listings Parser** - Fetches and formats all listing data
2. **Groups Parser** - Fetches and formats roommate group data with member information
3. **Serialization** - Converts Decimal, DateTime, and other non-JSON types to proper formats
4. **Algorithm-Ready Output** - Clean JSON objects ready for matching algorithms

## Files

- `app/services/data_parser.py` - Main data parsing service
- `app/scripts/test_data_parser.py` - Test script to verify parsing
- `app/services/matching_algorithm.py` - Updated to use parsed data

## Usage

### 1. In Python Scripts

```python
from app.services.data_parser import (
    fetch_and_parse_listings,
    fetch_and_parse_groups,
    fetch_parsed_data_for_algorithms
)

# Fetch all data at once
async def example():
    data = await fetch_parsed_data_for_algorithms()
    listings = data['listings']
    groups = data['groups']
    
    print(f"Found {len(listings)} listings")
    print(f"Found {len(groups)} groups")
    
    # Use in your algorithm
    for listing in listings:
        print(listing['title'], listing['price_per_month'])
```

### 2. Via API Endpoints

The following endpoints are available in `/api/matches`:

#### Get All Listings (Parsed)
```bash
GET /api/matches/data/listings
```
Returns all active listings in JSON format.

#### Get All Groups (Parsed)
```bash
GET /api/matches/data/groups
```
Returns all active groups with member information.

#### Get All Data
```bash
GET /api/matches/data/all
```
Returns both listings and groups in one response.

#### Get User Matches (v2)
```bash
GET /api/matches/{user_id}/v2?limit=20
```
Fetches fresh data and returns matches for a specific user.

#### Get Group Matches
```bash
GET /api/matches/{user_id}/groups?limit=20
```
Returns roommate group matches for a user.

### 3. Test Script

Run the test script to verify data parsing and save JSON files:

```bash
cd backend
python -m app.scripts.test_data_parser
```

This will:
- Fetch data from Supabase
- Parse and serialize it
- Display a summary
- Save JSON files:
  - `parsed_listings.json` - All listings
  - `parsed_groups.json` - All groups
  - `parsed_algorithm_data.json` - Combined data

## Data Structure

### Listing Object
```json
{
  "id": "uuid",
  "host_user_id": "uuid",
  "status": "active",
  "title": "Cozy Studio in Downtown SF",
  "description": "Beautiful studio apartment...",
  "property_type": "entire_place",
  "lease_type": "fixed_term",
  "lease_duration_months": 4,
  "number_of_bedrooms": 1,
  "number_of_bathrooms": 1.0,
  "area_sqft": 750,
  "furnished": true,
  "price_per_month": 2200.0,
  "utilities_included": false,
  "deposit_amount": 2200.0,
  "address_line_1": "123 Market Street",
  "city": "San Francisco",
  "state_province": "CA",
  "postal_code": "94102",
  "country": "USA",
  "available_from": "2025-05-01",
  "available_to": "2025-08-31",
  "amenities": {
    "wifi": true,
    "laundry": true,
    "parking": false,
    "ac": true
  },
  "house_rules": "No smoking, no pets...",
  "shared_spaces": ["lobby", "laundry room"],
  "view_count": 0,
  "created_at": "2025-11-10T12:00:00",
  "updated_at": "2025-11-10T12:00:00"
}
```

### Group Object
```json
{
  "id": "uuid",
  "creator_user_id": "uuid",
  "status": "active",
  "group_name": "Tech Professionals Group",
  "description": "Group of tech workers...",
  "target_city": "San Francisco",
  "budget_per_person_min": 1200.0,
  "budget_per_person_max": 2000.0,
  "target_move_in_date": "2025-06-01",
  "target_group_size": 3,
  "current_size": 2,
  "members": [
    {
      "user_id": "uuid",
      "is_creator": true,
      "joined_at": "2025-11-10T12:00:00"
    }
  ],
  "created_at": "2025-11-10T12:00:00",
  "updated_at": "2025-11-10T12:00:00"
}
```

## Key Features

### 1. Type Serialization
Automatically converts:
- `Decimal` → `float`
- `datetime` → ISO 8601 string
- `date` → ISO 8601 string
- Nested structures (dicts and lists)

### 2. Filtering
- Status filtering (active/inactive)
- Limit control
- Member inclusion (for groups)

### 3. User Context
Fetch user-specific data:
```python
# Get user preferences
prefs = await fetch_user_preferences(user_id)

# Get user's roommate post
post = await fetch_roommate_post(user_id)
```

## Integration with Algorithms

The matching algorithm (`matching_algorithm.py`) now has helper functions:

```python
from app.services.matching_algorithm import (
    get_matches_for_user,      # Fetch + match listings
    get_group_matches_for_user, # Fetch + match groups
    get_all_algorithm_data      # Fetch all data
)

# Use in async context
matches = await get_matches_for_user(user_id="...", limit=20)
```

## Development Notes

### Adding New Fields
To add new fields to parsing:

1. Update the parser function in `data_parser.py`:
```python
def parse_listing(raw_listing: Dict[str, Any]) -> Dict[str, Any]:
    parsed = {
        # ... existing fields ...
        'new_field': serialize_value(raw_listing.get('new_field'))
    }
    return parsed
```

2. Ensure the field exists in the Supabase schema

3. Test with the test script

### Error Handling
All functions handle missing/null fields gracefully:
- Returns `None` for missing optional fields
- Uses default values where appropriate
- Serializes nested structures recursively

## Testing

1. **Unit Testing** - Test individual parsing functions
2. **Integration Testing** - Use the test script
3. **API Testing** - Hit the `/api/matches/data/*` endpoints

## Environment Requirements

Ensure your `.env` file has:
```
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key
```

## Future Enhancements

- [ ] Add caching layer for frequently accessed data
- [ ] Add pagination for large datasets
- [ ] Add more filtering options (city, price range, etc.)
- [ ] Add data validation
- [ ] Add mock data generator
- [ ] Add performance metrics
