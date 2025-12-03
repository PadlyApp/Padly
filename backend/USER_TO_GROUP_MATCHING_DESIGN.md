# 🤝 User-to-Group Matching System Design

## Overview
Allow individual users to discover and join existing roommate groups that match their preferences, ensuring all group members are compatible BEFORE the group searches for housing.

---

## 🎯 **The Problem We're Solving**

**Current State**:
- Users must find roommates outside the app
- Groups are formed externally (friends, Slack, Reddit)
- Groups come to app already complete

**Desired State**:
- Users can browse open groups on the app
- System recommends compatible groups
- Users can request to join groups that fit their preferences
- Group creators approve/reject requests
- Everything happens in-app!

---

## 🏗️ **System Architecture**

### **1. Data Model** (Already Exists!)

You already have everything you need:

```sql
-- Users with their preferences
users (id, full_name, company_name, school_name, verification_status)
personal_preferences (user_id, target_city, budget_min, budget_max, 
                      move_in_date, lifestyle_preferences)

-- Groups looking for members
roommate_groups (id, creator_user_id, target_city, budget_per_person_min,
                 budget_per_person_max, target_move_in_date, target_group_size,
                 target_bedrooms, target_bathrooms, target_furnished, etc.)

-- Group membership tracking
group_members (group_id, user_id, is_creator, status, joined_at)
```

**Key insight**: 
- Groups with `member_count < target_group_size` are **open for new members**
- User preferences in `personal_preferences` should align with `roommate_groups` targets

---

## 🧮 **Compatibility Scoring Algorithm**

### **Score Calculation: User → Group (0-100 points)**

When a user is looking for groups, calculate how compatible they are with each open group:

