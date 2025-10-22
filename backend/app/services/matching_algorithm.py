"""
Matching Algorithm
Randomly matches users to available listings
"""

import random
from typing import List, Dict, Any, Optional
from datetime import datetime


def calculate_random_match_score(listing: Dict[str, Any], user_preferences: Optional[Dict[str, Any]] = None) -> int:
    """
    Calculate a random match score between 70-99 for a listing.
    This is a placeholder until real matching logic is implemented.
    
    Args:
        listing: The listing data
        user_preferences: User's preferences (not used in random matching)
    
    Returns:
        A random match score between 70 and 99
    """
    # Use listing ID as seed for consistent scores per listing
    listing_id = listing.get('id', '')
    if listing_id:
        # Create deterministic score based on listing ID
        hash_value = sum(ord(c) for c in str(listing_id))
        score = 70 + (hash_value % 30)  # Score between 70-99
    else:
        score = random.randint(70, 99)
    
    return score


def get_random_matches(
    listings: List[Dict[str, Any]], 
    user_preferences: Optional[Dict[str, Any]] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Get random listings with match scores.
    
    Args:
        listings: List of available listings
        user_preferences: User's preferences (not used in random matching)
        limit: Maximum number of matches to return
    
    Returns:
        List of listings with added match_score field, sorted by score
    """
    # Add match scores to each listing
    matches = []
    for listing in listings:
        listing_with_score = listing.copy()
        listing_with_score['match_score'] = calculate_random_match_score(listing, user_preferences)
        matches.append(listing_with_score)
    
    # Sort by match score (highest first)
    matches.sort(key=lambda x: x['match_score'], reverse=True)
    
    # Return limited results
    return matches[:limit]


def get_user_matches(
    user_id: str,
    all_listings: List[Dict[str, Any]],
    user_preferences: Optional[Dict[str, Any]] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get matches for a specific user.
    
    Args:
        user_id: The user's ID
        all_listings: All available listings
        user_preferences: User's housing and roommate preferences
        limit: Maximum number of matches
    
    Returns:
        Dictionary with matches and metadata
    """
    # For now, just filter out inactive listings if status field exists
    active_listings = [
        listing for listing in all_listings 
        if listing.get('status', 'active') == 'active'
    ]
    
    # Get matches
    matches = get_random_matches(active_listings, user_preferences, limit)
    
    return {
        "user_id": user_id,
        "total_matches": len(matches),
        "matches": matches,
        "generated_at": datetime.utcnow().isoformat(),
        "algorithm_version": "random_v1"
    }


# TODO: Future implementation with real matching logic
"""
Future matching criteria to implement:

1. Hard Constraints (Must Match):
   - lease_type
   - move_in_date (within range)
   - bedrooms (min/max)
   - pets_allowed
   - smoking_allowed
   - parking_required
   - accessibility_required

2. Soft Preferences (Weighted Score):
   - Amenities (laundry, dishwasher, AC, etc.)
   - Budget fit
   - Location preferences
   - Furnished preference

3. Roommate Compatibility (if applicable):
   - Age range
   - Lifestyle preferences
   - Social compatibility
   - Pet compatibility
   - Dietary preferences

4. Score Calculation:
   score = (hard_constraints_met * 100) + 
           (soft_preferences_score * weight) +
           (roommate_compatibility_score * weight)
"""

