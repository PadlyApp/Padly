"""
Personal Preferences routes
Manage user housing and roommate preferences
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Any
from datetime import date, datetime
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.models import (
    PersonalPreferencesUpdate, 
    PersonalPreferencesResponse,
    HousingPreferences,
    RoommatePreferences
)
import json

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


def serialize_preferences(prefs_data: dict) -> dict:
    """Convert nested preference objects to proper format for storage"""
    if not prefs_data:
        return prefs_data
    
    # Convert all dates to strings first
    prefs_data = convert_dates_to_strings(prefs_data)
    
    # Build the lifestyle_preferences JSONB field
    lifestyle_prefs = {}
    
    # Extract housing preferences
    if "housing_preferences" in prefs_data and prefs_data["housing_preferences"]:
        housing = prefs_data["housing_preferences"]
        lifestyle_prefs["housing"] = housing
    
    # Extract roommate preferences
    if "roommate_preferences" in prefs_data and prefs_data["roommate_preferences"]:
        roommate = prefs_data["roommate_preferences"]
        lifestyle_prefs["roommate"] = roommate
    
    # Merge legacy lifestyle_preferences if present
    if "lifestyle_preferences" in prefs_data and prefs_data["lifestyle_preferences"]:
        lifestyle_prefs.update(prefs_data["lifestyle_preferences"])
    
    # Build final data structure for DB
    db_data = {
        "target_city": prefs_data.get("target_city"),
        "budget_min": prefs_data.get("budget_min"),
        "budget_max": prefs_data.get("budget_max"),
        # preferred_neighborhoods removed - not used
        "lifestyle_preferences": lifestyle_prefs if lifestyle_prefs else None
    }
    
    # Handle move_in_date from housing_preferences
    if "housing_preferences" in prefs_data and prefs_data["housing_preferences"]:
        if "move_in_date" in prefs_data["housing_preferences"]:
            db_data["move_in_date"] = prefs_data["housing_preferences"]["move_in_date"]
    
    # Remove None values
    return {k: v for k, v in db_data.items() if v is not None}


def deserialize_preferences(db_data: dict) -> dict:
    """Convert DB format to API response format"""
    if not db_data:
        return db_data
    
    result = {
        "user_id": db_data.get("user_id"),
        "target_city": db_data.get("target_city"),
        "budget_min": db_data.get("budget_min"),
        "budget_max": db_data.get("budget_max"),
        # preferred_neighborhoods removed - not used
        "updated_at": db_data.get("updated_at")
    }
    
    # Extract nested preferences from lifestyle_preferences JSONB
    lifestyle_prefs = db_data.get("lifestyle_preferences", {})
    if lifestyle_prefs:
        result["housing_preferences"] = lifestyle_prefs.get("housing")
        result["roommate_preferences"] = lifestyle_prefs.get("roommate")
        
        # Keep other legacy fields
        legacy_fields = {k: v for k, v in lifestyle_prefs.items() 
                        if k not in ["housing", "roommate"]}
        if legacy_fields:
            result["lifestyle_preferences"] = legacy_fields
    
    # Move move_in_date to housing_preferences if it exists
    if db_data.get("move_in_date"):
        if not result.get("housing_preferences"):
            result["housing_preferences"] = {}
        result["housing_preferences"]["move_in_date"] = db_data.get("move_in_date")
    
    return result


@router.get("/{user_id}")
async def get_user_preferences(
    user_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get personal preferences for a user.
    
    Returns housing and roommate preferences used for matching algorithm.
    """
    client = SupabaseHTTPClient(token=token)
    
    prefs = await client.select_one(
        table="personal_preferences",
        id_value=user_id,
        id_column="user_id"
    )
    
    if not prefs:
        # Return empty preferences if not set yet
        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "housing_preferences": None,
                "roommate_preferences": None
            }
        }
    
    # Convert DB format to API format
    formatted_prefs = deserialize_preferences(prefs)
    
    return {
        "status": "success",
        "data": formatted_prefs
    }


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
    """
    client = SupabaseHTTPClient(token=token)
    
    # Convert Pydantic model to dict
    prefs_data = preferences.model_dump(exclude_none=True)
    
    if not prefs_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    # Convert to DB format
    db_data = serialize_preferences(prefs_data)
    
    # Check if preferences exist
    existing = await client.select_one(
        table="personal_preferences",
        id_value=user_id,
        id_column="user_id"
    )
    
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
    
    # Convert back to API format
    formatted_prefs = deserialize_preferences(updated)
    
    return {
        "status": "success",
        "message": "Preferences updated successfully",
        "data": formatted_prefs
    }


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