```python
def calculate_user_group_compatibility(user, user_prefs, group):
    """
    Calculate compatibility score between a user and a group.
    Higher score = better match.
    Range: 0-100 points
    """
    
    score = 0
    reasons = []  # Explanation for the score
    
    # ============================================================
    # 1. HARD CONSTRAINTS (Must ALL Pass) - Binary
    # ============================================================
    
    # City Match (REQUIRED)
    if user_prefs.target_city.lower() != group.target_city.lower():
        return {"score": 0, "reasons": ["City mismatch"], "eligible": False}
    
    # Budget Overlap (REQUIRED)
    user_budget_min = user_prefs.budget_min
    user_budget_max = user_prefs.budget_max
    group_budget_min = group.budget_per_person_min
    group_budget_max = group.budget_per_person_max
    
    # Check if budget ranges overlap
    if user_budget_max < group_budget_min or user_budget_min > group_budget_max:
        return {"score": 0, "reasons": ["Budget ranges don't overlap"], "eligible": False}
    
    # Move-in Date Proximity (REQUIRED - within ±60 days)
    date_diff = abs((user_prefs.move_in_date - group.target_move_in_date).days)
    if date_diff > 60:
        return {"score": 0, "reasons": [f"Move-in dates too far apart ({date_diff} days)"], "eligible": False}
    
    # Group has space (REQUIRED)
    current_member_count = count_accepted_members(group.id)
    if current_member_count >= group.target_group_size:
        return {"score": 0, "reasons": ["Group is full"], "eligible": False}
    
    # ============================================================
    # 2. SOFT PREFERENCES (Scoring 0-100)
    # ============================================================
    
    # Budget Fit (25 points)
    # Best score when user's midpoint matches group's midpoint
    user_budget_mid = (user_budget_min + user_budget_max) / 2
    group_budget_mid = (group_budget_min + group_budget_max) / 2
    budget_diff = abs(user_budget_mid - group_budget_mid)
    
    if budget_diff <= 100:
        budget_score = 25
        reasons.append("Budget perfectly aligned")
    elif budget_diff <= 300:
        budget_score = 20
        reasons.append("Budget well aligned")
    elif budget_diff <= 500:
        budget_score = 15
    else:
        budget_score = 10
    
    score += budget_score
    
    # Move-in Date Fit (20 points)
    # Best score when dates are within ±7 days
    if date_diff <= 7:
        date_score = 20
        reasons.append("Move-in dates very close")
    elif date_diff <= 14:
        date_score = 16
        reasons.append("Move-in dates close")
    elif date_diff <= 30:
        date_score = 12
    else:
        date_score = 8
    
    score += date_score
    
    # Company/School Match (15 points)
    # Bonus for going to same company or school
    if user.company_name and user.company_name == get_any_member_company(group):
        score += 15
        reasons.append(f"Same company: {user.company_name}")
    elif user.school_name and user.school_name == get_any_member_school(group):
        score += 15
        reasons.append(f"Same school: {user.school_name}")
    elif user.company_name or user.school_name:
        score += 5  # Some affiliation bonus
    
    # Verification Status (15 points)
    # Verified users are more trustworthy
    if user.verification_status == "email_verified":
        score += 10
        reasons.append("Email verified")
    elif user.verification_status == "admin_verified":
        score += 15
        reasons.append("Admin verified")
    
    # Check if group has verified members (prefer verified groups)
    group_verification_rate = get_group_verification_rate(group.id)
    if group_verification_rate >= 0.5:
        score += 5
        reasons.append("Group has verified members")
    
    # Lifestyle Compatibility (25 points)
    # Compare lifestyle_preferences JSONB fields
    lifestyle_score = calculate_lifestyle_compatibility(
        user_prefs.lifestyle_preferences,
        get_group_lifestyle_aggregate(group.id)
    )
    score += lifestyle_score
    
    if lifestyle_score >= 20:
        reasons.append("Excellent lifestyle match")
    elif lifestyle_score >= 15:
        reasons.append("Good lifestyle match")
    
    # ============================================================
    # 3. ADDITIONAL BONUSES
    # ============================================================
    
    # Bedrooms/Bathrooms Preference Alignment (bonus points)
    # If user has preferences that match group targets
    if hasattr(user_prefs, 'desired_bedrooms'):
        if user_prefs.desired_bedrooms == group.target_bedrooms:
            score += 3
            reasons.append("Bedroom preference matches")
    
    if hasattr(user_prefs, 'desired_bathrooms'):
        if user_prefs.desired_bathrooms == group.target_bathrooms:
            score += 2
            reasons.append("Bathroom preference matches")
    
    # ============================================================
    # FINAL RESULT
    # ============================================================
    
    return {
        "score": min(score, 100),  # Cap at 100
        "reasons": reasons,
        "eligible": True,
        "compatibility_level": get_compatibility_level(score)
    }


def get_compatibility_level(score):
    """Convert numeric score to human-readable level"""
    if score >= 80:
        return "Excellent Match"
    elif score >= 65:
        return "Great Match"
    elif score >= 50:
        return "Good Match"
    elif score >= 35:
        return "Fair Match"
    else:
        return "Poor Match"


def calculate_lifestyle_compatibility(user_lifestyle, group_lifestyle):
    """
    Compare lifestyle preferences (JSONB fields).
    Returns score 0-25.
    
    Example user_lifestyle:
    {
        "cleanliness": "very_clean",
        "noise_level": "quiet",
        "guests_frequency": "rarely",
        "smoking": "no_smoking",
        "pets": "no_pets",
        "diet": "vegetarian"
    }
    """
    if not user_lifestyle or not group_lifestyle:
        return 12  # Neutral score if no data
    
    score = 0
    max_points = 25
    
    # Define compatibility rules for each attribute
    compatibility_rules = {
        "cleanliness": {
            ("very_clean", "very_clean"): 5,
            ("very_clean", "clean"): 4,
            ("clean", "clean"): 5,
            ("clean", "moderate"): 3,
            # Opposite extremes = 0
        },
        "noise_level": {
            ("quiet", "quiet"): 5,
            ("quiet", "moderate"): 3,
            ("moderate", "moderate"): 5,
            ("loud", "loud"): 5,
            ("quiet", "loud"): 0,  # Incompatible
        },
        "smoking": {
            ("no_smoking", "no_smoking"): 5,
            ("no_smoking", "outdoor_only"): 3,
            ("no_smoking", "smoking_ok"): 0,  # Deal-breaker
        },
        "pets": {
            ("no_pets", "no_pets"): 5,
            ("no_pets", "pets_ok"): 2,
            ("pets_ok", "pets_ok"): 5,
        },
        "guests_frequency": {
            ("rarely", "rarely"): 3,
            ("occasionally", "occasionally"): 3,
            ("frequently", "frequently"): 3,
        }
    }
    
    # Calculate compatibility for each attribute
    for attribute, rules in compatibility_rules.items():
        user_val = user_lifestyle.get(attribute)
        group_val = group_lifestyle.get(attribute)
        
        if user_val and group_val:
            pair = (user_val, group_val)
            if pair in rules:
                score += rules[pair]
            elif (group_val, user_val) in rules:  # Check reverse pair
                score += rules[(group_val, user_val)]
    
    # Normalize to 0-25
    return min(score, max_points)


def get_group_lifestyle_aggregate(group_id):
    """
    Aggregate lifestyle preferences of current group members.
    Returns the most common preference for each attribute.
    """
    members = get_group_members(group_id)
    
    # Collect all lifestyle preferences
    all_preferences = []
    for member in members:
        user_prefs = get_user_preferences(member.user_id)
        if user_prefs and user_prefs.lifestyle_preferences:
            all_preferences.append(user_prefs.lifestyle_preferences)
    
    if not all_preferences:
        return {}
    
    # Find most common value for each key
    aggregated = {}
    all_keys = set()
    for prefs in all_preferences:
        all_keys.update(prefs.keys())
    
    for key in all_keys:
        values = [p.get(key) for p in all_preferences if key in p]
        if values:
            # Most common value
            aggregated[key] = max(set(values), key=values.count)
    
    return aggregated
```

