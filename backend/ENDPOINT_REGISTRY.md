# Padly Backend Endpoint Registry

**Last Updated:** October 19, 2025  
**Server:** http://localhost:8000  
**API Docs:** http://localhost:8000/docs

---

## Authentication Overview

### JWT Token Flow

```
┌─────────────┐     Sign Up/Login     ┌──────────────┐
│  Frontend   │ ───────────────────▶  │   Supabase   │
│  (Next.js)  │                        │     Auth     │
└─────────────┘                        └──────────────┘
       │                                      │
       │                                      │
       │              JWT Token               │
       │ ◀────────────────────────────────────┘
       │
       │  Authorization: Bearer <jwt>
       │
       ▼
┌─────────────┐
│   FastAPI   │
│   Backend   │
└─────────────┘
       │
       ├── Optional JWT (get_user_token)
       │   • Works with or without JWT
       │   • Used for: GET endpoints
       │   • RLS filters by user when JWT present
       │
       └── Required JWT (require_user_token)
           • Returns 401 if no JWT
           • Used for: POST, PUT, DELETE
           • RLS enforces user permissions
```

### Auth Dependencies

**File:** `backend/app/dependencies/auth.py`

#### 1. `get_user_token()` - Optional JWT
```python
from app.dependencies.auth import get_user_token

@router.get("/endpoint")
async def endpoint(token: Optional[str] = Depends(get_user_token)):
    # token is None if no Authorization header
    # token is the JWT string if header present
    pass
```

**Use Cases:**
- Public read endpoints (listings, search)
- Endpoints that work for both anonymous and authenticated users
- When RLS should filter based on user context if JWT present

#### 2. `require_user_token()` - Required JWT
```python
from app.dependencies.auth import require_user_token

@router.post("/endpoint")
async def endpoint(token: str = Depends(require_user_token)):
    # Raises 401 if no Authorization header
    # Returns JWT string if present
    pass
```

**Use Cases:**
- Create, Update, Delete operations
- User-specific data endpoints
- Any operation requiring authentication

---

## HTTP Client

**File:** `backend/app/services/supabase_client.py`

### SupabaseHTTPClient Class

```python
from app.services.supabase_client import SupabaseHTTPClient

# User client (uses ANON_KEY + optional JWT)
client = SupabaseHTTPClient(token=jwt_token)  # token can be None

# Admin client (uses SERVICE_ROLE_KEY, bypasses RLS)
client = SupabaseHTTPClient(is_admin=True)
```

### Available Methods

```python
# SELECT - Get multiple records
results = await client.select(
    table="table_name",
    columns="*",              # or "id,name,email"
    filters={"status": "eq.active"},
    limit=100,
    offset=0,
    order="created_at.desc"
)

# SELECT ONE - Get single record by ID
record = await client.select_one(
    table="table_name",
    id_value="uuid-here",
    id_column="id"  # default
)

# INSERT - Create new record
record = await client.insert(
    table="table_name",
    data={"name": "value", ...}
)

# UPDATE - Update existing record
record = await client.update(
    table="table_name",
    id_value="uuid-here",
    data={"field": "new_value"},
    id_column="id"  # default
)

# DELETE - Delete record
await client.delete(
    table="table_name",
    id_value="uuid-here",
    id_column="id"  # default
)

# COUNT - Get total count
total = await client.count(
    table="table_name",
    filters={"status": "eq.active"}
)
```

---

## Current Endpoints

### 🔹 User Endpoints

**File:** `backend/app/routes/users.py`  
**Prefix:** `/api`  
**Tag:** `users`

#### 1. List All Users
```http
GET /api/users
```

**Auth:** Optional JWT (`get_user_token`)  
**Query Parameters:**
- `limit` (int, default: 100) - Max records to return
- `offset` (int, default: 0) - Records to skip

**Response:**
```json
{
  "status": "success",
  "count": 10,
  "data": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "John Doe",
      "role": "renter",
      "verification_status": "verified",
      "profile_picture_url": "https://...",
      "bio": "Student looking for housing",
      "phone_number": "+1234567890",
      "created_at": "2025-10-19T...",
      "updated_at": "2025-10-19T..."
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/api/users
curl http://localhost:8000/api/users?limit=50&offset=100
```

---

#### 2. Get User by ID
```http
GET /api/users/{user_id}
```

**Auth:** Optional JWT (`get_user_token`)  
**Path Parameters:**
- `user_id` (UUID) - User ID

**Response:**
```json
{
  "status": "success",
  "data": { /* user object */ }
}
```

**Errors:**
- `404` - User not found

**Example:**
```bash
curl http://localhost:8000/api/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b
```

---

#### 3. Create New User
```http
POST /api/users
```

