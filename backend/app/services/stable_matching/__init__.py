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

from .feasible_pairs import (
    location_matches,
    date_matches,
    price_matches,
    hard_attributes_match,
    build_feasible_pairs,
    get_feasibility_statistics,
    analyze_rejection_reasons
)

from .scoring import (
    calculate_group_score,
    calculate_listing_score,
    rank_listings_for_group,
    rank_groups_for_listing,
    build_preference_lists,
    GROUP_SCORING_WEIGHTS,
    LISTING_SCORING_WEIGHTS
)

from .deferred_acceptance import (
    DeferredAcceptanceEngine,
    MatchResult,
    DiagnosticMetrics,
    run_deferred_acceptance
)

from .persistence import (
    MatchPersistenceEngine,
    save_matching_results,
    get_active_matches_for_group,
    get_active_matches_for_listing
)

__all__ = [
    # Filters
    'is_listing_pair_eligible',
    'is_group_eligible',
    'get_eligible_listings',
    'get_eligible_groups',
    'get_move_in_windows',
    'normalize_city_name',
    'validate_listing_data_quality',
    'validate_group_data_quality',
    'DateWindow',
    # Feasible Pairs
    'location_matches',
    'date_matches',
    'price_matches',
    'hard_attributes_match',
    'build_feasible_pairs',
    'get_feasibility_statistics',
    'analyze_rejection_reasons',
    # Scoring
    'calculate_group_score',
    'calculate_listing_score',
    'rank_listings_for_group',
    'rank_groups_for_listing',
    'build_preference_lists',
    'GROUP_SCORING_WEIGHTS',
    'LISTING_SCORING_WEIGHTS',
    # Deferred Acceptance (Phase 4)
    'DeferredAcceptanceEngine',
    'MatchResult',
    'DiagnosticMetrics',
    'run_deferred_acceptance',
    # Database Persistence (Phase 5)
    'MatchPersistenceEngine',
    'save_matching_results',
    'get_active_matches_for_group',
    'get_active_matches_for_listing'
]

__version__ = '0.5.0'
__algorithm__ = 'Deferred Acceptance (Gale-Shapley)'
