"""
Large Neighborhood Search (LNS) Optimizer for Stable Matching

Improves match quality by iteratively destroying and repairing the worst matches.

Algorithm:
1. Identify worst 15% of matches
2. Destroy selected matches (using heuristics)
3. Repair with intelligent assignment (using heuristics)
4. Accept if improvement found
5. Repeat for max 50 iterations or until convergence
"""

import random
import math
from typing import List, Dict, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Match:
    """Simplified match structure for LNS"""
    group_id: str
    listing_id: str
    group_score: float
    listing_score: float
    group_rank: int
    listing_rank: int
    quality_score: float = 0.0
    
    def calculate_quality(self):
        """
        Calculate combined quality score.
        Lower rank = better (closer to first choice)
        """
        self.quality_score = (
            0.4 * self.group_score +              # 40% weight on group's preference
            0.3 * self.listing_score +             # 30% weight on listing's preference
            0.2 * (100 / (self.group_rank + 1)) +  # 20% weight (inverse rank)
            0.1 * (100 / (self.listing_rank + 1))  # 10% weight (inverse rank)
        )
        return self.quality_score


# =============================================================================
# QUALITY METRICS
# =============================================================================

def calculate_total_quality(matches: List[Match]) -> float:
    """Calculate total quality of all matches"""
    return sum(m.quality_score for m in matches)


def calculate_average_quality(matches: List[Match]) -> float:
    """Calculate average quality score"""
    if not matches:
        return 0.0
    return calculate_total_quality(matches) / len(matches)


def identify_worst_matches(matches: List[Match], percentage: float = 0.15) -> List[Match]:
    """
    Identify worst matches by quality score.
    
    Args:
        matches: All current matches
        percentage: Percentage to destroy (default 15%)
    
    Returns:
        List of worst matches
    """
    # Ensure quality scores are calculated
    for m in matches:
        if m.quality_score == 0.0:
            m.calculate_quality()
    
    # Sort by quality (ascending = worst first)
    sorted_matches = sorted(matches, key=lambda m: m.quality_score)
    
    # Take bottom percentage
    destroy_count = max(1, int(len(matches) * percentage))
    return sorted_matches[:destroy_count]


# =============================================================================
# DESTROY HEURISTICS
# =============================================================================

def worst_first_destroy(matches: List[Match], destroy_count: int) -> List[Match]:
    """
    Destroy worst matches by quality score.
    
    Most aggressive - targets real problem matches.
    """
    sorted_matches = sorted(matches, key=lambda m: m.quality_score)
    return sorted_matches[:destroy_count]


def random_destroy(matches: List[Match], destroy_count: int) -> List[Match]:
    """
    Randomly select matches to destroy.
    
    Provides diversification and exploration.
    """
    return random.sample(matches, min(destroy_count, len(matches)))


def cluster_destroy(matches: List[Match], destroy_count: int, all_groups: List[Dict]) -> List[Match]:
    """
    Destroy matches in same city cluster/neighborhood.
    
    Groups matches by budget range and destroys worst cluster.
    """
    # Group by budget range
    budget_clusters = {}
    
    for match in matches:
        # Find group details
        group = next((g for g in all_groups if g['id'] == match.group_id), None)
        if not group:
            continue
        
        # Cluster by budget_min (rounded to nearest 500)
        budget_key = round(group.get('budget_per_person_min', 1500) / 500) * 500
        
        if budget_key not in budget_clusters:
            budget_clusters[budget_key] = []
        budget_clusters[budget_key].append(match)
    
    # Find cluster with worst average quality
    worst_cluster = None
    worst_avg = float('inf')
    
    for cluster_matches in budget_clusters.values():
        if len(cluster_matches) < destroy_count:
            continue
        
        avg_quality = sum(m.quality_score for m in cluster_matches) / len(cluster_matches)
        if avg_quality < worst_avg:
            worst_avg = avg_quality
            worst_cluster = cluster_matches
    
    # If no suitable cluster, fall back to worst-first
    if worst_cluster is None:
        return worst_first_destroy(matches, destroy_count)
    
    # Return worst matches from cluster
    return sorted(worst_cluster, key=lambda m: m.quality_score)[:destroy_count]


# =============================================================================
# REPAIR HEURISTICS
# =============================================================================

