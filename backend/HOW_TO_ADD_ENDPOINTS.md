# How to Add New Endpoints to Padly Backend

## Quick Reference

### 1. Choose Route Type

**User Route** (JWT-aware, RLS when enabled)
- Use when: Frontend needs to access user-specific data
- Auth: Optional or required JWT
- Example: `/api/users`, `/api/listings`

**Admin Route** (Service role, bypasses RLS)
- Use when: Backend admin operations only
- Auth: None (uses service role internally)
- Example: `/api/admin/users`, `/api/admin/stats`

---

## Step-by-Step Guide

### Option A: Add Endpoint to Existing Route File

**When to use:** Adding a new endpoint to an existing resource (e.g., new user endpoint)

1. **Open the route file**
   ```bash
   # Example: Adding to users
   backend/app/routes/users.py
   ```

2. **Add the endpoint function**
   ```python
   @router.get("/users/search")
   async def search_users(
       query: str,
       token: Optional[str] = Depends(get_user_token)
   ):
       """Search users by name or email"""
       client = SupabaseHTTPClient(token=token)
       
       filters = {
           "full_name": f"ilike.*{query}*"
       }
       
       users = await client.select(
           table="users",
           filters=filters,
           limit=20
       )
       
       return {
           "status": "success",
           "count": len(users),
           "data": users
       }
   ```

3. **Test it**
   ```bash
   curl "http://localhost:8000/api/users/search?query=test"
   ```

---

### Option B: Create New Route File

**When to use:** Adding a completely new resource (e.g., roommate posts)

#### Step 1: Create Route File

```bash
touch backend/app/routes/roommate_posts.py
```

#### Step 2: Write the Route

```python
"""
Roommate Posts routes
CRUD operations for roommate_posts table
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.models import RoommatePostCreate, RoommatePostUpdate

router = APIRouter(prefix="/api", tags=["roommate-posts"])


@router.get("/roommate-posts")
async def list_roommate_posts(
    token: Optional[str] = Depends(get_user_token),
    city: Optional[str] = None,
    limit: Optional[int] = 100
):
    """List all roommate posts"""
    client = SupabaseHTTPClient(token=token)
    
    filters = {}
    if city:
        filters["target_city"] = f"ilike.*{city}*"
    
    posts = await client.select(
        table="roommate_posts",
        filters=filters,
        limit=limit,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(posts),
        "data": posts
    }


@router.post("/roommate-posts")
async def create_roommate_post(
    post_data: RoommatePostCreate,
    token: str = Depends(require_user_token)
):
    """Create a new roommate post"""
    client = SupabaseHTTPClient(token=token)
    
    data = post_data.model_dump(exclude_none=True)
    
    post = await client.insert(
        table="roommate_posts",
        data=data
    )
    
    return {
        "status": "success",
        "message": "Roommate post created successfully",
        "data": post
    }
```

#### Step 3: Register Router in Main App

Edit `backend/app/routes/__init__.py`:
```python
from .users import router as users_router
from .listings import router as listings_router
from .admin import router as admin_router
from .roommate_posts import router as roommate_posts_router  # ADD THIS

__all__ = [
    "users_router",
    "listings_router",
    "admin_router",
    "roommate_posts_router",  # ADD THIS
]
```

Edit `backend/app/main.py`:
```python
from app.routes import (
    users_router, 
    listings_router, 
    admin_router,
    roommate_posts_router  # ADD THIS
)

# Include routers
app.include_router(users_router)
app.include_router(listings_router)
app.include_router(admin_router)
app.include_router(roommate_posts_router)  # ADD THIS
```

#### Step 4: Test

```bash
# Server auto-reloads
curl http://localhost:8000/api/roommate-posts
```

---

## Common Patterns

### 1. List with Filters

```python
@router.get("/resource")
async def list_resource(
    token: Optional[str] = Depends(get_user_token),
    status: Optional[str] = None,
    city: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    client = SupabaseHTTPClient(token=token)
    
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    if city:
        filters["city"] = f"ilike.*{city}*"
    
    results = await client.select(
        table="table_name",
        filters=filters,
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {"status": "success", "count": len(results), "data": results}
```

### 2. Get Single Record

```python
@router.get("/resource/{id}")
async def get_resource(
    id: str,
    token: Optional[str] = Depends(get_user_token)
):
    client = SupabaseHTTPClient(token=token)
    
    record = await client.select_one(
        table="table_name",
        id_value=id
    )
    
    if not record:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    return {"status": "success", "data": record}
```

### 3. Create (Requires JWT)

```python
@router.post("/resource")
async def create_resource(
    data: ResourceCreate,
    token: str = Depends(require_user_token)  # REQUIRED
):
    client = SupabaseHTTPClient(token=token)
    
    record_data = data.model_dump(exclude_none=True)
    
    record = await client.insert(
        table="table_name",
        data=record_data
    )
    
    return {
        "status": "success",
        "message": "Resource created successfully",
        "data": record
    }
```

### 4. Update (Requires JWT)

