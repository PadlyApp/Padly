# 📊 Padly Database Fields - Complete Reference

## Overview
This document provides a comprehensive reference of all database tables and their fields in the Padly platform.

---

## 🧑 **1. USERS Table**
**Purpose**: Core user profiles for all platform members

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | uuid | ✅ | auto | Primary key |
| `auth_id` | uuid | ❌ | - | Supabase Auth ID (unique) |
| `email` | text | ✅ | - | User email (unique) |
| `full_name` | text | ✅ | - | User's full name |
| `bio` | text | ❌ | - | User biography |
| `profile_picture_url` | text | ❌ | - | Profile photo URL |
| `role` | enum | ✅ | 'renter' | renter, host, admin |
| `company_name` | text | ❌ | - | Current company |
| `school_name` | text | ❌ | - | Current school |
| `role_title` | text | ❌ | - | Job/student title |
| `verification_status` | enum | ✅ | 'unverified' | unverified, email_verified, admin_verified |
| `verification_type` | enum | ❌ | - | school, company |
| `verified_email` | text | ❌ | - | Email used for verification |
| `verified_at` | timestamp | ❌ | - | When verified |
| `created_at` | timestamp | ✅ | now() | Account creation time |
| `updated_at` | timestamp | ✅ | now() | Last profile update |
| `last_active_at` | timestamp | ❌ | now() | Last activity timestamp |

---

## 🏠 **2. LISTINGS Table**
**Purpose**: Housing listings posted by hosts

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | uuid | ✅ | auto | Primary key |
| `host_user_id` | uuid | ✅ | - | FK to users (host) |
| `status` | enum | ✅ | 'draft' | active, inactive, draft |
| `title` | text | ✅ | - | Listing title |
| `description` | text | ✅ | - | Full description |
| `property_type` | enum | ✅ | - | entire_place, private_room, shared_room |
| `lease_type` | enum | ✅ | - | fixed_term, open_ended |
| `lease_duration_months` | integer | ❌ | - | e.g., 12, 6, 3 |
| `number_of_bedrooms` | integer | ❌ | - | Number of bedrooms |
| `number_of_bathrooms` | numeric | ❌ | - | e.g., 1.5, 2.0 |
| `area_sqft` | integer | ❌ | - | Square footage |
| `furnished` | boolean | ❌ | false | Is furnished? |
| `price_per_month` | numeric | ✅ | - | Monthly rent |
| `utilities_included` | boolean | ❌ | false | Utilities in rent? |
| `deposit_amount` | numeric | ❌ | - | Security deposit |
| `address_line_1` | text | ❌ | - | Street address |
| `address_line_2` | text | ❌ | - | Apt/Unit number |
| `city` | text | ✅ | - | City name |
| `state_province` | text | ❌ | - | State/Province |
| `postal_code` | text | ❌ | - | ZIP/Postal code |
| `country` | text | ❌ | 'USA' | Country |
| `latitude` | numeric | ❌ | - | GPS latitude |
| `longitude` | numeric | ❌ | - | GPS longitude |
| `available_from` | date | ✅ | - | Move-in date |
| `available_to` | date | ❌ | - | End availability (null = open) |
| `amenities` | jsonb | ❌ | - | {"wifi": true, "laundry": true, ...} |
| `house_rules` | text | ❌ | - | House rules text |
| `shared_spaces` | array | ❌ | - | ["kitchen", "living room", ...] |
| `view_count` | integer | ❌ | 0 | View tracking |
| `created_at` | timestamp | ✅ | now() | Created timestamp |
| `updated_at` | timestamp | ✅ | now() | Last updated |
| `accepts_groups` | boolean | ❌ | true | Accepts roommate groups? |
| `max_occupancy` | integer | ❌ | - | Maximum occupants |

**Common Amenities (JSONB)**:
```json
{
  "wifi": true,
  "laundry_in_unit": false,
  "laundry_in_building": true,
  "dishwasher": true,
  "air_conditioning": true,
  "heating": true,
  "parking": true,
  "gym": false,
  "pool": false,
  "pets_allowed": false
}
```

---

## 📸 **3. LISTING_PHOTOS Table**
**Purpose**: Photos for listings

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | uuid | ✅ | auto | Primary key |
| `listing_id` | uuid | ✅ | - | FK to listings |
| `photo_url` | text | ✅ | - | Image URL |
| `caption` | text | ❌ | - | Photo caption |
| `sort_order` | integer | ❌ | 0 | Display order |
| `created_at` | timestamp | ✅ | now() | Upload time |

---