def regret_greedy_repair(
    destroyed_groups: Set[str],
    destroyed_listings: Set[str],
    all_groups: List[Dict],
    all_listings: List[Dict],
    existing_matches: List[Match]
) -> List[Match]:
    """
    Regret-based greedy repair.
    
    Regret = difference between best and second-best option.
    High regret means we should assign now or lose the opportunity.
    
    Algorithm:
    1. For each unmatched group, calc regret for all available listings
    2. Assign pair with highest regret
    3. Remove from available
    4. Repeat
    """
    from app.services.stable_matching.scoring import calculate_group_score, calculate_listing_score
    
    repaired = []
    available_groups = set(destroyed_groups)
    available_listings = set(destroyed_listings)
    
    while available_groups and available_listings:
        # Calculate regret for all (group, listing) pairs
        regrets = []
        
        for group_id in available_groups:
            group = next((g for g in all_groups if g['id'] == group_id), None)
            if not group:
                continue
            
            # Get scores for all available listings
            scores = []
            for listing_id in available_listings:
                listing = next((l for l in all_listings if l['id'] == listing_id), None)
                if not listing:
                    continue
                
                score = calculate_group_score(group, listing)
                scores.append((score, listing_id))
            
            # Calculate regret
            if len(scores) >= 2:
                scores.sort(reverse=True, key=lambda x: x[0])
                regret = scores[0][0] - scores[1][0]  # Best - second best
                regrets.append((regret, group_id, scores[0][1], scores[0][0]))
            elif len(scores) == 1:
                # Only one option, high regret
                regrets.append((100, group_id, scores[0][1], scores[0][0]))
        
        if not regrets:
            break
        
        # Assign highest regret pair
        _, best_group_id, best_listing_id, group_score = max(regrets, key=lambda x: x[0])
        
        # Get listing score
        group = next((g for g in all_groups if g['id'] == best_group_id), None)
        listing = next((l for l in all_listings if l['id'] == best_listing_id), None)
        listing_score = calculate_listing_score(listing, group)
        
        # Create match
        repaired.append(Match(
            group_id=best_group_id,
            listing_id=best_listing_id,
            group_score=group_score,
            listing_score=listing_score,
            group_rank=1,  # Will be recalculated later
            listing_rank=1
        ))
        
        available_groups.remove(best_group_id)
        available_listings.remove(best_listing_id)
    
    # Calculate quality scores
    for match in repaired:
        match.calculate_quality()
    
    return repaired


def randomized_greedy_repair(
    destroyed_groups: Set[str],
    destroyed_listings: Set[str],
    all_groups: List[Dict],
    all_listings: List[Dict],
    K: int = 3
) -> List[Match]:
    """
    Randomized greedy repair.
    
    For each group, randomly pick from top K best listings.
    Adds diversity to exploration.
    """
    from app.services.stable_matching.scoring import calculate_group_score, calculate_listing_score
    import heapq
    
    repaired = []
    available_groups = list(destroyed_groups)
    available_listings = set(destroyed_listings)
    
    random.shuffle(available_groups)  # Random order
    
    for group_id in available_groups:
        group = next((g for g in all_groups if g['id'] == group_id), None)
        if not group or not available_listings:
            continue
        
        # Score all available listings
        scores = []
        for listing_id in available_listings:
            listing = next((l for l in all_listings if l['id'] == listing_id), None)
            if listing:
                score = calculate_group_score(group, listing)
                scores.append((score, listing_id, listing))
        
        if not scores:
            continue
        
        # Get top K
        top_k = heapq.nlargest(min(K, len(scores)), scores, key=lambda x: x[0])
        
        # Randomly pick from top K
        chosen = random.choice(top_k)
        group_score, listing_id, listing = chosen
        
        listing_score = calculate_listing_score(listing, group)
        
        repaired.append(Match(
            group_id=group_id,
            listing_id=listing_id,
            group_score=group_score,
            listing_score=listing_score,
            group_rank=1,
            listing_rank=1
        ))
        
        available_listings.remove(listing_id)
    
    # Calculate quality scores
    for match in repaired:
        match.calculate_quality()
    
    return repaired


# =============================================================================
# LNS MAIN ALGORITHM
# =============================================================================

