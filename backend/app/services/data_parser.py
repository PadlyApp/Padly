"""
Data Parser Service
Fetches and parses listings/groups from Supabase for matching algorithms.
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, date
from app.services.supabase_client import SupabaseHTTPClient


def serialize_value(value: Any) -> Any:
    """Serialize values for JSON compatibility."""
    if isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_value(item) for item in value]
    return value


def parse_listing(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse raw listing into clean format for algorithms."""
    return {
        'id': raw.get('id'),
        'host_user_id': raw.get('host_user_id'),
        'status': raw.get('status'),
        'title': raw.get('title'),
        'description': raw.get('description'),
        'property_type': raw.get('property_type'),
        'lease_type': raw.get('lease_type'),
        'lease_duration_months': raw.get('lease_duration_months'),
        'number_of_bedrooms': raw.get('number_of_bedrooms'),
        'number_of_bathrooms': serialize_value(raw.get('number_of_bathrooms')),
        'area_sqft': raw.get('area_sqft'),
        'furnished': raw.get('furnished', False),
        'price_per_month': serialize_value(raw.get('price_per_month')),
        'price_per_room': serialize_value(raw.get('price_per_room')),
        'utilities_included': raw.get('utilities_included', False),
        'deposit_amount': serialize_value(raw.get('deposit_amount')),
        'address_line_1': raw.get('address_line_1'),
        'address_line_2': raw.get('address_line_2'),
        'city': raw.get('city'),
        'state_province': raw.get('state_province'),
        'postal_code': raw.get('postal_code'),
        'country': raw.get('country', 'USA'),
        'latitude': serialize_value(raw.get('latitude')),
        'longitude': serialize_value(raw.get('longitude')),
        'available_from': serialize_value(raw.get('available_from')),
        'available_to': serialize_value(raw.get('available_to')),
        'amenities': raw.get('amenities', {}),
        'house_rules': raw.get('house_rules'),
        'shared_spaces': raw.get('shared_spaces', []),
        'view_count': raw.get('view_count', 0),
        'created_at': serialize_value(raw.get('created_at')),
        'updated_at': serialize_value(raw.get('updated_at'))
    }


def parse_group(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse raw group into clean format for algorithms."""
    return {
        'id': raw.get('id'),
        'creator_user_id': raw.get('creator_user_id'),
        'status': raw.get('status'),
        'group_name': raw.get('group_name'),
        'description': raw.get('description'),
        'target_city': raw.get('target_city'),
        'budget_per_person_min': serialize_value(raw.get('budget_per_person_min')),
        'budget_per_person_max': serialize_value(raw.get('budget_per_person_max')),
        'target_move_in_date': serialize_value(raw.get('target_move_in_date')),
        'target_group_size': raw.get('target_group_size', 2),
        'created_at': serialize_value(raw.get('created_at')),
        'updated_at': serialize_value(raw.get('updated_at'))
    }


async def fetch_and_parse_listings(
    client: Optional[SupabaseHTTPClient] = None,
    status_filter: str = "active",
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Fetch and parse listings from Supabase."""
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    filters = {"status": f"eq.{status_filter}"} if status_filter else {}
    
    raw_listings = await client.select(
        table="listings",
        columns="*",
        filters=filters,
        order="created_at.desc",
        limit=limit
    )
    
    return [parse_listing(listing) for listing in raw_listings]


async def fetch_and_parse_groups(
    client: Optional[SupabaseHTTPClient] = None,
    status_filter: str = "active",
    limit: Optional[int] = None,
    include_members: bool = False
) -> List[Dict[str, Any]]:
    """Fetch and parse groups from Supabase."""
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    filters = {"status": f"eq.{status_filter}"} if status_filter else {}
    
    raw_groups = await client.select(
        table="roommate_groups",
        columns="*",
        filters=filters,
        order="created_at.desc",
        limit=limit
    )
    
    parsed_groups = [parse_group(group) for group in raw_groups]
    
    if include_members:
        for group in parsed_groups:
            members = await client.select(
                table="group_members",
                columns="*",
                filters={"group_id": f"eq.{group['id']}"}
            )
            group['members'] = [
                {
                    'user_id': m.get('user_id'),
                    'is_creator': m.get('is_creator', False),
                    'joined_at': serialize_value(m.get('joined_at'))
                }
                for m in members
            ]
            group['current_size'] = len(members)
    
    return parsed_groups


async def fetch_parsed_data_for_algorithms() -> Dict[str, List[Dict[str, Any]]]:
    """Fetch all data needed for matching algorithms."""
    client = SupabaseHTTPClient(is_admin=True)
    
    listings = await fetch_and_parse_listings(client=client, status_filter="active")
    groups = await fetch_and_parse_groups(client=client, status_filter="active", include_members=True)
    
    return {'listings': listings, 'groups': groups}


async def fetch_user_preferences(user_id: str, client: Optional[SupabaseHTTPClient] = None) -> Optional[Dict[str, Any]]:
    """Fetch user preferences for matching."""
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    prefs = await client.select_one(table="personal_preferences", id_value=user_id, id_column="user_id")
    
    if not prefs:
        return None
    
    return {
        'user_id': prefs.get('user_id'),
        'target_city': prefs.get('target_city'),
        'budget_min': serialize_value(prefs.get('budget_min')),
        'budget_max': serialize_value(prefs.get('budget_max')),
        'move_in_date': serialize_value(prefs.get('move_in_date')),
        'lifestyle_preferences': prefs.get('lifestyle_preferences', {}),
        'preferred_neighborhoods': prefs.get('preferred_neighborhoods', []),
        'updated_at': serialize_value(prefs.get('updated_at'))
    }


async def fetch_roommate_post(user_id: str, client: Optional[SupabaseHTTPClient] = None) -> Optional[Dict[str, Any]]:
    """Fetch user's active roommate post."""
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    posts = await client.select(
        table="roommate_posts",
        columns="*",
        filters={"user_id": f"eq.{user_id}", "status": "eq.active"},
        limit=1
    )
    
    if not posts:
        return None
    
    post = posts[0]
    return {
        'id': post.get('id'),
        'user_id': post.get('user_id'),
        'status': post.get('status'),
        'title': post.get('title'),
        'description': post.get('description'),
        'target_city': post.get('target_city'),
        'preferred_neighborhoods': post.get('preferred_neighborhoods', []),
        'budget_min': serialize_value(post.get('budget_min')),
        'budget_max': serialize_value(post.get('budget_max')),
        'move_in_date': serialize_value(post.get('move_in_date')),
        'lease_duration_months': post.get('lease_duration_months'),
        'looking_for_property_type': post.get('looking_for_property_type'),
        'looking_for_roommates': post.get('looking_for_roommates', True),
        'preferred_roommate_count': post.get('preferred_roommate_count'),
        'created_at': serialize_value(post.get('created_at')),
        'updated_at': serialize_value(post.get('updated_at'))
    }