---

## 🔍 **API Endpoints to Implement**

### **1. Discover Groups (Main Feature)**

```http
GET /api/roommate-groups/discover

Query Parameters:
- city: string (required)
- budget_min: number
- budget_max: number
- move_in_date: date
- min_compatibility_score: number (default: 50)
- limit: number (default: 20)

Response:
{
  "status": "success",
  "count": 15,
  "groups": [
    {
      "id": "group-uuid-1",
      "group_name": "Google Engineers - SF Mission",
      "description": "Two Google SWEs looking for a third...",
      "target_city": "San Francisco",
      "budget_per_person_min": 1200,
      "budget_per_person_max": 1800,
      "target_move_in_date": "2025-12-01",
      "target_group_size": 3,
      "current_member_count": 2,
      "open_spots": 1,
      "members": [
        {
          "id": "user-1",
          "full_name": "Alice J.",
          "company_name": "Google",
          "verification_status": "email_verified",
          "is_creator": true
        },
        {
          "id": "user-2",
          "full_name": "Bob K.",
          "company_name": "Google",
          "verification_status": "email_verified"
        }
      ],
      "compatibility": {
        "score": 87,
        "level": "Excellent Match",
        "reasons": [
          "Budget perfectly aligned",
          "Move-in dates very close",
          "Same company: Google",
          "Email verified",
          "Group has verified members",
          "Excellent lifestyle match"
        ]
      },
      "created_at": "2025-11-20T10:00:00Z"
    },
    {
      "id": "group-uuid-2",
      "group_name": "Stanford Grads - Palo Alto",
      "compatibility": {
        "score": 72,
        "level": "Great Match",
        ...
      },
      ...
    }
  ]
}
```

### **2. Request to Join Group**

```http
POST /api/roommate-groups/{group_id}/request-join

Headers:
Authorization: Bearer <user_token>

Body:
{
  "message": "Hi! I'm also a Google SWE looking for housing in SF. Would love to join!"
}

Response:
{
  "status": "success",
  "message": "Join request sent to group creator",
  "data": {
    "group_id": "group-uuid-1",
    "user_id": "current-user-uuid",
    "status": "pending",
    "requested_at": "2025-11-30T17:00:00Z"
  }
}

Database:
Inserts into group_members:
  (group_id, user_id, is_creator=false, status='pending')
```

### **3. Group Creator Reviews Requests**

