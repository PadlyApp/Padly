"""
Gale-Shapley Deferred Acceptance Algorithm for stable matching.
Groups propose to listings, listings hold best offer. Guarantees stable matching.
"""

from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a stable matching."""
    group_id: str
    listing_id: str
    group_score: float
    listing_score: float
    group_rank: int
    listing_rank: int
    matched_at: datetime
    is_stable: bool
    
    def to_dict(self) -> Dict:
        return {
            'group_id': self.group_id, 'listing_id': self.listing_id,
            'group_score': round(self.group_score, 2), 'listing_score': round(self.listing_score, 2),
            'group_rank': self.group_rank, 'listing_rank': self.listing_rank,
            'matched_at': self.matched_at.isoformat(), 'is_stable': self.is_stable
        }


@dataclass
class DiagnosticMetrics:
    """Metrics for a matching round."""
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
    avg_group_rank: float
    avg_listing_rank: float
    match_quality_score: float
    is_stable: bool
    stability_check_passed: bool
    executed_at: datetime
    
    def to_dict(self) -> Dict:
        return {
            'city': self.city, 'date_window_start': self.date_window_start,
            'date_window_end': self.date_window_end, 'total_groups': self.total_groups,
            'total_listings': self.total_listings, 'feasible_pairs': self.feasible_pairs,
            'matched_groups': self.matched_groups, 'matched_listings': self.matched_listings,
            'unmatched_groups': self.unmatched_groups, 'unmatched_listings': self.unmatched_listings,
            'proposals_sent': self.proposals_sent, 'proposals_rejected': self.proposals_rejected,
            'iterations': self.iterations, 'avg_group_rank': round(self.avg_group_rank, 2),
            'avg_listing_rank': round(self.avg_listing_rank, 2),
            'match_quality_score': round(self.match_quality_score, 2),
            'is_stable': self.is_stable, 'stability_check_passed': self.stability_check_passed,
            'executed_at': self.executed_at.isoformat()
        }


class DeferredAcceptanceEngine:
    """Gale-Shapley algorithm: groups propose, listings hold best. O(n²) time, stable output."""
    
    def __init__(self, preference_lists: Dict):
        self.group_prefs = preference_lists.get('group_preferences', {})
        self.listing_prefs = preference_lists.get('listing_preferences', {})
        self.metadata = preference_lists.get('metadata', {})
        
        # State tracking
        self.free_groups: Set[str] = set(self.group_prefs.keys())
        self.current_matches: Dict[str, str] = {}  # listing_id -> group_id
        self.group_current_match: Dict[str, str] = {}  # group_id -> listing_id
        self.next_proposal_index: Dict[str, int] = {g: 0 for g in self.group_prefs.keys()}
        
        self.proposals_sent = 0
        self.proposals_rejected = 0
        self.iterations = 0
        
        logger.info(f"Initialized DA: {len(self.group_prefs)} groups, {len(self.listing_prefs)} listings")
    
    def run(self) -> Tuple[List[MatchResult], DiagnosticMetrics]:
        """Execute DA algorithm. Returns (matches, diagnostics)."""
        logger.info("Starting Deferred Acceptance...")
        start_time = datetime.now()
        
        # Main loop: each free group proposes
        while self.free_groups:
            self.iterations += 1
            if self.iterations > 10000:
                logger.error("DA exceeded iteration limit!")
                break
            
            group_id = next(iter(self.free_groups))
            next_listing = self._get_next_proposal(group_id)
            
            if next_listing is None:
                self.free_groups.remove(group_id)
                continue
            
            self._propose(group_id, next_listing)
        
        matches = self._generate_matches()
        diagnostics = self._generate_diagnostics()
        
        is_stable = self._verify_stability(matches)
        diagnostics.is_stable = is_stable
        diagnostics.stability_check_passed = is_stable
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"DA completed: {len(matches)} matches, {self.iterations} iters, {elapsed:.2f}s")
        
        return matches, diagnostics
    
    def _get_next_proposal(self, group_id: str) -> Optional[str]:
        """Get next listing for group to propose to."""
        pref_list = self.group_prefs.get(group_id, [])
        next_idx = self.next_proposal_index[group_id]
        
        if next_idx >= len(pref_list):
            return None
        
        listing_id = pref_list[next_idx][0]
        self.next_proposal_index[group_id] += 1
        return listing_id
    
    def _propose(self, group_id: str, listing_id: str):
        """Group proposes to listing. Listing accepts if better than current."""
        self.proposals_sent += 1
        current_match = self.current_matches.get(listing_id)
        
        if current_match is None:
            self._accept_proposal(group_id, listing_id)
        elif self._prefers(listing_id, group_id, current_match):
            self._reject_proposal(current_match)
            self._accept_proposal(group_id, listing_id)
        else:
            self._reject_proposal(group_id)
    
    def _prefers(self, listing_id: str, group_a: str, group_b: str) -> bool:
        """Does listing prefer group_a over group_b? Lower rank = better."""
        pref_list = self.listing_prefs.get(listing_id, [])
        ranks = {g_id: rank for g_id, rank, score in pref_list}
        return ranks.get(group_a, float('inf')) < ranks.get(group_b, float('inf'))
    
    def _accept_proposal(self, group_id: str, listing_id: str):
        self.current_matches[listing_id] = group_id
        self.group_current_match[group_id] = listing_id
        self.free_groups.discard(group_id)
    
    def _reject_proposal(self, group_id: str):
        self.proposals_rejected += 1
        self.group_current_match.pop(group_id, None)
        self.free_groups.add(group_id)
    
    def _generate_matches(self) -> List[MatchResult]:
        """Generate match results from final matching."""
        matches = []
        matched_at = datetime.now()
        
        for listing_id, group_id in self.current_matches.items():
            group_pref = self.group_prefs.get(group_id, [])
            listing_pref = self.listing_prefs.get(listing_id, [])
            
            group_score, group_rank = 0.0, 0
            for l_id, rank, score in group_pref:
                if l_id == listing_id:
                    group_score, group_rank = score, rank
                    break
            
            listing_score, listing_rank = 0.0, 0
            for g_id, rank, score in listing_pref:
                if g_id == group_id:
                    listing_score, listing_rank = score, rank
                    break
            
            matches.append(MatchResult(
                group_id=group_id, listing_id=listing_id,
                group_score=group_score, listing_score=listing_score,
                group_rank=group_rank, listing_rank=listing_rank,
                matched_at=matched_at, is_stable=True
            ))
        
        return matches
    
    def _generate_diagnostics(self) -> DiagnosticMetrics:
        """Generate diagnostic metrics for this matching round."""
        metadata = self.metadata
        num_groups = len(self.group_prefs)
        num_listings = len(self.listing_prefs)
        num_matches = len(self.current_matches)
        
        # Calculate average ranks
        avg_group_rank, avg_listing_rank = 0.0, 0.0
        if num_matches > 0:
            group_ranks, listing_ranks = [], []
            for listing_id, group_id in self.current_matches.items():
                for l_id, score, rank in self.group_prefs.get(group_id, []):
                    if l_id == listing_id:
                        group_ranks.append(rank)
                        break
                for g_id, score, rank in self.listing_prefs.get(listing_id, []):
                    if g_id == group_id:
                        listing_ranks.append(rank)
                        break
            
            avg_group_rank = sum(group_ranks) / len(group_ranks) if group_ranks else 0
            avg_listing_rank = sum(listing_ranks) / len(listing_ranks) if listing_ranks else 0
        
        # Quality score: 50% match rate + 50% rank quality
        match_rate = num_matches / max(num_groups, 1)
        max_rank = max(num_listings, num_groups)
        rank_quality = 1.0 - ((avg_group_rank + avg_listing_rank) / 2 / max_rank) if max_rank > 0 else 0
        quality_score = (match_rate * 50) + (rank_quality * 50)
        
        return DiagnosticMetrics(
            city=metadata.get('city', 'unknown'),
            date_window_start=metadata.get('date_window_start', ''),
            date_window_end=metadata.get('date_window_end', ''),
            total_groups=num_groups, total_listings=num_listings,
            feasible_pairs=metadata.get('feasible_pairs', 0),
            matched_groups=num_matches, matched_listings=num_matches,
            unmatched_groups=num_groups - num_matches,
            unmatched_listings=num_listings - num_matches,
            proposals_sent=self.proposals_sent, proposals_rejected=self.proposals_rejected,
            iterations=self.iterations, avg_group_rank=avg_group_rank,
            avg_listing_rank=avg_listing_rank, match_quality_score=quality_score,
            is_stable=False, stability_check_passed=False, executed_at=datetime.now()
        )
    
    def _verify_stability(self, matches: List[MatchResult]) -> bool:
        """Verify no blocking pairs exist. Blocking pair = both prefer each other over current."""
        if not matches:
            return True
        
        group_to_listing = {m.group_id: m.listing_id for m in matches}
        listing_to_group = {m.listing_id: m.group_id for m in matches}
        
        for group_id, group_prefs in self.group_prefs.items():
            current_listing = group_to_listing.get(group_id)
            
            if current_listing is None:
                # Unmatched group - check if any listing prefers it
                for listing_id, group_score, group_rank in group_prefs:
                    current_group = listing_to_group.get(listing_id)
                    if current_group and self._prefers(listing_id, group_id, current_group):
                        logger.warning(f"Blocking pair: unmatched {group_id} + {listing_id}")
                        return False
            else:
                # Find current rank
                current_rank = None
                for l_id, score, rank in group_prefs:
                    if l_id == current_listing:
                        current_rank = rank
                        break
                
                # Check all preferred listings
                for listing_id, group_score, group_rank in group_prefs:
                    if group_rank >= current_rank:
                        break
                    
                    current_group = listing_to_group.get(listing_id)
                    if current_group is None or self._prefers(listing_id, group_id, current_group):
                        logger.warning(f"Blocking pair: {group_id} + {listing_id}")
                        return False
        
        logger.info("Stability verified - no blocking pairs")
        return True


def run_deferred_acceptance(preference_lists: Dict) -> Tuple[List[MatchResult], DiagnosticMetrics]:
    """Main entry point for DA algorithm."""
    engine = DeferredAcceptanceEngine(preference_lists)
    return engine.run()


__all__ = ['DeferredAcceptanceEngine', 'MatchResult', 'DiagnosticMetrics', 'run_deferred_acceptance']
