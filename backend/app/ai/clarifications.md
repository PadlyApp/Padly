Did we assign listings to categories how did we choose which cateogry to assign a listing to 

Yes — we did assign every listing to exactly one category.

How category is chosen

In backend/app/ai/categorize_and_map.py, function categorize_listings(...) uses a priority cascade.
“Priority cascade” means: check rules in a fixed order; first matching rule wins; once assigned, stop checking for that listing.
Order used (highest priority first)

Accessible Modern (5)
wheelchair_access == 1 or electric_vehicle_charge == 1
Premium / Luxury (3)
price > 1500 and (comes_furnished == 1 or laundry_options == "w/d in unit" or garage parking)
Spacious Family (1)
beds >= 3 and sqfeet > 1100
Budget Compact (0)
price < 900 and sqfeet < 800 and beds <= 1
Pet-Friendly (2)
cats_allowed == 1 and dogs_allowed == 1
Urban Convenience (4)
catch-all for anything still unassigned
Why this method

Many listings match multiple rules (example: expensive + pet-friendly + EV).
Priority makes assignment deterministic and avoids duplicates.
So each listing has one category_id and one category_name, saved to listing_categories.csv.
If you want, I can also give you 3 concrete listing examples and show exactly which category each would get step-by-step.



- How is affinity boosted
Great question — this is exactly in compute_user_category_affinity.

How much each category is boosted

Start value for all 6 categories: 0.05 each (small base prior)
Then add boosts:

Category 0 (Budget Compact)

+0.8 if budget_max < 900
+0.3 else if budget_max < 1100
Category 1 (Spacious Family)

+0.7 if desired_beds >= 3
+0.4 if household_size >= 3
+0.3 if desired_sqft_min > 1100
Category 2 (Pet-Friendly)

+0.5 if has_cats == 1
+0.5 if has_dogs == 1
Category 3 (Premium/Luxury)

+0.6 if budget_max > 1500
+0.5 if wants_furnished == 1
+0.3 if income > 80_000
Category 4 (Urban Convenience)

+0.6 if type_pref_apartment == 1
+0.4 if 900 <= budget_max <= 1500
Category 5 (Accessible Modern)

+1.0 if needs_wheelchair == 1
+0.8 if has_ev == 1