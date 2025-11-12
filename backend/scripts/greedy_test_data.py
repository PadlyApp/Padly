#####
# =====
# GENERATE MATCHING LISTINGS AND GROUPS FOR GREEDY ALGORITHM TESTING
# =====
#####
def generate_matching_listings_and_groups():
    """
    Create listings and matching roommate groups that satisfy ALL hard constraints.
    
    Hard Constraints:
    1. City match
    2. State/Province match
    3. Budget (rent <= max_budget)
    4. Bedroom count match
    5. Move-in date (listing available <= group move-in date)
    6. Lease type match
    """
    users = get_all_users()
    if len(users) < 5:
        print("Need at least 5 users to create test data.")
        return
    
    # Test scenarios with exact hard constraint matches
    test_scenarios = [
        {
            "city": "San Francisco",
            "state": "CA",
            "rent": 3000.0,
            "bedrooms": 3,
            "lease_type": "fixed_term",
            "group_size": 3,
            "group_name": "SF Tech Squad"
        },
        {
            "city": "Los Angeles",
            "state": "CA",
            "rent": 2500.0,
            "bedrooms": 2,
            "lease_type": "open_ended",
            "group_size": 2,
            "group_name": "LA Roomies"
        },
        {
            "city": "San Diego",
            "state": "CA",
            "rent": 2800.0,
            "bedrooms": 4,
            "lease_type": "fixed_term",
            "group_size": 4,
            "group_name": "San Diego Beach Crew"
        },
        {
            "city": "San Jose",
            "state": "CA",
            "rent": 3500.0,
            "bedrooms": 3,
            "lease_type": "open_ended",
            "group_size": 3,
            "group_name": "SJ Professional Group"
        },
        {
            "city": "Oakland",
            "state": "CA",
            "rent": 2200.0,
            "bedrooms": 2,
            "lease_type": "fixed_term",
            "group_size": 2,
            "group_name": "Oakland Squad"
        }
    ]
    
    user_index = 0
    
    for scenario in test_scenarios:
        print("\n" + "="*60)
        print(f"Creating matched pair for: {scenario['group_name']}")
        print("="*60)
        
        # 1. CREATE THE LISTING
        host_user = users[user_index % len(users)]
        user_index += 1
        
        token, host_user_id = get_auth_context(host_user["email"], "123456")
        if not token or not host_user_id:
            print(f"Failed to get auth for host {host_user['email']}")
            continue
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Listing available date (30 days from now)
        available_date = (datetime.datetime.now() + datetime.timedelta(days=30)).date().isoformat()
        
        listing_data = {
            "title": f"{scenario['bedrooms']}BR {scenario['lease_type'].replace('_', ' ').title()} in {scenario['city']}",
            "description": f"Perfect {scenario['bedrooms']} bedroom place in {scenario['city']}",
            "city": scenario["city"],
            "state_province": scenario["state"],
            "postal_code": "94102",
            "address_line_1": f"{random.randint(100, 999)} Main St",
            "price_per_month": scenario["rent"],
            "status": "active",
            "property_type": "entire_place",
            "lease_type": scenario["lease_type"],
            "available_from": available_date,
            "host_user_id": host_user_id,
            "lease_duration_months": 12 if scenario["lease_type"] == "fixed_term" else None,
            "number_of_bedrooms": scenario["bedrooms"],
            "number_of_bathrooms": 2.0,
            "area_sqft": 1000,
            "furnished": True,
            "utilities_included": True,
            "deposit_amount": 2000.0,
            "country": "USA",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "amenities": {
                "wifi": True,
                "parking": True,
                "laundry": "in_unit",
                "air_conditioning": True,
                "heating": True,
                "dishwasher": True,
                "pets_allowed": False,
                "gym": False,
                "pool": False
            },
            "house_rules": "No smoking, no parties",
            "shared_spaces": ["kitchen", "living_room"]
        }
        
        listing_data = sanitize_for_json(listing_data)
        
        print(f"\n📍 Creating LISTING: {listing_data['title']}")
        try:
            response = requests.post(
                "http://127.0.0.1:8000/api/listings",
                json=listing_data,
                headers=headers
            )
            if response.status_code == 200:
                listing_result = response.json()["data"]
                print(f"✅ Listing created (ID: {listing_result.get('id')})")
            else:
                print(f"❌ Failed to create listing: {response.text}")
                continue
        except Exception as e:
            print(f"ERROR creating listing: {e}")
            continue
        
        # 2. CREATE MATCHING GROUP
        creator = users[user_index % len(users)]
        user_index += 1
        
        token, creator_user_id = get_auth_context(creator["email"], "123456")
        if not token:
            print(f"Failed to get auth for group creator {creator['email']}")
            continue
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Group move-in date (45 days from now - AFTER listing becomes available)
        group_move_in_date = (datetime.datetime.now() + datetime.timedelta(days=45)).date().isoformat()
        
        # Calculate budget: group max budget = rent + buffer
        group_max_budget = scenario["rent"] + 500.0
        
        group_data = {
            "creator_user_id": creator_user_id,
            "group_name": scenario["group_name"],
            "description": f"Looking for a {scenario['bedrooms']}BR place in {scenario['city']}",
            # HARD CONSTRAINT: City
            "target_city": scenario["city"],
            # HARD CONSTRAINT: Budget (max_budget >= rent)
            "budget_per_person_min": 800.0,
            "budget_per_person_max": group_max_budget / scenario["group_size"],
            "max_budget": group_max_budget,
            # HARD CONSTRAINT: Move-in date (after listing available)
            "target_move_in_date": group_move_in_date,
            "move_in_date_start": group_move_in_date,
            "move_in_date_end": (datetime.datetime.now() + datetime.timedelta(days=90)).date().isoformat(),
            "target_group_size": scenario["group_size"],
            "status": "active",
            # HARD CONSTRAINT: Bedrooms
            "target_bedrooms": scenario["bedrooms"],
            # HARD CONSTRAINT: State
            "target_state_province": scenario["state"],
            # HARD CONSTRAINT: Lease type
            "target_lease_type": scenario["lease_type"],
            # Soft constraints
            "target_lease_duration_months": 12 if scenario["lease_type"] == "fixed_term" else None,
            "target_bathrooms": 2.0,
            "target_furnished": True,
            "target_utilities_included": True,
            "target_deposit_amount": 2000.0,
            "target_country": "USA",
            "target_house_rules": "No smoking, no parties"
        }
        
        group_data = sanitize_for_json(group_data)
        
        print(f"\n👥 Creating GROUP: {scenario['group_name']}")
        print(f"   Hard Constraints:")
        print(f"   - City: {scenario['city']}")
        print(f"   - State: {scenario['state']}")
        print(f"   - Max Budget: ${group_max_budget} (Rent: ${scenario['rent']})")
        print(f"   - Bedrooms: {scenario['bedrooms']}")
        print(f"   - Lease Type: {scenario['lease_type']}")
        print(f"   - Move-in: {group_move_in_date} (Listing available: {available_date})")
        
        try:
            response = requests.post(
                "http://127.0.0.1:8000/api/roommate-groups",
                json=group_data,
                headers=headers
            )
            if response.status_code == 200:
                group_result = response.json()["data"]
                group_id = group_result["id"]
                print(f"✅ Group created (ID: {group_id})")
                
                # Add creator as first member
                member_data = {
                    "group_id": group_id,
                    "user_id": creator_user_id,
                    "is_creator": True
                }
                
                requests.post(
                    f"http://127.0.0.1:8000/api/roommate-groups/{group_id}/members",
                    json=member_data,
                    headers=headers
                )
                print(f"✅ Added creator as member")
                
                # Add additional members
                for i in range(scenario["group_size"] - 1):
                    member = users[user_index % len(users)]
                    user_index += 1
                    
                    member_data = {
                        "group_id": group_id,
                        "user_id": member["user_id"],
                        "is_creator": False
                    }
                    
                    requests.post(
                        f"http://127.0.0.1:8000/api/roommate-groups/{group_id}/members",
                        json=member_data,
                        headers=headers
                    )
                print(f"✅ Added {scenario['group_size'] - 1} additional members")
                
            else:
                print(f"❌ Failed to create group: {response.text}")
        except Exception as e:
            print(f"ERROR creating group: {e}")
    
    print("\n" + "="*60)
    print("✅ MATCHING TEST DATA GENERATION COMPLETE")
    print("="*60)

