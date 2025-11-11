"""
Data Parser Service
Fetches and parses listings and groups from Supabase for use in matching algorithms.
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, date
from app.services.supabase_client import SupabaseHTTPClient


def serialize_value(value: Any) -> Any:
    """
    Serialize values for JSON compatibility.
    
    Args:
        value: The value to serialize
        
    Returns:
        JSON-compatible value
    """
    if isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_value(item) for item in value]
    else:
        return value


def parse_listing(raw_listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a raw listing from Supabase into a clean format for algorithms.
    
    Args:
        raw_listing: Raw listing data from Supabase
        
    Returns:
        Parsed listing dictionary with serialized values
    """
    parsed = {
        'id': raw_listing.get('id'),
        'host_user_id': raw_listing.get('host_user_id'),
        'status': raw_listing.get('status'),
        'title': raw_listing.get('title'),
        'description': raw_listing.get('description'),
        'property_type': raw_listing.get('property_type'),
        'lease_type': raw_listing.get('lease_type'),
        'lease_duration_months': raw_listing.get('lease_duration_months'),
        'number_of_bedrooms': raw_listing.get('number_of_bedrooms'),
        'number_of_bathrooms': serialize_value(raw_listing.get('number_of_bathrooms')),
        'area_sqft': raw_listing.get('area_sqft'),
        'furnished': raw_listing.get('furnished', False),
        'price_per_month': serialize_value(raw_listing.get('price_per_month')),
        'utilities_included': raw_listing.get('utilities_included', False),
        'deposit_amount': serialize_value(raw_listing.get('deposit_amount')),
        'address_line_1': raw_listing.get('address_line_1'),
        'address_line_2': raw_listing.get('address_line_2'),
        'city': raw_listing.get('city'),
        'state_province': raw_listing.get('state_province'),
        'postal_code': raw_listing.get('postal_code'),
        'country': raw_listing.get('country', 'USA'),
        'latitude': serialize_value(raw_listing.get('latitude')),
        'longitude': serialize_value(raw_listing.get('longitude')),
        'available_from': serialize_value(raw_listing.get('available_from')),
        'available_to': serialize_value(raw_listing.get('available_to')),
        'amenities': raw_listing.get('amenities', {}),
        'house_rules': raw_listing.get('house_rules'),
        'shared_spaces': raw_listing.get('shared_spaces', []),
        'view_count': raw_listing.get('view_count', 0),
        'created_at': serialize_value(raw_listing.get('created_at')),
        'updated_at': serialize_value(raw_listing.get('updated_at'))
    }
    
    return parsed


