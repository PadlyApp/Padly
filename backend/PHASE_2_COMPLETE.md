# Phase 2 Complete: Core Infrastructure

## ✅ What Was Built

### 1. Dependencies Package Structure
```
backend/app/dependencies/
├── __init__.py          # Package exports
├── auth.py             # JWT token extraction
└── supabase.py         # Client factory
```

### 2. Auth Dependencies (`auth.py`)

**`get_user_token()`** - Optional JWT extraction
- Extracts JWT from `Authorization: Bearer <token>` header
- Returns `None` if no token provided (allows anonymous)
- Returns token string if provided
- Raises 401 if header format is invalid

**`require_user_token()`** - Required JWT extraction
- Same as `get_user_token()` but raises 401 if missing
- Use for routes that require authentication

### 3. Supabase Client Factory (`supabase.py`)

**`get_user_client(token)`** - User client
```python
# Creates client with ANON_KEY
client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# If token provided, set Authorization header for RLS
if user_token:
    client.postgrest.auth(user_token)
```

**`get_admin_client()`** - Admin client
```python
# Returns service role client (bypasses RLS)
return supabase_admin
```

---

## 🔑 Key Patterns

### User Routes (RLS-aware)
```python
from fastapi import APIRouter, Depends
from app.dependencies.auth import get_user_token
from app.dependencies.supabase import get_user_client

@router.get("/api/users")
async def list_users(token: str = Depends(get_user_token)):
    client = get_user_client(token)
    response = client.table('users').select("*").execute()
    return {"data": response.data}
```

### Admin Routes (RLS bypass)
```python
from app.dependencies.supabase import get_admin_client

@router.get("/api/admin/users")
async def admin_list_users():
    client = get_admin_client()
    response = client.table('users').select("*").execute()
    return {"data": response.data}
```

---

## ✅ Testing Results

### 1. Without JWT Token
```bash
curl http://localhost:8000/debug-client-factory
```
```json
{
  "token_extracted": false,
  "user_client_created": true,
  "admin_client_created": true
}
```

### 2. With JWT Token
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/debug-client-factory
```
```json
{
  "token_extracted": true,
  "token_prefix": "eyJhbGc...",
  "user_client_created": true,
  "admin_client_created": true
}
```

---

## 🔒 RLS Behavior

### With RLS Disabled (Current)
- `get_user_client(None)` → Works, sees all data
- `get_user_client(token)` → Works, sees all data
- `get_admin_client()` → Works, sees all data

### With RLS Enabled (Future)
- `get_user_client(None)` → `auth.uid()` is NULL → Limited access
- `get_user_client(token)` → `auth.uid()` from JWT → User's data only
- `get_admin_client()` → Bypasses RLS → Sees everything

---

## 📋 Next: Phase 3

Create route modules:
- `routes/users.py` - User CRUD
- `routes/listings.py` - Listing CRUD
- `routes/roommate_posts.py` - Roommate post CRUD
- `routes/admin.py` - Admin operations

Each route will use the dependencies we just built.