import random
from mimesis import Generic, Address
from mimesis.locales import Locale
import requests
import datetime
from decimal import Decimal

generic = Generic(locale=Locale.EN)
address = Address(Locale.EN)

USER_AMOUNT = 1

# User creation
#####
# =====
# generating users
# =====
#####
def create_users(num):
    """
    Generate and POST multiple fake users to the /api/users endpoint.
    Takes the number of users to create as an argument.
    """

    for i in range(num):
        first_name = generic.person.first_name()
        last_name = generic.person.last_name()
        full_name = f"{first_name} {last_name}"
        email_local = generic.person.email().split('@')[0]
        email = f"{email_local}@gmail.com"
        role = random.choice(['renter', 'host'])

        signup_data = {
            "email": email,
            "full_name": full_name,
            "password": "123456"
        }

        print(f"Creating User {i+1}: {full_name}")

        # Register user in authentication system (which also creates user profile)
        try:
            signup_response = requests.post(
                "http://127.0.0.1:8000/api/auth/signup",
                json=signup_data
            )
            if signup_response.status_code == 200:
                print(f"Auth signup successful ✅")
            else:
                print(f"Auth signup failed: {signup_response.text}")
        except Exception as e:
            print(f"ERROR during auth signup: {e}")

#####
# =====
# authentication helpers
# =====
#####
def get_auth_context(email, password):
    """
    Sign in and return (access_token, host_user_id from profile).
    """

    payload = {
        "email": email,
        "password": password
    }
    response = requests.post("http://127.0.0.1:8000/api/auth/signin", json=payload)
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        host_user_id = None
        try:
            host_user_id = data.get("user", {}).get("profile", {}).get("id")
        except Exception:
            host_user_id = None
        if not host_user_id:
            # Fallback: fetch /api/auth/me to resolve profile id
            headers = {"Authorization": f"Bearer {token}"}
            me_resp = requests.get("http://127.0.0.1:8000/api/auth/me", headers=headers)
            if me_resp.status_code == 200:
                host_user_id = me_resp.json().get("user", {}).get("profile", {}).get("id")
        if not token or not host_user_id:
            print("Failed to resolve auth context (token or host_user_id).")
            return None, None
        return token, host_user_id
    else:
        print(f"Failed to sign in: {response.text}")
        return None, None