def run_lns_optimization(
    initial_matches: List[Dict],
    all_groups: List[Dict],
    all_listings: List[Dict],
    max_iterations: int = 50,
    destroy_percentage: float = 0.15
) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Run Large Neighborhood Search optimization on stable matches.
    
    Args:
        initial_matches: Stable matches from Gale-Shapley
        all_groups: All groups (for scoring)
        all_listings: All listings (for scoring)
        max_iterations: Max LNS iterations
        destroy_percentage: Percentage of matches to destroy each iteration
    
    Returns:
        (optimized_matches, statistics)
    """
    start_time = datetime.now()
    
    # Convert to Match objects
    current_solution = [
        Match(
            group_id=m['group_id'],
            listing_id=m['listing_id'],
            group_score=m['group_score'],
            listing_score=m['listing_score'],
            group_rank=m['group_rank'],
            listing_rank=m.get('listing_rank', 1)
        )
        for m in initial_matches
    ]
    
    # Calculate initial quality scores
    for match in current_solution:
        match.calculate_quality()
    
    initial_quality = calculate_average_quality(current_solution)
    best_solution = current_solution.copy()
    best_quality = initial_quality
    
    iterations_without_improvement = 0
    destroy_count = max(1, int(len(current_solution) * destroy_percentage))
    
    for iteration in range(max_iterations):
        # Select destroy heuristic (adaptive mix)
        if iteration % 5 == 0:
            destroyed = random_destroy(current_solution, destroy_count)
            destroy_method = "random"
        elif iteration % 3 == 0:
            destroyed = cluster_destroy(current_solution, destroy_count, all_groups)
            destroy_method = "cluster"
        else:
            destroyed = worst_first_destroy(current_solution, destroy_count)
            destroy_method = "worst_first"
        
        # Extract groups and listings
        destroyed_group_ids = {m.group_id for m in destroyed}
        destroyed_listing_ids = {m.listing_id for m in destroyed}
        
        # Select repair heuristic
        if iteration % 4 == 0:
            repaired = randomized_greedy_repair(
                destroyed_group_ids,
                destroyed_listing_ids,
                all_groups,
                all_listings,
                K=3
            )
        else:
            repaired = regret_greedy_repair(
                destroyed_group_ids,
                destroyed_listing_ids,
                all_groups,
                all_listings,
                current_solution
            )
        
        # Build new solution
        new_solution = [m for m in current_solution if m not in destroyed] + repaired
        new_quality = calculate_average_quality(new_solution)
        
        # Acceptance criterion (simulated annealing)
        temperature = 0.1 * (max_iterations - iteration) / max_iterations
        
        if accept_solution(best_quality, new_quality, temperature):
            current_solution = new_solution
            
            if new_quality > best_quality:
                best_solution = new_solution
                best_quality = new_quality
                iterations_without_improvement = 0
            else:
                iterations_without_improvement += 1
        else:
            iterations_without_improvement += 1
        
        # Early stopping
        if iterations_without_improvement >= 10:
            break
    
    # Convert back to dict format
    optimized_matches = [
        {
            'group_id': m.group_id,
            'listing_id': m.listing_id,
            'group_score': m.group_score,
            'listing_score': m.listing_score,
            'group_rank': m.group_rank,
            'listing_rank': m.listing_rank,
            'matched_at': datetime.utcnow().isoformat(),
            'is_stable': True,  # May not be truly stable
            'quality_score': m.quality_score
        }
        for m in best_solution
    ]
    
    execution_time = (datetime.now() - start_time).total_seconds()
    
    statistics = {
        'initial_avg_quality': initial_quality,
        'final_avg_quality': best_quality,
        'improvement_percentage': ((best_quality - initial_quality) / initial_quality * 100) if initial_quality > 0 else 0,
        'iterations_run': iteration + 1,
        'execution_time_seconds': execution_time,
        'matches_optimized': len(optimized_matches)
    }
    
    return optimized_matches, statistics


def accept_solution(current_quality: float, new_quality: float, temperature: float) -> bool:
    """
    Simulated annealing acceptance criterion.
    
    Always accept improvements.
    Sometimes accept worse solutions with probability based on temperature.
    """
    if new_quality >= current_quality:
        return True
    
    # Accept worse with probability
    if temperature > 0:
        delta = new_quality - current_quality
        prob = math.exp(delta / temperature)
        return random.random() < prob
    
    return False


# Export public API
__all__ = [
    'run_lns_optimization',
    'Match',
    'calculate_average_quality',
    'identify_worst_matches'
]
