#!/usr/bin/env python3
"""
Run stable matching algorithm for all cities and save results to JSON
"""
import sys
import json
from datetime import datetime
from app.dependencies.supabase import get_admin_client
from app.services.stable_matching import (
    get_eligible_groups,
    get_eligible_listings,
    build_feasible_pairs,
    build_preference_lists,
    run_deferred_acceptance
)

def run_matching_for_city(city: str, date_flexibility_days: int = 60):
    """Run matching algorithm for a specific city"""
    print(f"\n📍 Processing {city}...")
    
    try:
        supabase = get_admin_client()
        
        # Fetch all groups and listings from database
        all_groups_response = supabase.table('roommate_groups').select('*, members:group_members(*)').eq('status', 'active').execute()
        all_groups = all_groups_response.data
        
        all_listings_response = supabase.table('listings').select('*').eq('status', 'active').execute()
        all_listings = all_listings_response.data
        
        # Get eligible groups and listings for this city
        groups, group_stats = get_eligible_groups(all_groups, city)
        listings, listing_stats = get_eligible_listings(all_listings, city)
        
        print(f"   Found {len(groups)} groups and {len(listings)} listings")
        
        # Debug: Check listing structure
        if listings and len(listings) > 0:
            first_listing = listings[0]
            print(f"   Debug - Listing amenities type: {type(first_listing.get('amenities'))}")
            print(f"   Debug - Listing house_rules type: {type(first_listing.get('house_rules'))}")
        
        if not groups or not listings:
            return {
                'status': 'no_data',
                'groups': len(groups),
                'listings': len(listings),
                'matches': []
            }
        
        # Build feasible pairs
        feasible_pairs, _ = build_feasible_pairs(
            groups, 
            listings, 
            date_delta_days=date_flexibility_days
        )
        
        print(f"   Found {len(feasible_pairs)} feasible pairs")
        
        if not feasible_pairs:
            return {
                'status': 'no_feasible_pairs',
                'groups': len(groups),
                'listings': len(listings),
                'feasible_pairs': 0,
                'matches': []
            }
        
        # Build preference lists
        preference_lists = build_preference_lists(feasible_pairs, groups, listings)
        
        # Run deferred acceptance algorithm
        matches, diagnostics = run_deferred_acceptance(preference_lists)
        
        print(f"   ✅ Created {len(matches)} stable matches")
        
        # Convert matches to serializable format
        matches_data = []
        for match in matches:
            matches_data.append({
                'group_id': match.group_id,
                'listing_id': match.listing_id,
                'group_rank': match.group_rank,
                'listing_rank': match.listing_rank,
                'group_score': match.group_score,
                'listing_score': match.listing_score,
                'is_stable': match.is_stable,
                'city': city
            })
        
        # Convert diagnostics to serializable format
        diagnostics_data = {
            'iterations': diagnostics.iterations,
            'matched_groups': diagnostics.matched_groups,
            'unmatched_groups': diagnostics.unmatched_groups,
            'matched_listings': diagnostics.matched_listings,
            'unmatched_listings': diagnostics.unmatched_listings,
            'proposals_sent': diagnostics.proposals_sent,
            'proposals_rejected': diagnostics.proposals_rejected,
            'avg_group_rank': diagnostics.avg_group_rank,
            'avg_listing_rank': diagnostics.avg_listing_rank,
            'match_quality_score': diagnostics.match_quality_score,
            'is_stable': diagnostics.is_stable
        }
        
        return {
            'status': 'success',
            'groups': len(groups),
            'listings': len(listings),
            'feasible_pairs': len(feasible_pairs),
            'matches': matches_data,
            'diagnostics': diagnostics_data
        }
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"   ❌ Error: {str(e)}")
        print(f"   Traceback: {error_detail[:500]}")
        return {
            'status': 'error',
            'error': str(e),
            'traceback': error_detail
        }

def main():
    cities = [
        'Fresno', 'San Jose', 'Los Angeles', 'Anaheim', 
        'Sacramento', 'Oakland', 'San Diego', 'San Francisco'
    ]
    
    print('🚀 Running Stable Matching Algorithm for All Cities')
    print('='*80)
    
    all_results = {
        'timestamp': datetime.now().isoformat(),
        'date_flexibility_days': 60,
        'cities': {},
        'summary': {
            'total_matches': 0,
            'total_groups': 0,
            'total_listings': 0,
            'cities_processed': 0,
            'cities_with_matches': 0
        }
    }
    
    for city in cities:
        result = run_matching_for_city(city, date_flexibility_days=60)
        all_results['cities'][city] = result
        
        if result['status'] == 'success':
            all_results['summary']['cities_processed'] += 1
            all_results['summary']['total_matches'] += len(result['matches'])
            all_results['summary']['total_groups'] += result['groups']
            all_results['summary']['total_listings'] += result['listings']
            if len(result['matches']) > 0:
                all_results['summary']['cities_with_matches'] += 1
    
    # Save to JSON file
    output_file = 'matching_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print('\n' + '='*80)
    print(f'\n📊 Summary:')
    print(f'   • Cities processed: {all_results["summary"]["cities_processed"]}/{len(cities)}')
    print(f'   • Cities with matches: {all_results["summary"]["cities_with_matches"]}')
    print(f'   • Total groups: {all_results["summary"]["total_groups"]}')
    print(f'   • Total listings: {all_results["summary"]["total_listings"]}')
    print(f'   • Total matches created: {all_results["summary"]["total_matches"]}')
    print(f'\n💾 Results saved to: {output_file}')
    print(f'📄 View results: cat {output_file} | python -m json.tool')

if __name__ == '__main__':
    main()