## 👥 **4. ROOMMATE_GROUPS Table**
**Purpose**: Groups of users looking for housing together

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | uuid | ✅ | auto | Primary key |
| `creator_user_id` | uuid | ✅ | - | FK to users (creator) |
| `group_name` | text | ✅ | - | Group name |
| `description` | text | ❌ | - | Group description |
| `target_city` | text | ✅ | - | Target city |
| `budget_per_person_min` | numeric | ❌ | - | Min budget per person |
| `budget_per_person_max` | numeric | ❌ | - | Max budget per person |
| `target_move_in_date` | date | ❌ | - | Desired move-in date |
| `target_group_size` | integer | ✅ | 2 | Group size (2 for stable matching) |
| `status` | enum | ✅ | 'active' | active, inactive, matched |
| `created_at` | timestamp | ✅ | now() | Created time |
| `updated_at` | timestamp | ✅ | now() | Updated time |
| `target_lease_duration_months` | integer | ❌ | - | Desired lease length |
| `target_bedrooms` | integer | ❌ | - | Desired bedrooms |
| `target_bathrooms` | numeric | ❌ | - | Desired bathrooms |
| `target_furnished` | boolean | ❌ | false | Want furnished? |
| `target_utilities_included` | boolean | ❌ | false | Want utilities included? |
| `target_deposit_amount` | numeric | ❌ | - | Max deposit willing to pay |
| `target_state_province` | text | ❌ | - | Target state |
| `target_country` | text | ❌ | 'USA' | Target country |
| `target_house_rules` | text | ❌ | - | Preferred house rules |
| `target_lease_type` | enum | ❌ | - | fixed_term, open_ended |

---

## 🤝 **5. GROUP_MEMBERS Table**
**Purpose**: Junction table linking users to groups

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `group_id` | uuid | ✅ | - | FK to roommate_groups (PK) |
| `user_id` | uuid | ✅ | - | FK to users (PK) |
| `is_creator` | boolean | ❌ | false | Is group creator? |
| `joined_at` | timestamp | ✅ | now() | Join timestamp |
| `status` | varchar | ✅ | 'accepted' | pending, accepted, rejected |

**Composite Primary Key**: (`group_id`, `user_id`)

---

## 📝 **6. ROOMMATE_POSTS Table**
**Purpose**: Individual users advertising themselves to find roommates

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | uuid | ✅ | auto | Primary key |
| `user_id` | uuid | ✅ | - | FK to users |
| `status` | enum | ✅ | 'active' | active, inactive, matched |
| `title` | text | ✅ | - | Post title |
| `description` | text | ✅ | - | Description |
| `target_city` | text | ✅ | - | Target city |
| `preferred_neighborhoods` | array | ❌ | - | ["Mission", "SOMA", ...] |
| `budget_min` | numeric | ✅ | - | Min budget |
| `budget_max` | numeric | ✅ | - | Max budget |
| `move_in_date` | date | ✅ | - | Move-in date |
| `lease_duration_months` | integer | ❌ | - | Desired lease length |
| `looking_for_property_type` | enum | ❌ | - | entire_place, private_room, shared_room |
| `looking_for_roommates` | boolean | ❌ | true | Looking for roommates? |
| `preferred_roommate_count` | integer | ❌ | - | e.g., 1, 2, 3 |
| `view_count` | integer | ❌ | 0 | View tracking |
| `created_at` | timestamp | ✅ | now() | Created time |
| `updated_at` | timestamp | ✅ | now() | Updated time |

---

## ⚙️ **7. PERSONAL_PREFERENCES Table**
**Purpose**: User housing preferences

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `user_id` | uuid | ✅ | - | FK to users (PK) |
| `target_city` | text | ❌ | - | Target city |
| `budget_min` | numeric | ❌ | - | Min budget |
| `budget_max` | numeric | ❌ | - | Max budget |
| `move_in_date` | date | ❌ | - | Move-in date |
| `lifestyle_preferences` | jsonb | ❌ | - | Flexible preferences object |
| `updated_at` | timestamp | ✅ | now() | Last updated |

**Lifestyle Preferences (JSONB)**:
```json
{
  "cleanliness": "very_clean",
  "noise_level": "quiet",
  "guests_frequency": "rarely",
  "smoking": "no_smoking",
  "pets": "no_pets",
  "diet": "vegetarian",
  "work_schedule": "9to5",
  "socialness": "introverted"
}
```

---

