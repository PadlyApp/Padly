"""
Generate Field Reference
Connects to Supabase and generates a comprehensive field reference for listings and groups.
"""

import asyncio
import json
from typing import Dict, Any, List
from app.services.supabase_client import SupabaseHTTPClient


async def get_table_schema(client: SupabaseHTTPClient, table_name: str) -> List[Dict[str, Any]]:
    """
    Get schema information for a table by fetching one record.
    """
    try:
        response = await client.select(table_name, "*", limit=1)
        if response and len(response) > 0:
            return response[0]
        return {}
    except Exception as e:
        print(f"Error fetching {table_name}: {e}")
        return {}


async def get_sample_data(client: SupabaseHTTPClient, table_name: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Get sample data from a table.
    """
    try:
        response = await client.select(table_name, "*", limit=limit)
        return response if response else []
    except Exception as e:
        print(f"Error fetching sample data from {table_name}: {e}")
        return []


def format_value(value: Any) -> str:
    """
    Format a value for display.
    """
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        if len(value) > 50:
            return f'"{value[:47]}..."'
        return f'"{value}"'
    elif isinstance(value, dict):
        return json.dumps(value, indent=2)
    elif isinstance(value, list):
        return json.dumps(value)
    else:
        return str(value)


def get_field_type(value: Any) -> str:
    """
    Determine the type of a field value.
    """
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "numeric/float"
    elif isinstance(value, str):
        # Check if it looks like a UUID
        if len(value) == 36 and value.count('-') == 4:
            return "uuid"
        # Check if it looks like a date
        if 'T' in value or '-' in value[:10]:
            return "timestamp/date"
        return "text"
    elif isinstance(value, dict):
        return "jsonb"
    elif isinstance(value, list):
        return "array"
    else:
        return type(value).__name__


async def generate_field_reference():
    """
    Generate a comprehensive field reference for listings and groups.
    """
    client = SupabaseHTTPClient()
    
    output = []
    output.append("=" * 80)
    output.append("PADLY DATABASE FIELD REFERENCE")
    output.append("Generated: 2025-11-11")
    output.append("=" * 80)
    output.append("")
    
    # ==================== LISTINGS ====================
    output.append("=" * 80)
    output.append("TABLE: LISTINGS")
    output.append("=" * 80)
    output.append("")
    
    # Get listing schema and samples
    listings = await get_sample_data(client, "listings", limit=1)
    
    if listings:
        listing = listings[0]
        
        output.append("FIELD STRUCTURE:")
        output.append("-" * 80)
        output.append(f"{'Field Name':<30} {'Type':<20} {'Example Value'}")
        output.append("-" * 80)
        
        for field_name, value in sorted(listing.items()):
            field_type = get_field_type(value)
            example = format_value(value)
            
            # Handle long examples
            if len(example) > 50:
                output.append(f"{field_name:<30} {field_type:<20}")
                for line in example.split('\n'):
                    output.append(f"{'':<30} {'':<20} {line}")
            else:
                output.append(f"{field_name:<30} {field_type:<20} {example}")
        
        output.append("-" * 80)
        output.append("")
        
        # Full JSON Example
        output.append("FULL JSON EXAMPLE:")
        output.append("-" * 80)
        output.append(json.dumps(listing, indent=2, default=str))
        output.append("")
    else:
        output.append("⚠️  No listings found in database")
        output.append("")
    
    # ==================== ROOMMATE GROUPS ====================
    output.append("")
    output.append("=" * 80)
    output.append("TABLE: ROOMMATE_GROUPS")
    output.append("=" * 80)
    output.append("")
    
    # Get groups with members
    groups = await client.select(
        "roommate_groups",
        "*,group_members(*)",
        limit=1
    )
    
    if groups:
        group = groups[0]
        
        output.append("FIELD STRUCTURE:")
        output.append("-" * 80)
        output.append(f"{'Field Name':<30} {'Type':<20} {'Example Value'}")
        output.append("-" * 80)
        
        for field_name, value in sorted(group.items()):
            field_type = get_field_type(value)
            example = format_value(value)
            
            # Handle long examples
            if len(example) > 50:
                output.append(f"{field_name:<30} {field_type:<20}")
                for line in example.split('\n'):
                    output.append(f"{'':<30} {'':<20} {line}")
            else:
                output.append(f"{field_name:<30} {field_type:<20} {example}")
        
        output.append("-" * 80)
        output.append("")
        
        # Full JSON Example
        output.append("FULL JSON EXAMPLE:")
        output.append("-" * 80)
        output.append(json.dumps(group, indent=2, default=str))
        output.append("")
    else:
        output.append("⚠️  No roommate groups found in database")
        output.append("")
    
    # ==================== GROUP MEMBERS ====================
    output.append("")
    output.append("=" * 80)
    output.append("TABLE: GROUP_MEMBERS")
    output.append("=" * 80)
    output.append("")
    
    members = await get_sample_data(client, "group_members", limit=1)
    
    if members:
        member = members[0]
        
        output.append("FIELD STRUCTURE:")
        output.append("-" * 80)
        output.append(f"{'Field Name':<30} {'Type':<20} {'Example Value'}")
        output.append("-" * 80)
        
        for field_name, value in sorted(member.items()):
            field_type = get_field_type(value)
            example = format_value(value)
            output.append(f"{field_name:<30} {field_type:<20} {example}")
        
        output.append("-" * 80)
        output.append("")
        
        output.append("FULL JSON EXAMPLE:")
        output.append("-" * 80)
        output.append(json.dumps(member, indent=2, default=str))
        output.append("")
    else:
        output.append("⚠️  No group members found in database")
        output.append("")
    
    # ==================== USERS (sample) ====================
    output.append("")
    output.append("=" * 80)
    output.append("TABLE: USERS (Sample)")
    output.append("=" * 80)
    output.append("")
    
    users = await get_sample_data(client, "users", limit=1)
    
    if users:
        user = users[0]
        
        output.append("FIELD STRUCTURE:")
        output.append("-" * 80)
        output.append(f"{'Field Name':<30} {'Type':<20} {'Example Value'}")
        output.append("-" * 80)
        
        for field_name, value in sorted(user.items()):
            field_type = get_field_type(value)
            example = format_value(value)
            output.append(f"{field_name:<30} {field_type:<20} {example}")
        
        output.append("-" * 80)
        output.append("")
    
    # ==================== PERSONAL PREFERENCES ====================
    output.append("")
    output.append("=" * 80)
    output.append("TABLE: PERSONAL_PREFERENCES")
    output.append("=" * 80)
    output.append("")
    
    prefs = await get_sample_data(client, "personal_preferences", limit=1)
    
    if prefs:
        pref = prefs[0]
        
        output.append("FIELD STRUCTURE:")
        output.append("-" * 80)
        output.append(f"{'Field Name':<30} {'Type':<20} {'Example Value'}")
        output.append("-" * 80)
        
        for field_name, value in sorted(pref.items()):
            field_type = get_field_type(value)
            example = format_value(value)
            
            if len(example) > 50:
                output.append(f"{field_name:<30} {field_type:<20}")
                for line in example.split('\n'):
                    output.append(f"{'':<30} {'':<20} {line}")
            else:
                output.append(f"{field_name:<30} {field_type:<20} {example}")
        
        output.append("-" * 80)
        output.append("")
        
        output.append("FULL JSON EXAMPLE:")
        output.append("-" * 80)
        output.append(json.dumps(pref, indent=2, default=str))
        output.append("")
    else:
        output.append("⚠️  No personal preferences found in database")
        output.append("")
    
    # ==================== SUMMARY ====================
    output.append("")
    output.append("=" * 80)
    output.append("SUMMARY")
    output.append("=" * 80)
    output.append("")
    
    # Count records
    listing_count = len(await client.select("listings", "id"))
    group_count = len(await client.select("roommate_groups", "id"))
    user_count = len(await client.select("users", "id"))
    member_count = len(await client.select("group_members", "group_id"))
    
    output.append(f"Total Listings: {listing_count}")
    output.append(f"Total Roommate Groups: {group_count}")
    output.append(f"Total Users: {user_count}")
    output.append(f"Total Group Members: {member_count}")
    output.append("")
    
    # Write to file
    output_text = "\n".join(output)
    
    with open("DATABASE_FIELD_REFERENCE.txt", "w") as f:
        f.write(output_text)
    
    print(output_text)
    print("\n" + "=" * 80)
    print("✅ Field reference saved to: DATABASE_FIELD_REFERENCE.txt")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(generate_field_reference())