```http
GET /api/roommate-groups/{group_id}/pending-requests

Response:
{
  "status": "success",
  "count": 3,
  "requests": [
    {
      "user_id": "user-3",
      "full_name": "Charlie M.",
      "company_name": "Google",
      "school_name": null,
      "verification_status": "email_verified",
      "profile_picture_url": "...",
      "requested_at": "2025-11-30T17:00:00Z",
      "user_preferences": {
        "target_city": "San Francisco",
        "budget_min": 1300,
        "budget_max": 1700,
        "move_in_date": "2025-12-05",
        "lifestyle_preferences": {
          "cleanliness": "very_clean",
          "noise_level": "quiet"
        }
      },
      "compatibility": {
        "score": 82,
        "level": "Excellent Match",
        "reasons": [...]
      }
    }
  ]
}
```

### **4. Approve/Reject Join Request**

```http
POST /api/roommate-groups/{group_id}/members/{user_id}/approve

Response:
{
  "status": "success",
  "message": "User added to group",
  "group": {
    "id": "group-uuid-1",
    "current_member_count": 3,
    "target_group_size": 3,
    "is_full": true
  }
}

Database:
Updates group_members.status: 'pending' → 'accepted'
```

```http
POST /api/roommate-groups/{group_id}/members/{user_id}/reject

Response:
{
  "status": "success",
  "message": "Request rejected"
}

Database:
Updates group_members.status: 'pending' → 'rejected'
Or deletes the row
```

---

## 📝 **Implementation Steps**

### **Step 1: Create the Compatibility Service**

File: `app/services/user_group_matching.py`

```python
"""
User-to-Group Matching Service

Matches individual users to existing roommate groups based on
compatibility scoring.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.services.supabase_client import get_supabase_admin_client


async def find_compatible_groups(
    user_id: str,
    user_prefs: Dict[str, Any],
    min_score: int = 50,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Find groups compatible with a user's preferences.
    
    Args:
        user_id: User's ID
        user_prefs: User's preferences dict
        min_score: Minimum compatibility score (0-100)
        limit: Max results
        
    Returns:
        List of groups with compatibility scores
    """
    supabase = get_supabase_admin_client()
    
    # 1. Get user details
    user_response = await supabase.table("users").select("*").eq("id", user_id).execute()
    if not user_response.data:
        raise ValueError("User not found")
    user = user_response.data[0]
    
    # 2. Get open groups (not full)
    # Query groups where current member count < target_group_size
    groups_response = await supabase.table("roommate_groups").select("""
        *,
        group_members(user_id, status)
    """).eq("status", "active").eq("target_city", user_prefs.get("target_city")).execute()
    
    # 3. Filter to groups with open spots
    open_groups = []
    for group in groups_response.data:
        accepted_members = [m for m in group['group_members'] if m['status'] == 'accepted']
        if len(accepted_members) < group['target_group_size']:
            group['current_member_count'] = len(accepted_members)
            group['open_spots'] = group['target_group_size'] - len(accepted_members)
            open_groups.append(group)
    
    # 4. Score each group
    scored_groups = []
    for group in open_groups:
        compatibility = calculate_user_group_compatibility(user, user_prefs, group)
        
        if compatibility['eligible'] and compatibility['score'] >= min_score:
            group['compatibility'] = compatibility
            scored_groups.append(group)
    
    # 5. Sort by score (highest first)
    scored_groups.sort(key=lambda g: g['compatibility']['score'], reverse=True)
    
    # 6. Return top results
    return scored_groups[:limit]


def calculate_user_group_compatibility(
    user: Dict,
    user_prefs: Dict,
    group: Dict
) -> Dict[str, Any]:
    """Implementation as shown above"""
    # ... (full implementation from algorithm section)
    pass
```

### **Step 2: Add API Route**

File: `app/routes/groups.py` (add to existing file)

```python
@router.get("/discover", response_model=Dict)
async def discover_groups(
    city: str = Query(..., description="Target city"),
    budget_min: Optional\[float] = None,
    budget_max: Optional[float] = None,
    move_in_date: Optional[str] = None,
    min_compatibility_score: int = Query(50, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(require_user_token)
):
    """
    Discover compatible roommate groups.
    """
    from app.services.user_group_matching import find_compatible_groups
    from app.dependencies.auth import get_current_user
    
    # Get current user
    user_id = get_current_user(token)
    
    # Build user preferences
    # First try to get from personal_preferences table
    supabase = get_supabase_admin_client()
    prefs_response = await supabase.table("personal_preferences").select("*").eq("user_id", user_id).execute()
    
    if prefs_response.data:
        user_prefs = prefs_response.data[0]
    else:
        # Use query parameters as preferences
        user_prefs = {
            "target_city": city,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "move_in_date": move_in_date
        }
    
    # Find compatible groups
    groups = await find_compatible_groups(
        user_id=user_id,
        user_prefs=user_prefs,
        min_score=min_compatibility_score,
        limit=limit
    )
    
    return {
        "status": "success",
        "count": len(groups),
        "groups": groups
    }
```