```python
@router.put("/resource/{id}")
async def update_resource(
    id: str,
    data: ResourceUpdate,
    token: str = Depends(require_user_token)  # REQUIRED
):
    client = SupabaseHTTPClient(token=token)
    
    record_data = data.model_dump(exclude_none=True)
    
    if not record_data:
        raise HTTPException(status_code=400, detail="No data provided")
    
    record = await client.update(
        table="table_name",
        id_value=id,
        data=record_data
    )
    
    return {
        "status": "success",
        "message": "Resource updated successfully",
        "data": record
    }
```

### 5. Delete (Requires JWT)

```python
@router.delete("/resource/{id}")
async def delete_resource(
    id: str,
    token: str = Depends(require_user_token)  # REQUIRED
):
    client = SupabaseHTTPClient(token=token)
    
    await client.delete(
        table="table_name",
        id_value=id
    )
    
    return {
        "status": "success",
        "message": "Resource deleted successfully"
    }
```

### 6. Admin Endpoint (No JWT)

```python
@router.get("/admin/resource")
async def admin_list_resource():
    """Admin-only: Bypasses RLS"""
    client = SupabaseHTTPClient(is_admin=True)  # Service role
    
    results = await client.select(
        table="table_name",
        limit=100
    )
    
    return {"status": "success", "count": len(results), "data": results}
```

---

## PostgREST Filter Examples

### Exact Match
```python
filters = {"status": "eq.active"}
```

### Pattern Matching (Case Insensitive)
```python
filters = {"city": "ilike.*san francisco*"}
```

### Greater Than / Less Than
```python
filters = {
    "price": "gte.1000",  # price >= 1000
    "price": "lte.5000"   # price <= 5000
}
```

### Multiple Filters
```python
filters = {
    "status": "eq.active",
    "city": "eq.New York",
    "price": "lte.3000"
}
```

### OR Filters
```python
filters = {"role": "in.(renter,host)"}
```

---

## JWT Decision Tree

```
Do you need authentication?
│
├─ NO → Use `get_user_token` (Optional)
│        token: Optional[str] = Depends(get_user_token)
│        • Works with or without JWT
│        • When RLS enabled: anonymous vs authenticated access
│
└─ YES → Use `require_user_token` (Required)
         token: str = Depends(require_user_token)
         • Returns 401 if no JWT
         • Use for: POST, PUT, DELETE operations
```

---

## Response Format Standards

### Success Response
```json
{
  "status": "success",
  "message": "Optional message",
  "data": { ... } or [ ... ]
}
```

### List Response
```json
{
  "status": "success",
  "count": 10,
  "data": [ ... ]
}
```

### Error Response (automatic)
```json
{
  "detail": "Error message"
}
```

---

## Testing Checklist

- [ ] Test without JWT: `curl http://localhost:8000/api/endpoint`
- [ ] Test with mock JWT: `curl -H "Authorization: Bearer test" http://localhost:8000/api/endpoint`
- [ ] Test POST with data: `curl -X POST -H "Content-Type: application/json" -d '{"field":"value"}' ...`
- [ ] Check auto-docs: http://localhost:8000/docs
- [ ] Verify in admin endpoint: `curl http://localhost:8000/api/admin/...`

---

## Quick Commands

```bash
# Start server
cd backend
python3 -m uvicorn app.main:app --reload --port 8000

# Test endpoint
curl http://localhost:8000/api/your-endpoint

# Test with JWT
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/your-endpoint

# Test POST
curl -X POST http://localhost:8000/api/your-endpoint \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# Check docs
open http://localhost:8000/docs
```

---

## Common Issues

### Server doesn't reload
- Kill and restart: `pkill -f uvicorn && python3 -m uvicorn app.main:app --reload`

### Import error
- Check `__init__.py` exports
- Verify router is imported in `main.py`

### 404 on new endpoint
- Check router prefix in decorator
- Verify router is included in main app
- Check URL path matches

### JWT not working
- Verify header format: `Authorization: Bearer <token>`
- Check dependency: `get_user_token` vs `require_user_token`
- Test without JWT first (if optional)

---

## File Locations Quick Reference

```
backend/app/
├── routes/
│   ├── __init__.py           ← Register new routers here
│   ├── users.py              ← User endpoints
│   ├── listings.py           ← Listing endpoints
│   ├── admin.py              ← Admin endpoints
│   └── your_new_route.py     ← Your new endpoints
├── services/
│   └── supabase_client.py    ← HTTP client (don't modify)
├── dependencies/
│   ├── auth.py               ← JWT extraction (don't modify)
│   └── supabase.py           ← Client factory (legacy)
├── models.py                 ← Pydantic models for validation
├── db.py                     ← Database config (don't modify)
└── main.py                   ← Register routers here
```

---

## Need Help?

1. Check existing routes: `backend/app/routes/users.py` or `listings.py`
2. Check API docs: http://localhost:8000/docs
3. Check endpoint registry: `backend/ENDPOINT_REGISTRY.md`
4. Test with curl or Postman

---

**Last Updated:** October 19, 2025
