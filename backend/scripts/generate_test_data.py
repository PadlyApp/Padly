#####
# =====
# generating preferences
# =====
#####
def generate_preferences_for_all_users():
    users = get_all_users()
    for user in users:
        user_id = user["user_id"]
        preferred_city = random.choice([
            "San Francisco", "Los Angeles", "San Diego", "San Jose", "Sacramento",
            "Oakland", "Fresno", "Long Beach", "Santa Ana", "Anaheim"
        ])
        preferred_property_type = random.choice(["entire_place", "private_room", "shared_room"])
        budget_min = float(random.randint(800, 1800))
        budget_max = budget_min + float(random.randint(200, 1200))
        pet_policy = random.choice(["allowed", "not_allowed"])
        smoking_policy = random.choice(["allowed", "not_allowed"])
        amenities = random.sample([
            "wifi", "parking", "laundry", "air_conditioning", "heating", "dishwasher", "gym", "pool"
        ], k=random.randint(2, 5))
        roommate_gender_preference = random.choice(["any", "male", "female", None])
        lease_length = random.choice([6, 12, 18, 24])
        preferences_data = {
            "user_id": user_id,
            "preferred_city": preferred_city,
            "preferred_property_type": preferred_property_type,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "pet_policy": pet_policy,
            "smoking_policy": smoking_policy,
            "amenities": amenities,
            "roommate_gender_preference": roommate_gender_preference,
            "lease_length": lease_length
        }
        print(f"Creating preferences for user {user_id} ...")
        response = requests.post("http://127.0.0.1:8000/api/preferences", json=preferences_data)
        if response.status_code == 200:
            print(f"Preferences created for user {user_id} ✅")
        else:
            print(f"Failed to create preferences for user {user_id}: {response.text}")

#####
# =====
# generating reviews 
# TODO NEED to implement reviews for this to work
# =====
#####
def generate_reviews_for_all_users():
    users = get_all_users()
    for reviewer in users:
        reviewer_id = reviewer["user_id"]
        # Each user reviews 2 random other users
        review_targets = random.sample([u for u in users if u["user_id"] != reviewer_id], k=min(2, len(users)-1))
        for target in review_targets:
            target_id = target["user_id"]
            rating = random.randint(1, 5)
            review_text = random.choice([
                "Great experience!", "Would recommend.", "Very clean and friendly.", "Had some issues, but resolved.", "Not as expected.", "Awesome roommate!"
            ])
            review_date = datetime.datetime.now().isoformat()
            review_data = {
                "reviewer_user_id": reviewer_id,
                "target_user_id": target_id,
                "rating": rating,
                "review_text": review_text,
                "date": review_date
            }
            print(f"Creating review from {reviewer_id} to {target_id} ...")
            response = requests.post("http://127.0.0.1:8000/api/reviews", json=review_data)
            if response.status_code == 200:
                print(f"Review created from {reviewer_id} to {target_id} ✅")
            else:
                print(f"Failed to create review from {reviewer_id} to {target_id}: {response.text}")
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

# === Main script entry: Generate all mock data ===
if __name__ == "__main__":
    # 1. Create users
    create_users(10)  # Adjust number as needed

    # 2. Create listings for each user
    users = get_all_users()
    for user in users:
        create_listings(2, user["email"], "123456")  # 2 listings per user

    # 3. Create preferences for all users
    generate_preferences_for_all_users()

    # 4. Create roommate posts for all users
    generate_roommate_posts()

    # Note: Review generation is disabled (endpoint not implemented)