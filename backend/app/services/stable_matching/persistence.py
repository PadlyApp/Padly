"""
Phase 5: Database Persistence

This module handles saving match results and diagnostics to the Supabase database.

Tables:
- stable_matches: Stores individual match results
- match_diagnostics: Stores aggregate metrics per matching round

Author: Padly Matching Team
Version: 0.6.0
"""

from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
import logging
from supabase import Client

from .deferred_acceptance import MatchResult, DiagnosticMetrics

logger = logging.getLogger(__name__)


class MatchPersistenceEngine:
    """
    Handles persistence of matching results to the database
    
    Responsibilities:
    - Save match results to stable_matches table
    - Save diagnostics to match_diagnostics table
    - Handle batch insertions
    - Manage transactions
    - Expire old matches
    - Preserve confirmed matches (Option 3: Hybrid Re-matching)
    """
    
    def __init__(self, supabase_client: Client):
        """
        Initialize persistence engine
        
        Args:
            supabase_client: Authenticated Supabase client
        """
        self.supabase = supabase_client
        logger.info("MatchPersistenceEngine initialized")
    
    async def get_confirmed_matches(self, city: Optional[str] = None) -> Tuple[List[Dict], Set[str], Set[str]]:
        """
        Get matches that have been confirmed by BOTH group and listing owner.
        
        A match is considered "confirmed" when both group_confirmed_at AND 
        listing_confirmed_at are NOT NULL.
        
        Args:
            city: Optional city filter
        
        Returns:
            Tuple of:
            - List of confirmed match records
            - Set of confirmed group IDs (to exclude from matching)
            - Set of confirmed listing IDs (to exclude from matching)
        """
        try:
            # Get confirmed matches (both confirmations present)
            query = self.supabase.table('stable_matches')\
                .select('*')\
                .eq('status', 'active')\
                .not_.is_('group_confirmed_at', 'null')\
                .not_.is_('listing_confirmed_at', 'null')
            
            response = query.execute()
            all_confirmed = response.data if response.data else []
            
            # If city filter, we need to get the group's city
            if city and all_confirmed:
                # Get group IDs and filter by city
                group_ids = [m['group_id'] for m in all_confirmed]
                groups_response = self.supabase.table('roommate_groups')\
                    .select('id, target_city')\
                    .in_('id', group_ids)\
                    .eq('target_city', city)\
                    .execute()
                
                city_group_ids = {g['id'] for g in (groups_response.data or [])}
                confirmed_matches = [m for m in all_confirmed if m['group_id'] in city_group_ids]
            else:
                confirmed_matches = all_confirmed
            
            confirmed_group_ids = {m['group_id'] for m in confirmed_matches}
            confirmed_listing_ids = {m['listing_id'] for m in confirmed_matches}
            
            logger.info(f"Found {len(confirmed_matches)} confirmed matches "
                       f"({len(confirmed_group_ids)} groups, {len(confirmed_listing_ids)} listings)")
            
            return confirmed_matches, confirmed_group_ids, confirmed_listing_ids
            
        except Exception as e:
            logger.error(f"Failed to get confirmed matches: {str(e)}")
            return [], set(), set()
    
    async def delete_unconfirmed_matches(self, city: str) -> int:
        """
        Delete only UNCONFIRMED matches for a city before re-matching.
        
        Confirmed matches (where both group_confirmed_at AND listing_confirmed_at 
        are NOT NULL) are preserved.
        
        Args:
            city: City to clear unconfirmed matches for
        
        Returns:
            Number of matches deleted
        """
        try:
            # Get group IDs in this city first
            groups_response = self.supabase.table('roommate_groups')\
                .select('id')\
                .eq('target_city', city)\
                .execute()
            
            if not groups_response.data:
                return 0
            
            group_ids = [g['id'] for g in groups_response.data]
            
            # Delete all unconfirmed matches for these groups in a single query
            # Unconfirmed = group_confirmed_at IS NULL OR listing_confirmed_at IS NULL
            # We delete where group_confirmed_at IS NULL (covers partial and no confirmation)
            response = self.supabase.table('stable_matches')\
                .delete()\
                .in_('group_id', group_ids)\
                .eq('status', 'active')\
                .is_('group_confirmed_at', 'null')\
                .execute()
            
            deleted_count = len(response.data) if response.data else 0
            
            # Also delete where listing didn't confirm (but group did)
            response2 = self.supabase.table('stable_matches')\
                .delete()\
                .in_('group_id', group_ids)\
                .eq('status', 'active')\
                .is_('listing_confirmed_at', 'null')\
                .execute()
            
            deleted_count += len(response2.data) if response2.data else 0
            
            logger.info(f"Deleted {deleted_count} unconfirmed matches in {city}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete unconfirmed matches: {str(e)}")
            return 0
    
    async def save_matches(
        self,
        matches: List[MatchResult],
        diagnostics: DiagnosticMetrics,
        batch_size: int = 100
    ) -> Dict:
        """
        Save matches and diagnostics to database
        
        Args:
            matches: List of match results from DA algorithm
            diagnostics: Diagnostic metrics for this round
            batch_size: Number of matches to insert per batch
        
        Returns:
            Dict with status and counts
        """
        logger.info(f"Saving {len(matches)} matches and diagnostics to database...")
        
        try:
            # First, save diagnostics (parent record)
            diagnostics_id = await self._save_diagnostics(diagnostics)
            logger.info(f"Diagnostics saved with ID: {diagnostics_id}")
            
            # Then, save matches in batches
            matches_saved = await self._save_matches_batch(
                matches, 
                diagnostics_id,
                batch_size
            )
            logger.info(f"Saved {matches_saved} matches")
            
            # Expire old matches (older than 30 days)
            expired_count = await self._expire_old_matches()
            logger.info(f"Expired {expired_count} old matches")
            
            return {
                'status': 'success',
                'diagnostics_id': diagnostics_id,
                'matches_saved': matches_saved,
                'matches_expired': expired_count,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to save matches: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'matches_saved': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _save_diagnostics(self, diagnostics: DiagnosticMetrics) -> str:
        """
        Save diagnostics to match_diagnostics table
        
        Args:
            diagnostics: Diagnostic metrics to save
        
        Returns:
            ID of inserted diagnostics record
        """
        try:
            data = diagnostics.to_dict()
            
            # Insert diagnostics
            response = self.supabase.table('match_diagnostics').insert(data).execute()
            
            if not response.data or len(response.data) == 0:
                raise Exception("Failed to insert diagnostics - no data returned")
            
            diagnostics_id = response.data[0]['id']
            return diagnostics_id
            
        except Exception as e:
            logger.error(f"Failed to save diagnostics: {str(e)}")
            raise
    
    async def _save_matches_batch(
        self,
        matches: List[MatchResult],
        diagnostics_id: str,
        batch_size: int
    ) -> int:
        """
        Save matches in batches to stable_matches table
        
        Args:
            matches: List of matches to save
            diagnostics_id: Foreign key to diagnostics record
            batch_size: Number of matches per batch
        
        Returns:
            Total number of matches saved
        """
        if not matches:
            return 0
        
        total_saved = 0
        
        # Process in batches
        for i in range(0, len(matches), batch_size):
            batch = matches[i:i + batch_size]
            
            # Convert to database format
            batch_data = []
            for match in batch:
                data = match.to_dict()
                data['diagnostics_id'] = diagnostics_id
                batch_data.append(data)
            
            try:
                # Insert batch
                response = self.supabase.table('stable_matches').insert(batch_data).execute()
                
                if response.data:
                    batch_count = len(response.data)
                    total_saved += batch_count
                    logger.debug(f"Saved batch {i//batch_size + 1}: {batch_count} matches")
                else:
                    logger.warning(f"Batch {i//batch_size + 1} returned no data")
                    
            except Exception as e:
                logger.error(f"Failed to save batch {i//batch_size + 1}: {str(e)}")
                # Continue with next batch instead of failing completely
                continue
        
        return total_saved
    
    async def _expire_old_matches(self, days: int = 30) -> int:
        """
        Expire matches older than specified days
        
        Uses the expire_old_matches() database function
        
        Args:
            days: Number of days threshold (default 30)
        
        Returns:
            Number of matches expired
        """
        try:
            # Call the database function
            response = self.supabase.rpc(
                'expire_old_matches',
                {'days_threshold': days}
            ).execute()
            
            # Function returns count of expired matches
            if response.data is not None:
                return response.data
            else:
                return 0
                
        except Exception as e:
            logger.warning(f"Failed to expire old matches: {str(e)}")
            return 0
    
    async def get_active_matches(
        self,
        city: Optional[str] = None,
        group_id: Optional[str] = None,
        listing_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve active matches from database
        
        Args:
            city: Filter by city (optional)
            group_id: Filter by specific group (optional)
            listing_id: Filter by specific listing (optional)
        
        Returns:
            List of active match records
        """
        try:
            # Use the v_active_stable_matches view
            query = self.supabase.table('v_active_stable_matches').select('*')
            
            # Apply filters
            if city:
                query = query.eq('city', city)
            if group_id:
                query = query.eq('group_id', group_id)
            if listing_id:
                query = query.eq('listing_id', listing_id)
            
            # Order by match quality (highest ranks first)
            query = query.order('group_rank', desc=False)
            
            response = query.execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Failed to retrieve active matches: {str(e)}")
            return []
    
    async def get_diagnostics(
        self,
        city: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Retrieve diagnostic records
        
        Args:
            city: Filter by city (optional)
            limit: Maximum records to return
        
        Returns:
            List of diagnostic records
        """
        try:
            query = self.supabase.table('match_diagnostics').select('*')
            
            if city:
                query = query.eq('city', city)
            
            # Order by most recent first
            query = query.order('executed_at', desc=True).limit(limit)
            
            response = query.execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Failed to retrieve diagnostics: {str(e)}")
            return []
    
    async def delete_matches_for_group(self, group_id: str) -> int:
        """
        Delete all matches for a specific group
        
        Use case: When a group is dissolved or changes preferences
        
        Args:
            group_id: The group ID
        
        Returns:
            Number of matches deleted
        """
        try:
            response = self.supabase.table('stable_matches')\
                .delete()\
                .eq('group_id', group_id)\
                .execute()
            
            count = len(response.data) if response.data else 0
            logger.info(f"Deleted {count} matches for group {group_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete matches for group {group_id}: {str(e)}")
            return 0
    
    async def delete_matches_for_listing(self, listing_id: str) -> int:
        """
        Delete all matches for a specific listing
        
        Use case: When a listing is removed or becomes unavailable
        
        Args:
            listing_id: The listing ID
        
        Returns:
            Number of matches deleted
        """
        try:
            response = self.supabase.table('stable_matches')\
                .delete()\
                .eq('listing_id', listing_id)\
                .execute()
            
            count = len(response.data) if response.data else 0
            logger.info(f"Deleted {count} matches for listing {listing_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete matches for listing {listing_id}: {str(e)}")
            return 0
    
    async def get_match_statistics(self, city: Optional[str] = None) -> Dict:
        """
        Get aggregate statistics about matches
        
        Args:
            city: Filter by city (optional)
        
        Returns:
            Dict with statistics
        """
        try:
            # Get active matches
            active_matches = await self.get_active_matches(city=city)
            
            # Get latest diagnostics
            diagnostics = await self.get_diagnostics(city=city, limit=1)
            
            if not diagnostics:
                return {
                    'total_active_matches': len(active_matches),
                    'latest_run': None
                }
            
            latest = diagnostics[0]
            
            return {
                'total_active_matches': len(active_matches),
                'latest_run': {
                    'city': latest.get('city'),
                    'executed_at': latest.get('executed_at'),
                    'matched_groups': latest.get('matched_groups'),
                    'matched_listings': latest.get('matched_listings'),
                    'match_quality_score': latest.get('match_quality_score'),
                    'is_stable': latest.get('is_stable')
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get match statistics: {str(e)}")
            return {'error': str(e)}


async def save_matching_results(
    supabase_client: Client,
    matches: List[MatchResult],
    diagnostics: DiagnosticMetrics
) -> Dict:
    """
    Main entry point for saving matching results
    
    Args:
        supabase_client: Authenticated Supabase client
        matches: List of match results from DA algorithm
        diagnostics: Diagnostic metrics
    
    Returns:
        Dict with save status and counts
    """
    engine = MatchPersistenceEngine(supabase_client)
    result = await engine.save_matches(matches, diagnostics)
    return result


async def get_active_matches_for_group(
    supabase_client: Client,
    group_id: str
) -> Optional[Dict]:
    """
    Get the active match for a specific group
    
    Args:
        supabase_client: Authenticated Supabase client
        group_id: The group ID
    
    Returns:
        Match record or None if no active match
    """
    engine = MatchPersistenceEngine(supabase_client)
    matches = await engine.get_active_matches(group_id=group_id)
    
    return matches[0] if matches else None


async def get_active_matches_for_listing(
    supabase_client: Client,
    listing_id: str
) -> Optional[Dict]:
    """
    Get the active match for a specific listing
    
    Args:
        supabase_client: Authenticated Supabase client
        listing_id: The listing ID
    
    Returns:
        Match record or None if no active match
    """
    engine = MatchPersistenceEngine(supabase_client)
    matches = await engine.get_active_matches(listing_id=listing_id)
    
    return matches[0] if matches else None


# Export public API
__all__ = [
    'MatchPersistenceEngine',
    'save_matching_results',
    'get_active_matches_for_group',
    'get_active_matches_for_listing'
]