### **Step 3: Add Pending Requests Endpoint**

```python
@router.get("/{group_id}/pending-requests", response_model=Dict)
async def get_pending_requests(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Get pending join requests for a group.
    Only the group creator can view.
    """
    user_id = get_current_user(token)
    supabase = get_supabase_admin_client()
    
    # Verify user is group creator
    group_response = await supabase.table("roommate_groups").select("*").eq("id", group_id).execute()
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data[0]
    if group['creator_user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Only group creator can view requests")
    
    # Get pending members
    pending_response = await supabase.table("group_members").select("""
        user_id,
        joined_at,
        users(*)
    """).eq("group_id", group_id).eq("status", "pending").execute()
    
    # Calculate compatibility for each pending user
    requests = []
    for member_data in pending_response.data:
        user = member_data['users']
        
        # Get user preferences
        prefs_response = await supabase.table("personal_preferences").select("*").eq("user_id", user['id']).execute()
        user_prefs = prefs_response.data[0] if prefs_response.data else {}
        
        # Calculate compatibility
        from app.services.user_group_matching import calculate_user_group_compatibility
        compatibility = calculate_user_group_compatibility(user, user_prefs, group)
        
        requests.append({
            "user_id": user['id'],
            "full_name": user['full_name'],
            "company_name": user.get('company_name'),
            "school_name": user.get('school_name'),
            "verification_status": user['verification_status'],
            "requested_at": member_data['joined_at'],
            "user_preferences": user_prefs,
            "compatibility": compatibility
        })
    
    # Sort by compatibility score
    requests.sort(key=lambda r: r['compatibility']['score'], reverse=True)
    
    return {
        "status": "success",
        "count": len(requests),
        "requests": requests
    }
```

---

## 🎨 **Frontend User Experience**

### **User Flow**:

1. **User signs up** → Sets preferences
2. **User clicks "Find Groups"** → Sees ranked list of compatible groups
3. **User browses groups** → Views group details, member profiles, compatibility reasons
4. **User clicks "Request to Join"** → Sends request with optional message
5. **Group creator gets notification** → Reviews pending requests with compatibility scores
6. **Creator approves** → User joins group
7. **Group is complete** → Now eligible for stable matching with listings

---

## 🔐 **Privacy & Safety Considerations**

1. **Limited Profile Info**: Show only name, company/school, verification status
2. **No Contact Info**: Users can't message directly until approved
3. **Creator Control**: Only creator can approve/reject requests
4. **Verification Bonus**: Incentivize verification for trust
5. **Report/Block**: Add ability to report suspicious users

---

## 📊 **Metrics to Track**

1. **Discovery metrics**:
   - % of users who use "Find Groups"
   - Average groups viewed per session
   - Average compatibility score of viewed groups

2. **Conversion metrics**:
   - % of users who request to join
   - % of requests that get approved
   - Average time from request to approval

3. **Success metrics**:
   - % of groups that complete via this system
   - Match quality of groups formed this way vs. external groups

---

## 🚀 **Next Steps**

1. ✅ **Implement compatibility algorithm** (scoring.py)
2. ✅ **Add discover endpoint** (GET /api/roommate-groups/discover)
3. ✅ **Add pending requests endpoint** (GET /api/roommate-groups/{id}/pending-requests
4. ✅ **Add approve/reject endpoints** (existing in groups.py)
5. ⏳ **Build frontend UI** for group discovery
6. ⏳ **Add notifications** when requests are received/approved
7. ⏳ **Add analytics** to track feature usage

---

**This approach**:
- ✅ Uses existing data model
- ✅ Similar to your stable matching algorithm
- ✅ Keeps everything in-app
- ✅ Provides transparency (compatibility scores & reasons)
- ✅ Scales well

Ready to implement? I can help you build the actual code!
