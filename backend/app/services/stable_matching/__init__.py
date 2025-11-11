"""
Stable Matching Algorithm Module
Implements Deferred Acceptance (Gale-Shapley) for matching 2-person groups to entire-unit listings.
"""

from .filters import (
    is_listing_pair_eligible,
    is_group_eligible,
    get_eligible_listings,
    get_eligible_groups,
    get_move_in_windows,
    normalize_city_name,
    validate_listing_data_quality,
    validate_group_data_quality,
    DateWindow
)

__all__ = [
    'is_listing_pair_eligible',
    'is_group_eligible',
    'get_eligible_listings',
    'get_eligible_groups',
    'get_move_in_windows',
    'normalize_city_name',
    'validate_listing_data_quality',
    'validate_group_data_quality',
    'DateWindow'
]

__version__ = '0.1.0'
__algorithm__ = 'Deferred Acceptance (Gale-Shapley)'
