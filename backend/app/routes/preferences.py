"""
Personal Preferences routes
Manage user housing and roommate preferences
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Any
from datetime import date, datetime
from decimal import Decimal
from app.dependencies.auth import get_user_token, require_user_token, resolve_auth_user
from app.dependencies.supabase import get_admin_client
from app.services.supabase_client import SupabaseHTTPClient
from app.models import (
    PersonalPreferencesUpdate,
)
from app.services.controlled_vocab import validate_location, validate_neighborhoods
from app.services.preferences_contract import (
    FRONTEND_FURNISHED_PREFERENCES,
    FRONTEND_GENDER_POLICIES,
    FRONTEND_LEASE_TYPES,
    normalize_gender_policy,
    normalize_lease_type,
    resolve_furnished_preference,
    target_furnished_from_preference,
)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


def convert_dates_to_strings(obj: Any) -> Any:
    """Recursively convert date/datetime objects to ISO format strings"""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_dates_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates_to_strings(item) for item in obj]
    return obj


def make_json_serializable(obj: Any) -> Any:
    """
    Convert non-JSON-serializable types to JSON-compatible types.
    Handles Decimal, date, datetime, and nested structures.
    """
    if isinstance(obj, Decimal):
        # Convert Decimal to float for JSON serialization
        return float(obj)
    elif isinstance(obj, (date, datetime)):
        # Convert date/datetime to ISO format string
        return obj.isoformat()
    elif isinstance(obj, dict):
        # Recursively process dictionary values
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        # Recursively process list items
        return [make_json_serializable(item) for item in obj]
    else:
        # Return as-is for primitives (str, int, bool, None)
        return obj


def serialize_preferences(prefs_data: dict) -> dict:
    """
    Convert preference data to database format.
    Database schema is simple with direct fields matching the model.
    """
    if not prefs_data:
        return prefs_data
    
    # Convert all dates to strings
    prefs_data = convert_dates_to_strings(prefs_data)
    
    # Database fields match the model directly
    db_data = {
        # Frontend hard constraints (PreferencesForm contract)
        "target_country": prefs_data.get("target_country"),
        "target_city": prefs_data.get("target_city"),
        "target_state_province": prefs_data.get("target_state_province"),
        "budget_min": prefs_data.get("budget_min"),
        "budget_max": prefs_data.get("budget_max"),
        "required_bedrooms": prefs_data.get("required_bedrooms"),
        "target_bathrooms": prefs_data.get("target_bathrooms"),
        "target_deposit_amount": prefs_data.get("target_deposit_amount"),
        "furnished_preference": prefs_data.get("furnished_preference"),
        "gender_policy": prefs_data.get("gender_policy"),
        "move_in_date": prefs_data.get("move_in_date"),
        "target_lease_type": prefs_data.get("target_lease_type"),
        "target_lease_duration_months": prefs_data.get("target_lease_duration_months"),
        # Frontend soft constraints
        "target_house_rules": prefs_data.get("target_house_rules"),
        "preferred_neighborhoods": prefs_data.get("preferred_neighborhoods"),
        "lifestyle_preferences": prefs_data.get("lifestyle_preferences"),
        # Legacy compatibility fields
        "target_furnished": prefs_data.get("target_furnished"),
        "target_utilities_included": prefs_data.get("target_utilities_included"),
    }
    
    # Remove None values
    return {k: v for k, v in db_data.items() if v is not None}


def deserialize_preferences(db_data: dict) -> dict:
    """
    Convert database format to API response format.
    Converts Decimal and date objects to JSON-serializable types.
    """
    if not db_data:
        return db_data
    
    # Resolve canonical frontend values from a mix of new + legacy columns.
    furnished_preference = resolve_furnished_preference(
        db_data.get("furnished_preference"),
        db_data.get("target_furnished"),
    ) or "no_preference"
    target_furnished = target_furnished_from_preference(furnished_preference)
    gender_policy = normalize_gender_policy(db_data.get("gender_policy")) or "mixed_ok"
    lease_type = normalize_lease_type(db_data.get("target_lease_type"))

    # Database structure matches API response structure
    result = {
        "user_id": db_data.get("user_id"),
        # Frontend hard constraints
        "target_country": db_data.get("target_country"),
        "target_city": db_data.get("target_city"),
        "target_state_province": db_data.get("target_state_province"),
        "budget_min": db_data.get("budget_min"),
        "budget_max": db_data.get("budget_max"),
        "required_bedrooms": db_data.get("required_bedrooms"),
        "target_bathrooms": db_data.get("target_bathrooms"),
        "target_deposit_amount": db_data.get("target_deposit_amount"),
        "target_furnished": target_furnished,
        "furnished_preference": furnished_preference,
        "gender_policy": gender_policy,
        "move_in_date": db_data.get("move_in_date"),
        "target_lease_type": lease_type,
        "target_lease_duration_months": db_data.get("target_lease_duration_months"),
        # Frontend soft constraints
        "target_house_rules": db_data.get("target_house_rules"),
        "preferred_neighborhoods": db_data.get("preferred_neighborhoods"),
        "lifestyle_preferences": db_data.get("lifestyle_preferences"),
        # Legacy compatibility field (not shown in current frontend form)
        "target_utilities_included": db_data.get("target_utilities_included"),
        "updated_at": db_data.get("updated_at")
    }
    
    # Convert all non-JSON-serializable types (Decimal, datetime, etc.)
    return make_json_serializable(result)


@router.get("/{user_id}")
async def get_user_preferences(
    user_id: str,
    token: str = Depends(require_user_token)
):
    """
    Get personal preferences for the authenticated user.
    Users can only retrieve their own preferences.
    """
    # Verify the caller owns the requested user_id
    try:
        admin = get_admin_client()
        auth_user = resolve_auth_user(admin, token)
        record = admin.table("users").select("id").eq("auth_id", auth_user.id).limit(1).execute()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Authentication check failed. Please try again.") from e

    if not record.data or record.data[0]["id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only view your own preferences")

    client = SupabaseHTTPClient(token=token)
    
    prefs = await client.select_one(
        table="personal_preferences",
        id_value=user_id,
        id_column="user_id"
    )
    
    if not prefs:
        # Return empty preferences if not set yet
        response_data = {
            "status": "success",
            "data": {
                "user_id": user_id,
                # Frontend hard constraints
                "target_country": None,
                "target_city": None,
                "target_state_province": None,
                "budget_min": None,
                "budget_max": None,
                "required_bedrooms": None,
                "target_bathrooms": None,
                "target_deposit_amount": None,
                "target_furnished": None,
                "furnished_preference": "no_preference",
                "gender_policy": "mixed_ok",
                "move_in_date": None,
                "target_lease_type": None,
                "target_lease_duration_months": None,
                # Frontend soft constraints
                "target_house_rules": None,
                "preferred_neighborhoods": None,
                "lifestyle_preferences": None,
                # Legacy compatibility field
                "target_utilities_included": None,
            }
        }
        return JSONResponse(content=make_json_serializable(response_data))
    
    # Convert DB format to API format
    formatted_prefs = deserialize_preferences(prefs)
    
    response_data = {
        "status": "success",
        "data": formatted_prefs
    }
    
    # Use JSONResponse with custom encoder to handle Decimal and other types
    return JSONResponse(content=make_json_serializable(response_data))


@router.put("/{user_id}")
async def update_user_preferences(
    user_id: str,
    preferences: PersonalPreferencesUpdate,
    token: str = Depends(require_user_token)
):
    """
    Update personal preferences for a user.
    
    Creates preferences if they don't exist, updates if they do.
    All fields are optional - only provided fields will be updated.
    
    Legacy stable matching is retired and is no longer triggered on update.
    """
    try:
        client = SupabaseHTTPClient(token=token)
        
        # Convert Pydantic model to dict
        prefs_data = preferences.model_dump(exclude_none=True)
        
        if not prefs_data:
            raise HTTPException(status_code=400, detail="No data provided for update")

        # Load existing record early so partial updates can still validate against
        # already-saved canonical location values.
        existing = await client.select_one(
            table="personal_preferences",
            id_value=user_id,
            id_column="user_id"
        )

        # Strict controlled location validation.
        location_keys = ("target_country", "target_state_province", "target_city")
        has_location_update = any(k in prefs_data for k in location_keys)
        if has_location_update:
            country = prefs_data.get("target_country")
            state = prefs_data.get("target_state_province")
            city = prefs_data.get("target_city")
            if not all(v for v in [country, state, city]):
                raise HTTPException(
                    status_code=422,
                    detail="target_country, target_state_province, and target_city must all be provided together."
                )
            try:
                canonical_country, canonical_state, canonical_city = validate_location(
                    str(country), str(state), str(city)
                )
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

            prefs_data["target_country"] = canonical_country
            prefs_data["target_state_province"] = canonical_state
            prefs_data["target_city"] = canonical_city

        # Validate neighborhood options against effective city (updated or existing).
        if "preferred_neighborhoods" in prefs_data:
            effective_city = prefs_data.get("target_city") or (existing or {}).get("target_city")
            try:
                prefs_data["preferred_neighborhoods"] = validate_neighborhoods(
                    str(effective_city or ""),
                    prefs_data.get("preferred_neighborhoods"),
                )
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

        if "gender_policy" in prefs_data:
            normalized_gender_policy = normalize_gender_policy(prefs_data.get("gender_policy"))
            if normalized_gender_policy is None:
                allowed = ", ".join(sorted(FRONTEND_GENDER_POLICIES))
                raise HTTPException(status_code=422, detail=f"gender_policy must be one of: {allowed}")
            prefs_data["gender_policy"] = normalized_gender_policy

        if "target_lease_type" in prefs_data:
            normalized_lease_type = normalize_lease_type(prefs_data.get("target_lease_type"))
            if normalized_lease_type is None:
                # Keep accepting known frontend values only.
                allowed = ", ".join(sorted(FRONTEND_LEASE_TYPES))
                raise HTTPException(status_code=422, detail=f"target_lease_type must be one of: {allowed}")
            prefs_data["target_lease_type"] = normalized_lease_type

        # Keep tri-state furnished preference as source-of-truth.
        if "furnished_preference" in prefs_data or "target_furnished" in prefs_data:
            resolved_furnished_preference = resolve_furnished_preference(
                prefs_data.get("furnished_preference"),
                prefs_data.get("target_furnished"),
            )
            if resolved_furnished_preference is None:
                allowed = ", ".join(sorted(FRONTEND_FURNISHED_PREFERENCES))
                raise HTTPException(status_code=422, detail=f"furnished_preference must be one of: {allowed}")
            prefs_data["furnished_preference"] = resolved_furnished_preference
            prefs_data["target_furnished"] = target_furnished_from_preference(resolved_furnished_preference)
        
        # Convert to DB format
        db_data = serialize_preferences(prefs_data)
        
        if existing:
            # Update existing preferences
            updated = await client.update(
                table="personal_preferences",
                id_value=user_id,
                data=db_data,
                id_column="user_id"
            )
        else:
            # Create new preferences
            db_data["user_id"] = user_id
            updated = await client.insert(
                table="personal_preferences",
                data=db_data
            )
        
        target_city = db_data.get("target_city")
        matching_result = {
            "status": "retired",
            "city": target_city,
            "message": "Legacy stable matching has been removed. Listing discovery uses direct ranked recommendations.",
        }
        
        # Convert back to API format
        formatted_prefs = deserialize_preferences(updated)
        
        response_data = {
            "status": "success",
            "message": "Preferences updated successfully",
            "data": formatted_prefs,
            "matching": matching_result  # Include matching results
        }
        
        return JSONResponse(content=make_json_serializable(response_data))
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"\n❌ ERROR in update_user_preferences:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to update preferences. Please try again."
        )


@router.get("/me")
async def get_my_preferences(
    token: str = Depends(require_user_token)
):
    """
    Get preferences for the currently authenticated user.
    
    Requires authentication. Extracts user_id from JWT token.
    """
    # TODO: Extract user_id from JWT token
    # For now, this is a placeholder endpoint
    raise HTTPException(
        status_code=501,
        detail="This endpoint requires JWT parsing to extract user_id. Use GET /{user_id} for now."
    )