# Listing creation
#####
# =====
# generating listings
# =====
#####
def create_listings(num, email, password):
    """
    Generate and POST multiple fake listings to the /api/listings endpoint.
    Takes the number of listings to create and user credentials for authentication.
    """
    token, host_user_id = get_auth_context(email, password)
    if not token or not host_user_id:
        print("No valid auth context. Cannot create listings.")
        return
    headers = {"Authorization": f"Bearer {token}"}

    california_cities = [
        "San Francisco", "Los Angeles", "San Diego", "San Jose", "Sacramento",
        "Oakland", "Fresno", "Long Beach", "Santa Ana", "Anaheim"
    ]


    for i in range(num):
        city = random.choice(california_cities)
        street = address.street_name()
        postal_code = address.zip_code()
        state = "CA"
        address_line_1 = f"{random.randint(100, 9999)} {street}"
        price_per_month = float(random.randint(1200, 5000))
        status = random.choice(['active', 'inactive', 'draft'])
        property_type = random.choice(['entire_place', 'private_room', 'shared_room'])
        lease_type = random.choice(['fixed_term', 'open_ended'])
        title = f"{random.choice(['Spacious', 'Modern', 'Cozy', 'Sunny', 'Affordable'])} {property_type.replace('_', ' ').title()} on {street}, {city}"

        lease_duration_months = random.randint(3, 24) if lease_type == 'fixed_term' else None
        number_of_bedrooms = random.randint(1, 5)
        number_of_bathrooms = round(random.uniform(1, 4), 1)
        area_sqft = random.randint(350, 2200)
        furnished = bool(random.choice([True, False]))
        utilities_included = bool(random.choice([True, False]))
        deposit_amount = float(random.randint(500, 2500))
        country = "USA"
        latitude = round(random.uniform(32.5, 38.5), 8)
        longitude = round(random.uniform(-124.5, -117.0), 8)
        available_from = generic.datetime.date(start=2024, end=2025).isoformat()
        # F*ck date stuff
        # available_to = None
        # if lease_type == 'fixed_term':
        #     avail_dt = datetime.fromisoformat(available_from)
        #     months = lease_duration_months or 12
        #     available_to = (avail_dt + datetime.timedelta(days=30*months)).date().isoformat() # ensure always str or None
        
        amenities = {
            "wifi": bool(random.choice([True, False])),
            "parking": bool(random.choice([True, False])),
            "laundry": random.choice(["in_unit", "on_site", "none"]),
            "air_conditioning": bool(random.choice([True, False])),
            "heating": bool(random.choice([True, False])),
            "dishwasher": bool(random.choice([True, False])),
            "pets_allowed": bool(random.choice([True, False])),
            "gym": bool(random.choice([True, False])),
            "pool": bool(random.choice([True, False]))
        }
        house_rules = random.choice([
            "No smoking. No parties.",
            "Pets allowed with deposit.",
            "Respect quiet hours (10pm-8am)."
        ])

        shared_spaces = random.sample([
            "kitchen", "living_room", "bathroom", "laundry", "yard"
        ], k=random.randint(1, 5))

        # Generate realistic real estate description (move this up before listing_data is built)
        description_templates = [
            "This {property_type} is located in the heart of {city}, offering {feature1} and {feature2}. Perfect for those looking for {target_audience}.",
            "A {property_type} in {city} with {feature1} and {feature2}. Ideal for {target_audience}.",
            "Experience the best of {city} in this {property_type}, featuring {feature1} and {feature2}. Great for {target_audience}."
        ]

        features = ["spacious living areas", "modern appliances", "a private balcony", "a large backyard", "ample storage space", "natural lighting"]
        target_audiences = ["young professionals", "families", "students", "remote workers"]
        description = random.choice(description_templates).format(
            property_type=property_type.replace('_', ' '),
            city=city,
            feature1=random.choice(features),
            feature2=random.choice(features),
            target_audience=random.choice(target_audiences)
        )

        # Ensure all date/datetime fields are ISO strings
        def ensure_iso(val):
            if isinstance(val, (datetime.date, datetime.datetime)):
                return val.isoformat()
            return val

        listing_data = {
            "title": title,
            "description": description,
            "city": city,
            "state_province": state,
            "postal_code": postal_code,
            "address_line_1": str(address_line_1),
            "price_per_month": float(price_per_month),
            "status": status,
            "property_type": property_type,
            "lease_type": lease_type,
            "available_from": ensure_iso(available_from),
            "host_user_id": host_user_id,
            "lease_duration_months": lease_duration_months,
            "number_of_bedrooms": number_of_bedrooms,
            "number_of_bathrooms": number_of_bathrooms,
            "area_sqft": area_sqft,
            "furnished": furnished,
            "utilities_included": utilities_included,
            "deposit_amount": deposit_amount,
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
            # "available_to": ensure_iso(available_to) if available_to else None,
            "amenities": amenities,
            "house_rules": house_rules,
            "shared_spaces": shared_spaces
        }
        sanitized_listing_data = sanitize_for_json(listing_data)
        print("Amenities debug:", [(k, v, type(v)) for k, v in sanitized_listing_data.get("amenities", {}).items()])
        print(f"Listing POST types: {[ (k, type(v)) for k, v in sanitized_listing_data.items() ]}")
        print(f"Creating Listing {i+1}: {title}")
        try:
            response = requests.post(
                "http://127.0.0.1:8000/api/listings",
                json=sanitized_listing_data,
                headers=headers
            )
            if response.status_code == 200:
                print(f"Listing created successfully ✅")
            else:
                print(f"❌ Failed to create Listing: {response.text}")
        except Exception as e:
            print(f"ERROR creating Listing: {e}")

