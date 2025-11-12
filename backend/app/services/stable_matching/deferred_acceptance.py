"""
Phase 4: Deferred Acceptance Algorithm Implementation

This module implements the Gale-Shapley Deferred Acceptance algorithm
for stable matching between groups and listings.

Algorithm Overview:
- Groups-proposing orientation (groups make offers to listings)
- Listings hold the best offer and reject worse ones
- Continues until all groups are matched or exhaust preference lists
- Guarantees stable matching (no blocking pairs)

Author: Padly Matching Team
Version: 0.4.0
"""

from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a stable matching round"""
    group_id: str
    listing_id: str
    group_score: float  # How much group likes listing (0-1000)
    listing_score: float  # How much listing likes group (0-1000)
    group_rank: int  # Rank of listing in group's preference (1 = top choice)
    listing_rank: int  # Rank of group in listing's preference (1 = top choice)
    matched_at: datetime
    is_stable: bool
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'group_id': self.group_id,
            'listing_id': self.listing_id,
            'group_score': round(self.group_score, 2),
            'listing_score': round(self.listing_score, 2),
            'group_rank': self.group_rank,
            'listing_rank': self.listing_rank,
            'matched_at': self.matched_at.isoformat(),
            'is_stable': self.is_stable
        }


@dataclass
class DiagnosticMetrics:
    """Metrics for a matching round"""
    city: str
    date_window_start: str
    date_window_end: str
    total_groups: int
    total_listings: int
    feasible_pairs: int
    matched_groups: int
    matched_listings: int
    unmatched_groups: int
    unmatched_listings: int
    proposals_sent: int
    proposals_rejected: int
    iterations: int
    avg_group_rank: float  # Average rank of matched listing for groups
    avg_listing_rank: float  # Average rank of matched group for listings
    match_quality_score: float  # Overall quality (0-100)
    is_stable: bool
    stability_check_passed: bool
    executed_at: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'city': self.city,
            'date_window_start': self.date_window_start,
            'date_window_end': self.date_window_end,
            'total_groups': self.total_groups,
            'total_listings': self.total_listings,
            'feasible_pairs': self.feasible_pairs,
            'matched_groups': self.matched_groups,
            'matched_listings': self.matched_listings,
            'unmatched_groups': self.unmatched_groups,
            'unmatched_listings': self.unmatched_listings,
            'proposals_sent': self.proposals_sent,
            'proposals_rejected': self.proposals_rejected,
            'iterations': self.iterations,
            'avg_group_rank': round(self.avg_group_rank, 2),
            'avg_listing_rank': round(self.avg_listing_rank, 2),
            'match_quality_score': round(self.match_quality_score, 2),
            'is_stable': self.is_stable,
            'stability_check_passed': self.stability_check_passed,
            'executed_at': self.executed_at.isoformat()
        }


class DeferredAcceptanceEngine:
    """
    Implements the Gale-Shapley Deferred Acceptance algorithm
    
    The algorithm works as follows:
    1. Each free group proposes to its most-preferred listing not yet proposed to
    2. Each listing reviews all proposals and tentatively accepts the best one
    3. Rejected groups become free again
    4. Repeat until no free group wants to propose
    
    Properties:
    - Group-optimal: Best stable matching for groups
    - Listing-pessimal: Worst stable matching for listings (but still stable)
    - Always terminates in O(n²) time
    - Produces stable matching (no blocking pairs)
    """
    
    def __init__(self, preference_lists: Dict):
        """
        Initialize the DA engine with preference lists
        
        Args:
            preference_lists: Dict with keys:
                - 'group_preferences': Dict[group_id, List[Tuple(listing_id, score, rank)]]
                - 'listing_preferences': Dict[listing_id, List[Tuple(group_id, score, rank)]]
                - 'metadata': Dict with groups, listings, city, date_window info
        """
        self.group_prefs = preference_lists.get('group_preferences', {})
        self.listing_prefs = preference_lists.get('listing_preferences', {})
        self.metadata = preference_lists.get('metadata', {})
        
        # State tracking
        self.free_groups: Set[str] = set(self.group_prefs.keys())
        self.current_matches: Dict[str, str] = {}  # listing_id -> group_id
        self.group_current_match: Dict[str, str] = {}  # group_id -> listing_id
        self.next_proposal_index: Dict[str, int] = {g: 0 for g in self.group_prefs.keys()}
        
        # Metrics tracking
        self.proposals_sent = 0
        self.proposals_rejected = 0
        self.iterations = 0
        
        logger.info(f"Initialized DA engine with {len(self.group_prefs)} groups and {len(self.listing_prefs)} listings")
    
    def run(self) -> Tuple[List[MatchResult], DiagnosticMetrics]:
        """
        Execute the Deferred Acceptance algorithm
        
        Returns:
            Tuple of (matches, diagnostics)
        """
        logger.info("Starting Deferred Acceptance algorithm...")
        start_time = datetime.now()
        
        # Main DA loop
        while self.free_groups:
            self.iterations += 1
            if self.iterations > 10000:  # Safety limit
                logger.error("DA algorithm exceeded iteration limit!")
                break
            
            # Get a free group
            group_id = next(iter(self.free_groups))
            
            # Get next listing to propose to
            next_listing = self._get_next_proposal(group_id)
            
            if next_listing is None:
                # Group has exhausted preference list
                self.free_groups.remove(group_id)
                logger.debug(f"Group {group_id} exhausted preference list")
                continue
            
            # Group proposes to listing
            self._propose(group_id, next_listing)
        
        # Generate results
        matches = self._generate_matches()
        diagnostics = self._generate_diagnostics()
        
        # Verify stability
        is_stable = self._verify_stability(matches)
        diagnostics.is_stable = is_stable
        diagnostics.stability_check_passed = is_stable
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"DA algorithm completed in {elapsed:.2f}s: {len(matches)} matches, {self.iterations} iterations")
        
        return matches, diagnostics
    
    def _get_next_proposal(self, group_id: str) -> Optional[str]:
        """Get the next listing for group to propose to"""
        pref_list = self.group_prefs.get(group_id, [])
        next_idx = self.next_proposal_index[group_id]
        
        if next_idx >= len(pref_list):
            return None  # Exhausted preference list
        
        listing_id = pref_list[next_idx][0]  # (listing_id, rank, score)
        self.next_proposal_index[group_id] += 1
        
        return listing_id
    
    def _propose(self, group_id: str, listing_id: str):
        """
        Group proposes to listing
        
        Listing will:
        - Accept if currently unmatched
        - Accept if group is better than current match
        - Reject otherwise
        """
        self.proposals_sent += 1
        
        current_match = self.current_matches.get(listing_id)
        
        if current_match is None:
            # Listing is free, accept proposal
            self._accept_proposal(group_id, listing_id)
            logger.debug(f"Listing {listing_id} accepted free proposal from group {group_id}")
        else:
            # Listing has current match, compare
            if self._prefers(listing_id, group_id, current_match):
                # Listing prefers new group, reject old match
                self._reject_proposal(current_match)
                self._accept_proposal(group_id, listing_id)
                logger.debug(f"Listing {listing_id} upgraded from group {current_match} to {group_id}")
            else:
                # Listing prefers current match, reject new group
                self._reject_proposal(group_id)
                logger.debug(f"Listing {listing_id} rejected group {group_id}, keeping {current_match}")
    
    def _prefers(self, listing_id: str, group_a: str, group_b: str) -> bool:
        """
        Does listing prefer group_a over group_b?
        
        Preference is determined by rank (lower is better)
        """
        pref_list = self.listing_prefs.get(listing_id, [])
        
        # Build rank lookup
        # Format: (group_id, rank, score)
        ranks = {g_id: rank for g_id, rank, score in pref_list}
        
        rank_a = ranks.get(group_a, float('inf'))
        rank_b = ranks.get(group_b, float('inf'))
        
        return rank_a < rank_b
    
    def _accept_proposal(self, group_id: str, listing_id: str):
        """Accept a proposal (tentatively)"""
        self.current_matches[listing_id] = group_id
        self.group_current_match[group_id] = listing_id
        self.free_groups.discard(group_id)
    
    def _reject_proposal(self, group_id: str):
        """Reject a proposal"""
        self.proposals_rejected += 1
        self.group_current_match.pop(group_id, None)
        self.free_groups.add(group_id)
    
    def _generate_matches(self) -> List[MatchResult]:
        """Generate match results from final matching"""
        matches = []
        matched_at = datetime.now()
        
        for listing_id, group_id in self.current_matches.items():
            # Get scores and ranks
            group_pref = self.group_prefs.get(group_id, [])
            listing_pref = self.listing_prefs.get(listing_id, [])
            
            # Find scores and ranks for this match
            # Note: preference list format is (id, rank, score)
            group_score = 0.0
            group_rank = 0
            for l_id, rank, score in group_pref:
                if l_id == listing_id:
                    group_score = score
                    group_rank = rank
                    break
            
            listing_score = 0.0
            listing_rank = 0
            for g_id, rank, score in listing_pref:
                if g_id == group_id:
                    listing_score = score
                    listing_rank = rank
                    break
            
            match = MatchResult(
                group_id=group_id,
                listing_id=listing_id,
                group_score=group_score,
                listing_score=listing_score,
                group_rank=group_rank,
                listing_rank=listing_rank,
                matched_at=matched_at,
                is_stable=True  # Will verify later
            )
            matches.append(match)
        
        return matches
    
    def _generate_diagnostics(self) -> DiagnosticMetrics:
        """Generate diagnostic metrics for this matching round"""
        metadata = self.metadata
        
        num_groups = len(self.group_prefs)
        num_listings = len(self.listing_prefs)
        num_matches = len(self.current_matches)
        
        # Calculate average ranks
        avg_group_rank = 0.0
        avg_listing_rank = 0.0
        
        if num_matches > 0:
            group_ranks = []
            listing_ranks = []
            
            for listing_id, group_id in self.current_matches.items():
                # Get group's rank for this listing
                group_pref = self.group_prefs.get(group_id, [])
                for l_id, score, rank in group_pref:
                    if l_id == listing_id:
                        group_ranks.append(rank)
                        break
                
                # Get listing's rank for this group
                listing_pref = self.listing_prefs.get(listing_id, [])
                for g_id, score, rank in listing_pref:
                    if g_id == group_id:
                        listing_ranks.append(rank)
                        break
            
            if group_ranks:
                avg_group_rank = sum(group_ranks) / len(group_ranks)
            if listing_ranks:
                avg_listing_rank = sum(listing_ranks) / len(listing_ranks)
        
        # Calculate match quality score (0-100)
        # Based on: match rate (50%), average ranks (50%)
        match_rate = num_matches / max(num_groups, 1)
        max_possible_rank = max(num_listings, num_groups)
        
        group_rank_quality = 1.0 - (avg_group_rank / max_possible_rank) if max_possible_rank > 0 else 0.0
        listing_rank_quality = 1.0 - (avg_listing_rank / max_possible_rank) if max_possible_rank > 0 else 0.0
        rank_quality = (group_rank_quality + listing_rank_quality) / 2
        
        quality_score = (match_rate * 50) + (rank_quality * 50)
        
        diagnostics = DiagnosticMetrics(
            city=metadata.get('city', 'unknown'),
            date_window_start=metadata.get('date_window_start', ''),
            date_window_end=metadata.get('date_window_end', ''),
            total_groups=num_groups,
            total_listings=num_listings,
            feasible_pairs=metadata.get('feasible_pairs', 0),
            matched_groups=num_matches,
            matched_listings=num_matches,
            unmatched_groups=num_groups - num_matches,
            unmatched_listings=num_listings - num_matches,
            proposals_sent=self.proposals_sent,
            proposals_rejected=self.proposals_rejected,
            iterations=self.iterations,
            avg_group_rank=avg_group_rank,
            avg_listing_rank=avg_listing_rank,
            match_quality_score=quality_score,
            is_stable=False,  # Will be set after verification
            stability_check_passed=False,
            executed_at=datetime.now()
        )
        
        return diagnostics
    
    def _verify_stability(self, matches: List[MatchResult]) -> bool:
        """
        Verify that the matching is stable (no blocking pairs)
        
        A blocking pair exists if:
        - Group g is matched to listing l1
        - Listing l2 is matched to group g2 (or unmatched)
        - Group g prefers l2 over l1
        - Listing l2 prefers g over g2 (or is unmatched)
        
        Returns:
            True if stable (no blocking pairs found)
        """
        if not matches:
            return True  # Empty matching is trivially stable
        
        # Build matching dictionaries
        group_to_listing = {m.group_id: m.listing_id for m in matches}
        listing_to_group = {m.listing_id: m.group_id for m in matches}
        
        # Check all possible blocking pairs
        for group_id, group_prefs in self.group_prefs.items():
            current_listing = group_to_listing.get(group_id)
            
            if current_listing is None:
                # Unmatched group - check if any listing prefers it to current match
                for listing_id, group_score, group_rank in group_prefs:
                    current_group = listing_to_group.get(listing_id)
                    if current_group is None:
                        # Both unmatched - not a blocking pair (would have matched)
                        continue
                    
                    # Would listing prefer this unmatched group?
                    if self._prefers(listing_id, group_id, current_group):
                        logger.warning(f"Found blocking pair: unmatched group {group_id} + listing {listing_id}")
                        return False
            else:
                # Matched group - check if prefers other listings
                current_rank = None
                for l_id, score, rank in group_prefs:
                    if l_id == current_listing:
                        current_rank = rank
                        break
                
                # Check all listings group prefers over current
                for listing_id, group_score, group_rank in group_prefs:
                    if group_rank >= current_rank:
                        break  # No more preferred listings
                    
                    # Group prefers this listing - does listing prefer group?
                    current_group = listing_to_group.get(listing_id)
                    
                    if current_group is None:
                        # Listing is unmatched and group prefers it - blocking pair!
                        logger.warning(f"Found blocking pair: group {group_id} + unmatched listing {listing_id}")
                        return False
                    
                    if self._prefers(listing_id, group_id, current_group):
                        # Both prefer each other over current matches - blocking pair!
                        logger.warning(f"Found blocking pair: group {group_id} + listing {listing_id}")
                        return False
        
        logger.info("Stability verification passed - no blocking pairs found")
        return True


def run_deferred_acceptance(preference_lists: Dict) -> Tuple[List[MatchResult], DiagnosticMetrics]:
    """
    Main entry point for running the Deferred Acceptance algorithm
    
    Args:
        preference_lists: Output from Phase 3 (scoring.build_preference_lists)
    
    Returns:
        Tuple of (matches, diagnostics)
    """
    engine = DeferredAcceptanceEngine(preference_lists)
    matches, diagnostics = engine.run()
    
    logger.info(f"Matching complete: {len(matches)} stable matches created")
    return matches, diagnostics


# Export public API
__all__ = [
    'DeferredAcceptanceEngine',
    'MatchResult',
    'DiagnosticMetrics',
    'run_deferred_acceptance'
]