def parse_group(raw_group: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a raw roommate group from Supabase into a clean format for algorithms.
    
    Args:
        raw_group: Raw group data from Supabase
        
    Returns:
        Parsed group dictionary with serialized values
    """
    # Parse house rules from comma-separated string to array
    house_rules_str = raw_group.get('target_house_rules')
    house_rules_array = []
    if house_rules_str and isinstance(house_rules_str, str):
        # Split by comma and strip whitespace from each rule
        house_rules_array = [rule.strip() for rule in house_rules_str.split(',') if rule.strip()]
    elif isinstance(house_rules_str, list):
        # Already an array
        house_rules_array = house_rules_str
    
    parsed = {
        'id': raw_group.get('id'),
        'creator_user_id': raw_group.get('creator_user_id'),
        'status': raw_group.get('status'),
        'group_name': raw_group.get('group_name'),
        'description': raw_group.get('description'),
        
        # Location preferences
        'target_city': raw_group.get('target_city'),
        'target_state_province': raw_group.get('target_state_province'),
        'target_country': raw_group.get('target_country'),
        
        # Budget preferences
        'budget_per_person_min': serialize_value(raw_group.get('budget_per_person_min')),
        'budget_per_person_max': serialize_value(raw_group.get('budget_per_person_max')),
        
        # Move-in and lease preferences
        'target_move_in_date': serialize_value(raw_group.get('target_move_in_date')),
        'target_lease_duration_months': raw_group.get('target_lease_duration_months'),
        'target_lease_type': raw_group.get('target_lease_type'),
        
        # Property requirements
        'target_bedrooms': raw_group.get('target_bedrooms'),
        'target_bathrooms': serialize_value(raw_group.get('target_bathrooms')),
        'target_furnished': raw_group.get('target_furnished'),
        'target_utilities_included': raw_group.get('target_utilities_included'),
        'target_deposit_amount': serialize_value(raw_group.get('target_deposit_amount')),
        
        # House rules (converted from comma-separated string to array)
        'target_house_rules': house_rules_array,
        
        # Group size
        'target_group_size': raw_group.get('target_group_size', 2),
        
        # Timestamps
        'created_at': serialize_value(raw_group.get('created_at')),
        'updated_at': serialize_value(raw_group.get('updated_at'))
    }
    
    return parsed


async def fetch_and_parse_listings(
    client: Optional[SupabaseHTTPClient] = None,
    status_filter: str = "active",
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch and parse all listings from Supabase.
    
    Args:
        client: Optional SupabaseHTTPClient instance (creates admin client if not provided)
        status_filter: Filter by listing status (default: "active")
        limit: Optional limit on number of results
        
    Returns:
        List of parsed listing dictionaries ready for algorithm processing
    """
    # Create admin client if not provided
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    # Build filters
    filters = {}
    if status_filter:
        filters["status"] = f"eq.{status_filter}"
    
    # Fetch listings from Supabase
    raw_listings = await client.select(
        table="listings",
        columns="*",
        filters=filters,
        order="created_at.desc",
        limit=limit
    )
    
    # Parse and return
    parsed_listings = [parse_listing(listing) for listing in raw_listings]
    return parsed_listings


async def fetch_and_parse_groups(
    client: Optional[SupabaseHTTPClient] = None,
    status_filter: str = "active",
    limit: Optional[int] = None,
    include_members: bool = False
) -> List[Dict[str, Any]]:
    """
    Fetch and parse all roommate groups from Supabase.
    
    Args:
        client: Optional SupabaseHTTPClient instance (creates admin client if not provided)
        status_filter: Filter by group status (default: "active")
        limit: Optional limit on number of results
        include_members: Whether to include group members data
        
    Returns:
        List of parsed group dictionaries ready for algorithm processing
    """
    # Create admin client if not provided
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    # Build filters
    filters = {}
    if status_filter:
        filters["status"] = f"eq.{status_filter}"
    
    # Fetch groups from Supabase
    raw_groups = await client.select(
        table="roommate_groups",
        columns="*",
        filters=filters,
        order="created_at.desc",
        limit=limit
    )
    
    # Parse groups
    parsed_groups = [parse_group(group) for group in raw_groups]
    
    # Optionally fetch members for each group
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
    """
    Fetch and parse all necessary data for matching algorithms.
    
    Returns:
        Dictionary containing:
            - 'listings': List of parsed active listings
            - 'groups': List of parsed active groups with member info
    """
    # Create admin client
    client = SupabaseHTTPClient(is_admin=True)
    
    # Fetch both datasets in parallel would be ideal, but we'll do sequentially for simplicity
    listings = await fetch_and_parse_listings(client=client, status_filter="active")
    groups = await fetch_and_parse_groups(client=client, status_filter="active", include_members=True)
    
    return {
        'listings': listings,
        'groups': groups
    }


async def fetch_user_preferences(
    user_id: str,
    client: Optional[SupabaseHTTPClient] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch and parse user preferences for matching.
    
    Args:
        user_id: User ID to fetch preferences for
        client: Optional SupabaseHTTPClient instance
        
    Returns:
        Parsed user preferences or None if not found
    """
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    prefs = await client.select_one(
        table="personal_preferences",
        id_value=user_id,
        id_column="user_id"
    )
    
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


async def fetch_roommate_post(
    user_id: str,
    client: Optional[SupabaseHTTPClient] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch user's active roommate post for matching.
    
    Args:
        user_id: User ID to fetch post for
        client: Optional SupabaseHTTPClient instance
        
    Returns:
        Parsed roommate post or None if not found
    """
    if client is None:
        client = SupabaseHTTPClient(is_admin=True)
    
    posts = await client.select(
        table="roommate_posts",
        columns="*",
        filters={
            "user_id": f"eq.{user_id}",
            "status": "eq.active"
        },
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