#####
# =====
# data sanitization helpers
# =====
#####
def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif type(obj) is float or type(obj) is int:
        return obj
    elif isinstance(obj, bool) or obj is None:
        return obj
    elif isinstance(obj, str):
        return obj
    else:
        return str(obj)

#####
# =====
# fetching users
# =====
#####
def get_all_users():
    print("Fetching all users from API...")
    response = requests.get("http://127.0.0.1:8000/api/users")
    if response.status_code == 200:
        users = response.json().get("data", [])
        result = []
        for user in users:
            email = user.get("email")
            user_id = user.get("id") or user.get("profile", {}).get("id")
            if email and user_id:
                result.append({"email": email, "user_id": user_id})
        print(f"Fetched {len(result)} users.")
        return result
    else:
        print(f"Failed to fetch users: {response.text}")
        return []


#####
# =====
# generating roommate posts
# =====
#####
def create_roommate_post_for_user(email, password):
    token, user_id = get_auth_context(email, password)
    if not token or not user_id:
        print(f"Skipping {email}: unable to get token or user_id.")
        return
    headers = {"Authorization": f"Bearer {token}"}
    
    title = random.choice([
        "Looking for Roommate in", "Seeking Roommate for", "Need Housemate -", "Searching for Roommates:"])
    city = random.choice([
        "San Francisco", "Los Angeles", "San Diego", "San Jose", "Sacramento",
        "Oakland", "Fresno", "Long Beach", "Santa Ana", "Anaheim"
    ])
    full_title = f"{title} {city}"
    description = random.choice([
        "Responsible, clean, and friendly. Prefer a quiet environment.",
        "Working professional seeking fun, social housemate.",
        "Student looking to share an apartment near {city}.",
        "Love pets and outdoor activities. Looking for like-minded roommate!"
    ]).replace("{city}", city)
    preferred_neighborhoods = random.sample([
        "Downtown", "Mission", "Uptown", "Chinatown", "Lakeview", "Sunset", "Hollywood", "Belmont"
    ], k=random.randint(1, 2)) if random.random() < 0.6 else None
    budget_min = float(random.randint(600, 1200))
    budget_max = budget_min + float(random.randint(200, 1200))
    move_in_date = (datetime.datetime.now() + datetime.timedelta(days=random.randint(7, 120))).date().isoformat()
    lease_duration_months = random.choice([6, 9, 12, None])
    looking_for_property_type = random.choice(["entire_place", "private_room", "shared_room", None])
    looking_for_roommates = random.choice([True, False])
    preferred_roommate_count = random.choice([1, 2, 3, 4, None])
    status = random.choice(["active", "inactive", "matched"])

    post_data = {
        "title": full_title,
        "description": description,
        "target_city": city,
        "preferred_neighborhoods": preferred_neighborhoods,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "move_in_date": move_in_date,
        "lease_duration_months": lease_duration_months,
        "looking_for_property_type": looking_for_property_type,
        "looking_for_roommates": looking_for_roommates,
        "preferred_roommate_count": preferred_roommate_count,
        "user_id": user_id,
        "status": status
    }
    print(f"Creating roommate post for {email} ...")
    def sanitize_for_json(obj):
        if isinstance(obj, dict):
            return {k: sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_for_json(v) for v in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        else:
            return obj
    post_data = sanitize_for_json(post_data)
    response = requests.post("http://127.0.0.1:8000/api/roommate-posts", json=post_data, headers=headers)
    if response.status_code == 200:
        print(f"Roommate post created for {email} ✅")
    else:
        print(f"Failed to create roommate post for {email}: {response.text}")


#####
# =====
# batch roommate post generation
# =====
#####
def generate_roommate_posts(password="123456"):
    users = get_all_users()
    for user in users:
        email = user["email"]
        create_roommate_post_for_user(email, password)

# =====
# main script entry
# =====

# === Main script entry: Generate matching test data ===
if __name__ == "__main__":
    print("="*60)
    print("GREEDY ALGORITHM TEST DATA GENERATOR")
    print("Creating matching listings and groups with exact hard constraints")
    print("="*60)
    
    # 1. Create users first (if needed)
    users = get_all_users()
    if len(users) < 15:
        print(f"\nCreating {15 - len(users)} users...")
        create_users(15 - len(users))
    
    # 2. Generate matching listings and groups
    generate_matching_listings_and_groups()