**Auth:** Required JWT (`require_user_token`)  
**Content-Type:** `application/json`

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "full_name": "Jane Smith",
  "role": "renter",
  "phone_number": "+1234567890",
  "bio": "Graduate student",
  "profile_picture_url": "https://..."
}
```

**Required Fields:**
- `email` (EmailStr)
- `full_name` (string)
- `role` (enum: "renter" | "host" | "admin")

**Optional Fields:**
- `phone_number` (string)
- `bio` (string)
- `profile_picture_url` (string)
- `verification_status` (enum: "unverified" | "pending" | "verified")

**Response:**
```json
{
  "status": "success",
  "message": "User created successfully",
  "data": { /* created user object */ }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{
    "email": "test@example.com",
    "full_name": "Test User",
    "role": "renter"
  }'
```

---

#### 4. Update User
```http
PUT /api/users/{user_id}
```

**Auth:** Required JWT (`require_user_token`)  
**Path Parameters:**
- `user_id` (UUID) - User ID

**Request Body:** (all fields optional)
```json
{
  "full_name": "Updated Name",
  "phone_number": "+9876543210",
  "bio": "Updated bio",
  "profile_picture_url": "https://new-url.com/pic.jpg"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "User updated successfully",
  "data": { /* updated user object */ }
}
```

**Errors:**
- `400` - No data provided

**Example:**
```bash
curl -X PUT http://localhost:8000/api/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"full_name": "Updated Name"}'
```

---

#### 5. Delete User
```http
DELETE /api/users/{user_id}
```

**Auth:** Required JWT (`require_user_token`)  
**Path Parameters:**
- `user_id` (UUID) - User ID

**Response:**
```json
{
  "status": "success",
  "message": "User deleted successfully"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b \
  -H "Authorization: Bearer <jwt>"
```

---

### 🔹 Listing Endpoints

**File:** `backend/app/routes/listings.py`  
**Prefix:** `/api`  
**Tag:** `listings`

#### 1. List All Listings
```http
GET /api/listings
```

**Auth:** Optional JWT (`get_user_token`)  
**Query Parameters:**
- `status` (string) - Filter by status (e.g., "available", "unavailable")
- `city` (string) - Filter by city (case-insensitive partial match)
- `limit` (int, default: 100) - Max records
- `offset` (int, default: 0) - Records to skip

**Response:**
```json
{
  "status": "success",
  "count": 5,
  "data": [
    {
      "id": "uuid",
      "host_id": "uuid",
      "title": "Cozy Studio in Downtown",
      "description": "Perfect for students...",
      "property_type": "apartment",
      "address": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "zip_code": "94102",
      "country": "USA",
      "price": 1500.00,
      "bedrooms": 1,
      "bathrooms": 1,
      "square_feet": 500,
      "available_from": "2025-11-01",
      "available_until": "2026-05-31",
      "status": "available",
      "amenities": ["wifi", "parking"],
      "rules": ["no smoking", "no pets"],
      "created_at": "2025-10-19T...",
      "updated_at": "2025-10-19T..."
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8000/api/listings
curl "http://localhost:8000/api/listings?status=available&city=san%20francisco"
curl "http://localhost:8000/api/listings?limit=20&offset=40"
```

---

#### 2. Get Listing by ID
```http
GET /api/listings/{listing_id}
```

**Auth:** Optional JWT (`get_user_token`)  
**Path Parameters:**
- `listing_id` (UUID) - Listing ID

**Response:**
```json
{
  "status": "success",
  "data": { /* listing object */ }
}
```

**Errors:**
- `404` - Listing not found

**Example:**
```bash
curl http://localhost:8000/api/listings/abc123-uuid-here
```

---

#### 3. Create New Listing
```http
POST /api/listings
```

**Auth:** Required JWT (`require_user_token`)  
**Content-Type:** `application/json`

**Request Body:**
```json
{
  "host_id": "uuid",
  "title": "Cozy Studio",
  "description": "Perfect for students...",
  "property_type": "apartment",
  "address": "123 Main St",
  "city": "San Francisco",
  "state": "CA",
  "zip_code": "94102",
  "country": "USA",
  "price": 1500.00,
  "bedrooms": 1,
  "bathrooms": 1,
  "square_feet": 500,
  "available_from": "2025-11-01",
  "available_until": "2026-05-31",
  "amenities": ["wifi", "parking"],
  "rules": ["no smoking"]
}
```

**Required Fields:**
- `host_id` (UUID)
- `title` (string)
- `property_type` (enum: "apartment" | "house" | "condo" | "room" | "studio")
- `address` (string)
- `city` (string)
- `state` (string)
- `zip_code` (string)
- `country` (string)
- `price` (decimal)
- `bedrooms` (integer)
- `bathrooms` (integer)

**Optional Fields:**
- `description` (string)
- `square_feet` (integer)
- `available_from` (date)
- `available_until` (date)
- `status` (enum: "draft" | "available" | "unavailable")
- `amenities` (array of strings)
- `rules` (array of strings)

**Response:**
```json
{
  "status": "success",
  "message": "Listing created successfully",
  "data": { /* created listing */ }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/listings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{
    "host_id": "f562bc2f-7a51-4a7a-8033-213bf62eac5b",
    "title": "Studio Apartment",
    "property_type": "studio",
    "address": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "country": "USA",
    "price": 1800.00,
    "bedrooms": 0,
    "bathrooms": 1
  }'
```

---

#### 4. Update Listing
```http
PUT /api/listings/{listing_id}
```

**Auth:** Required JWT (`require_user_token`)  
**Path Parameters:**
- `listing_id` (UUID) - Listing ID

**Request Body:** (all fields optional)
```json
{
  "title": "Updated Title",
  "price": 1600.00,
  "status": "available",
  "description": "Updated description"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Listing updated successfully",
  "data": { /* updated listing */ }
}
```

**Errors:**
- `400` - No data provided

**Example:**
```bash
curl -X PUT http://localhost:8000/api/listings/abc123 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"price": 1700.00, "status": "available"}'
```

---

#### 5. Delete Listing
```http
DELETE /api/listings/{listing_id}
```

**Auth:** Required JWT (`require_user_token`)  
**Path Parameters:**
- `listing_id` (UUID) - Listing ID

**Response:**
```json
{
  "status": "success",
  "message": "Listing deleted successfully"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/listings/abc123 \
  -H "Authorization: Bearer <jwt>"
```

---

### 🔹 Admin Endpoints

**File:** `backend/app/routes/admin.py`  
**Prefix:** `/api/admin`  
**Tag:** `admin`

**Note:** All admin endpoints use `is_admin=True` (service role key) and bypass RLS. No JWT required.

#### 1. List All Users (Admin)
```http
GET /api/admin/users
```

**Auth:** None (uses service role internally)  
**Query Parameters:**
- `limit` (int, default: 100)
- `offset` (int, default: 0)

**Response:** Same as `/api/users` but with full access

**Example:**
```bash
curl http://localhost:8000/api/admin/users
```

---

#### 2. Get User by ID (Admin)
```http
GET /api/admin/users/{user_id}
```

**Auth:** None (uses service role internally)  
**Path Parameters:**
- `user_id` (UUID)

**Response:** Same as `/api/users/{id}` but with full access

**Example:**
```bash
curl http://localhost:8000/api/admin/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b
```

---

#### 3. List All Listings (Admin)
```http
GET /api/admin/listings
```

**Auth:** None (uses service role internally)  
**Query Parameters:**
- `limit` (int, default: 100)
- `offset` (int, default: 0)

**Response:** Same as `/api/listings` but with full access

**Example:**
```bash
curl http://localhost:8000/api/admin/listings
```

---

#### 4. Get Listing by ID (Admin)
```http
GET /api/admin/listings/{listing_id}
```

**Auth:** None (uses service role internally)  
**Path Parameters:**
- `listing_id` (UUID)

**Response:** Same as `/api/listings/{id}` but with full access

**Example:**
```bash
curl http://localhost:8000/api/admin/listings/abc123
```

---

#### 5. Delete User (Admin)
```http
DELETE /api/admin/users/{user_id}
```

**Auth:** None (uses service role internally)  
**Path Parameters:**
- `user_id` (UUID)

**Response:**
```json
{
  "status": "success",
  "message": "User deleted successfully (admin)"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/admin/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b
```

---

#### 6. Get Platform Statistics
```http
GET /api/admin/stats
```

**Auth:** None (uses service role internally)

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_users": 150,
    "total_listings": 45,
    "active_listings": 32
  }
}
```

## Testing Quick Reference

### Test User Endpoints
```bash
# List users
curl http://localhost:8000/api/users

# Create user (needs JWT)
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"email":"test@example.com","full_name":"Test User","role":"renter"}'

# Get user by ID
curl http://localhost:8000/api/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b

# Update user (needs JWT)
curl -X PUT http://localhost:8000/api/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"full_name":"Updated Name"}'

# Delete user (needs JWT)
curl -X DELETE http://localhost:8000/api/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b \
  -H "Authorization: Bearer test-token"
```

### Test Admin Endpoints
```bash
# Get all users (admin, no JWT needed)
curl http://localhost:8000/api/admin/users

# Get platform stats
curl http://localhost:8000/api/admin/stats

# Delete user (admin)
curl -X DELETE http://localhost:8000/api/admin/users/f562bc2f-7a51-4a7a-8033-213bf62eac5b
```

### Test with Real Supabase JWT
```bash
# 1. Get JWT from Supabase Auth (frontend)
# User signs in with Supabase Auth → receives JWT

# 2. Use JWT in API calls
curl http://localhost:8000/api/users \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Next Steps

### To Add New Endpoints:
1. Read `backend/HOW_TO_ADD_ENDPOINTS.md`
2. Create route file or add to existing
3. Register in `__init__.py` and `main.py`
4. Test with curl
5. Update this registry

### To Add RLS Support:
1. Set `VERIFY_JWT=true` in `.env`
2. Enable RLS on tables in Supabase
3. Create RLS policies
4. Test with real JWT tokens

### To Add More Tables:
1. Check schema: `backend/app/schemas/padly_mvp_schema.sql`
2. Add Pydantic models to `models.py`
3. Create route file (e.g., `roommate_posts.py`)
4. Follow patterns from `users.py` or `listings.py`

---

**Documentation Files:**
- `HOW_TO_ADD_ENDPOINTS.md` - Step-by-step guide
- `ENDPOINT_REGISTRY.md` - This file (complete reference)
- `API_DOCUMENTATION.md` - Original API design
- `PHASE_3_COMPLETE.md` - Implementation summary