## 🎯 **8. STABLE_MATCHES Table**
**Purpose**: Stores results from stable matching algorithm

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | uuid | ✅ | auto | Primary key |
| `diagnostics_id` | uuid | ❌ | - | FK to match_diagnostics |
| `group_id` | text | ✅ | - | ID of matched group |
| `listing_id` | text | ✅ | - | ID of matched listing |
| `group_score` | numeric | ✅ | - | How much group likes listing (0-100) |
| `listing_score` | numeric | ✅ | - | How much listing likes group (0-100) |
| `group_rank` | integer | ✅ | - | Listing's rank for group (1 = top choice) |
| `listing_rank` | integer | ✅ | - | Group's rank for listing (1 = top choice) |
| `matched_at` | timestamp | ✅ | now() | Match timestamp |
| `is_stable` | boolean | ✅ | true | Is a stable match? |
| `status` | text | ✅ | 'active' | active, accepted, rejected, expired |
| `expires_at` | timestamp | ❌ | - | Expiration time |

---

## 📊 **9. MATCH_DIAGNOSTICS Table**
**Purpose**: Analytics and diagnostics for matching runs

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | uuid | ✅ | auto | Primary key |
| `city` | text | ✅ | - | City for this match run |
| `date_window_start` | date | ✅ | - | Start of date window |
| `date_window_end` | date | ✅ | - | End of date window |
| `total_groups` | integer | ✅ | - | Total groups considered |
| `total_listings` | integer | ✅ | - | Total listings considered |
| `feasible_pairs` | integer | ✅ | 0 | Pairs passing hard constraints |
| `matched_groups` | integer | ✅ | - | Groups that got matched |
| `matched_listings` | integer | ✅ | - | Listings that got matched |
| `unmatched_groups` | integer | ✅ | - | Groups without match |
| `unmatched_listings` | integer | ✅ | - | Listings without match |
| `proposals_sent` | integer | ✅ | 0 | Total proposals in DA algorithm |
| `proposals_rejected` | integer | ✅ | 0 | Rejected proposals |
| `iterations` | integer | ✅ | 0 | DA algorithm iterations |
| `avg_group_rank` | numeric | ✅ | 0 | Average rank of matches for groups |
| `avg_listing_rank` | numeric | ✅ | 0 | Average rank of matches for listings |
| `match_quality_score` | numeric | ✅ | 0 | Overall quality metric |
| `is_stable` | boolean | ✅ | false | All matches stable? |
| `stability_check_passed` | boolean | ✅ | false | Stability verified? |
| `executed_at` | timestamp | ✅ | now() | When run executed |

---

## 🔑 **Key Relationships**

```
users (1) ──────→ (many) listings [host_user_id]
users (1) ──────→ (many) roommate_posts [user_id]
users (1) ──────→ (many) roommate_groups [creator_user_id]
users (1) ──────→ (1) personal_preferences [user_id]
users (many) ───→ (many) roommate_groups [via group_members]

listings (1) ───→ (many) listing_photos [listing_id]

roommate_groups (1) ──→ (many) group_members [group_id]

match_diagnostics (1) ──→ (many) stable_matches [diagnostics_id]
```

---

## 📈 **Data Usage in Algorithms**

### **Stable Matching (Groups → Listings)**
**From Groups**:
- `target_city`, `target_state_province`, `target_country` (location matching)
- `budget_per_person_min`, `budget_per_person_max` (price matching)
- `target_move_in_date` (date matching)
- `target_bedrooms`, `target_bathrooms` (preference scoring)
- `target_furnished`, `target_utilities_included` (hard constraints)
- `target_deposit_amount` (deposit scoring)
- `target_house_rules` (rules compatibility)

**From Listings**:
- `city`, `state_province`, `country` (location matching)
- `price_per_month` (price matching)
- `available_from`, `available_to` (date matching)
- `number_of_bedrooms`, `number_of_bathrooms` (eligibility + scoring)
- `property_type` (must be entire_place for groups)
- `furnished`, `utilities_included` (hard constraints)
- `deposit_amount` (deposit scoring)
- `house_rules` (rules compatibility)

### **Individual Matching (Users → Listings)**
**From Personal Preferences**:
- `target_city`, `budget_min`, `budget_max`, `move_in_date`
- `lifestyle_preferences` (for compatibility scoring)

**From Listings**: Same as above

---

## 🎨 **Enums Reference**

**UserRole**: `renter`, `host`, `admin`  
**VerificationStatus**: `unverified`, `email_verified`, `admin_verified`  
**VerificationType**: `school`, `company`  
**ListingStatus**: `active`, `inactive`, `draft`  
**PropertyType**: `entire_place`, `private_room`, `shared_room`  
**LeaseType**: `fixed_term`, `open_ended`  
**PostStatus**: `active`, `inactive`, `matched`  

---

**Generated**: 2025-11-30  
**Total Tables**: 9  
**Total Fields**: ~120+
