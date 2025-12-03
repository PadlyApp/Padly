-- ============================================================================
-- PADLY MOCK DATA
-- Realistic sample data for testing and development
-- ============================================================================

-- Note: Run this after your schema is created
-- You may need to adjust UUIDs if they conflict with existing data

-- ============================================================================
-- 1. MOCK USERS
-- ============================================================================

-- Create some mock users (hosts and renters)
INSERT INTO public.users (id, email, full_name, bio, role, company_name, school_name, role_title, verification_status, verification_type, verified_email, created_at, updated_at) VALUES
-- Hosts
('11111111-1111-1111-1111-111111111111', 'sarah.johnson@gmail.com', 'Sarah Johnson', 'Property manager with 5+ years of experience. I love helping students find their perfect home!', 'host', NULL, NULL, 'Property Manager', 'email_verified', 'company', 'sarah.johnson@realtyco.com', NOW() - INTERVAL '6 months', NOW()),
('22222222-2222-2222-2222-222222222222', 'michael.chen@gmail.com', 'Michael Chen', 'Tech professional renting out my spare rooms to fellow interns and young professionals.', 'host', 'Google', NULL, 'Software Engineer', 'email_verified', 'company', 'michael.chen@google.com', NOW() - INTERVAL '4 months', NOW()),
('33333333-3333-3333-3333-333333333333', 'emma.williams@gmail.com', 'Emma Williams', 'Graduate student subletting my apartment while studying abroad.', 'host', NULL, 'Stanford University', 'PhD Student', 'email_verified', 'school', 'emma.williams@stanford.edu', NOW() - INTERVAL '3 months', NOW()),

-- Renters
('44444444-4444-4444-4444-444444444444', 'alex.martinez@gmail.com', 'Alex Martinez', 'Software Engineering intern looking for housing in SF for summer 2025.', 'renter', 'Meta', NULL, 'Software Engineering Intern', 'email_verified', 'company', 'alex.martinez@meta.com', NOW() - INTERVAL '2 months', NOW()),
('55555555-5555-5555-5555-555555555555', 'jessica.lee@gmail.com', 'Jessica Lee', 'Recent graduate starting my career in tech. Clean, quiet, and responsible.', 'renter', 'Amazon', NULL, 'Product Manager', 'email_verified', 'company', 'jessica.lee@amazon.com', NOW() - INTERVAL '1 month', NOW()),
('66666666-6666-6666-6666-666666666666', 'david.kim@gmail.com', 'David Kim', 'Computer Science student at UC Berkeley looking for affordable housing.', 'renter', NULL, 'UC Berkeley', 'CS Student', 'email_verified', 'school', 'david.kim@berkeley.edu', NOW() - INTERVAL '2 weeks', NOW());


-- ============================================================================
-- 2. MOCK LISTINGS
-- ============================================================================

INSERT INTO public.listings (
    id,
    host_user_id,
    status,
    title,
    description,
    property_type,
    lease_type,
    lease_duration_months,
    number_of_bedrooms,
    number_of_bathrooms,
    area_sqft,
    furnished,
    price_per_month,
    utilities_included,
    deposit_amount,
    address_line_1,
    city,
    state_province,
    postal_code,
    country,
    available_from,
    available_to,
    amenities,
    house_rules,
    shared_spaces,
    created_at,
    updated_at
) VALUES
-- Listing 1: Cozy Studio in Downtown SF
(
    'a0000001-0000-0000-0000-000000000001',
    '11111111-1111-1111-1111-111111111111',
    'active',
    'Cozy Studio in Downtown SF',
    'Beautiful studio apartment in the heart of downtown San Francisco. Perfect for interns and young professionals. Walking distance to BART, shops, and restaurants. The unit features hardwood floors, large windows with great natural light, and a modern kitchen with stainless steel appliances. Building has secure entry and on-site laundry.',
    'entire_place',
    'fixed_term',
    4,
    1,
    1,
    750,
    true,
    2200,
    false,
    2200,
    '123 Market Street, Apt 405',
    'San Francisco',
    'CA',
    '94102',
    'USA',
    '2025-05-01',
    '2025-08-31',
    '{"wifi": true, "laundry": true, "parking": false, "ac": true, "heating": true, "dishwasher": true, "gym": false, "pet_friendly": false}',
    'No smoking, no pets. Quiet hours after 10 PM. Keep common areas clean.',
    ARRAY['lobby', 'laundry room'],
    NOW() - INTERVAL '2 weeks',
    NOW()
),

-- Listing 2: Modern Loft with City Views
(
    'a0000002-0000-0000-0000-000000000002',
    '11111111-1111-1111-1111-111111111111',
    'active',
    'Modern Loft with City Views',
    'Stunning 2-bedroom loft in SOMA with floor-to-ceiling windows and panoramic city views. This spacious unit features an open floor plan, exposed brick, modern kitchen with island, and in-unit washer/dryer. Perfect for roommates or small families. Building amenities include rooftop deck, gym, and bike storage.',
    'entire_place',
    'open_ended',
    NULL,
    2,
    2,
    1200,
    true,
    3800,
    true,
    7600,
    '456 Folsom Street, Unit 8B',
    'San Francisco',
    'CA',
    '94105',
    'USA',
    '2025-06-01',
    NULL,
    '{"wifi": true, "laundry": true, "parking": true, "ac": true, "heating": true, "dishwasher": true, "gym": true, "pet_friendly": true, "rooftop": true, "doorman": true}',
    'No smoking indoors. Pets allowed with deposit. Respect neighbors.',
    ARRAY['gym', 'rooftop deck', 'bike storage', 'lobby'],
    NOW() - INTERVAL '1 week',
    NOW()
),

-- Listing 3: Bright Corner Unit Near Campus
(
    'a0000003-0000-0000-0000-000000000003',
    '33333333-3333-3333-3333-333333333333',
    'active',
    'Bright Corner Unit Near Stanford',
    'Charming 1-bedroom apartment near Stanford University, perfect for grad students or visiting scholars. Corner unit with lots of natural light, updated kitchen and bathroom, and quiet neighborhood. Walking distance to campus and Caltrain. Available for short-term lease while I study abroad.',
    'entire_place',
    'fixed_term',
    6,
    1,
    1,
    850,
    true,
    2400,
    true,
    2400,
    '789 University Avenue, #12',
    'Palo Alto',
    'CA',
    '94301',
    'USA',
    '2025-09-01',
    '2026-02-28',
    '{"wifi": true, "laundry": true, "parking": true, "ac": false, "heating": true, "dishwasher": false, "gym": false, "pet_friendly": false}',
    'No smoking, no pets. Must be affiliated with Stanford.',
    ARRAY['parking lot', 'laundry room'],
    NOW() - INTERVAL '5 days',
    NOW()
),

-- Listing 4: Minimalist Suite in Mission District
(
    'a0000004-0000-0000-0000-000000000004',
    '22222222-2222-2222-2222-222222222222',
    'active',
    'Minimalist Suite in Mission District',
    'Clean, modern private room in a shared 3-bedroom apartment. Perfect for young professionals working in tech. The room comes fully furnished with a queen bed, desk, and closet. Shared spaces include a modern kitchen, living room, and 2 bathrooms. Great location near restaurants, bars, and public transit.',
    'private_room',
    'open_ended',
    NULL,
    1,
    1,
    680,
    true,
    1400,
    true,
    1400,
    '234 Valencia Street, Unit B',
    'San Francisco',
    'CA',
    '94103',
    'USA',
    '2025-07-01',
    NULL,
    '{"wifi": true, "laundry": true, "parking": false, "ac": false, "heating": true, "dishwasher": true, "gym": false, "pet_friendly": false}',
    'Clean up after yourself. No overnight guests more than 2 nights/week. Respectful of others.',
    ARRAY['kitchen', 'living room', 'bathrooms', 'laundry'],
    NOW() - INTERVAL '3 days',
    NOW()
),

-- Listing 5: Urban Living Space in Oakland
(
    'a0000005-0000-0000-0000-000000000005',
    '11111111-1111-1111-1111-111111111111',
    'active',
    'Urban Living Space in Oakland',
    'Spacious 2-bedroom apartment in downtown Oakland. Great for roommates or couples. Features include updated kitchen, hardwood floors, and lots of storage. Close to BART, restaurants, and entertainment. Diverse, vibrant neighborhood with easy access to San Francisco.',
    'entire_place',
    'open_ended',
    NULL,
    2,
    1,
    950,
    false,
    2600,
    false,
    2600,
    '567 Broadway, Apt 304',
    'Oakland',
    'CA',
    '94612',
    'USA',
    '2025-06-15',
    NULL,
    '{"wifi": false, "laundry": true, "parking": true, "ac": false, "heating": true, "dishwasher": false, "gym": false, "pet_friendly": true}',
    'Cats allowed, no dogs. No smoking.',
    ARRAY['parking', 'laundry room'],
    NOW() - INTERVAL '4 days',
    NOW()
),

-- Listing 6: Spacious Industrial Loft
(
    'a0000006-0000-0000-0000-000000000006',
    '22222222-2222-2222-2222-222222222222',
    'active',
    'Spacious Industrial Loft in SOMA',
    'Stunning 3-bedroom industrial loft with high ceilings, exposed brick, and modern finishes. Perfect for a group of young professionals or roommates. Open concept living area, chef''s kitchen, 2 full bathrooms, and in-unit washer/dryer. Building has a rooftop terrace with BBQ and stunning city views.',
    'entire_place',
    'fixed_term',
    12,
    3,
    2,
    1500,
    true,
    4500,
    true,
    9000,
    '890 Brannan Street, #10',
    'San Francisco',
    'CA',
    '94103',
    'USA',
    '2025-08-01',
    '2026-07-31',
    '{"wifi": true, "laundry": true, "parking": true, "ac": true, "heating": true, "dishwasher": true, "gym": true, "pet_friendly": true, "rooftop": true}',
    'No smoking. Pets negotiable. Must maintain cleanliness.',
    ARRAY['rooftop terrace', 'gym', 'bike storage'],
    NOW() - INTERVAL '6 days',
    NOW()
),

-- Listing 7: Affordable Room in Berkeley
(
    'a0000007-0000-0000-0000-000000000007',
    '33333333-3333-3333-3333-333333333333',
    'active',
    'Affordable Room Near UC Berkeley',
    'Private room in a 4-bedroom house shared with other students. Great location near campus, shops, and restaurants. The room is furnished with bed, desk, and storage. Shared kitchen, living room, and 2 bathrooms. Backyard with patio. Perfect for students on a budget.',
    'private_room',
    'fixed_term',
    10,
    1,
    1,
    500,
    true,
    900,
    true,
    900,
    '345 Durant Avenue',
    'Berkeley',
    'CA',
    '94704',
    'USA',
    '2025-08-15',
    '2026-06-15',
    '{"wifi": true, "laundry": true, "parking": false, "ac": false, "heating": true, "dishwasher": false, "gym": false, "pet_friendly": false}',
    'Students only. Keep noise down during finals. Clean shared spaces weekly.',
    ARRAY['kitchen', 'living room', 'bathrooms', 'backyard'],
    NOW() - INTERVAL '1 day',
    NOW()
),

-- Listing 8: Luxury Apartment in Financial District
(
    'a0000008-0000-0000-0000-000000000008',
    '11111111-1111-1111-1111-111111111111',
    'active',
    'Luxury Apartment in Financial District',
    'High-end 1-bedroom apartment in a luxury building in the Financial District. Features include floor-to-ceiling windows, gourmet kitchen, marble bathrooms, and stunning bay views. Building amenities include 24-hour concierge, fitness center, pool, and conference rooms. Walk to work!',
    'entire_place',
    'open_ended',
    NULL,
    1,
    1,
    900,
    true,
    3200,
    false,
    6400,
    '100 Pine Street, Unit 2505',
    'San Francisco',
    'CA',
    '94111',
    'USA',
    '2025-07-01',
    NULL,
    '{"wifi": true, "laundry": true, "parking": true, "ac": true, "heating": true, "dishwasher": true, "gym": true, "pet_friendly": false, "pool": true, "doorman": true, "concierge": true}',
    'No smoking, no pets. Professional tenants only.',
    ARRAY['gym', 'pool', 'conference rooms', 'lounge'],
    NOW() - INTERVAL '2 days',
    NOW()
);


-- ============================================================================
-- 3. LISTING PHOTOS
-- ============================================================================

-- Add photos for listings
INSERT INTO public.listing_photos (listing_id, photo_url, caption, sort_order) VALUES
-- Listing 1 photos
('a0000001-0000-0000-0000-000000000001', 'https://images.unsplash.com/photo-1610123172763-1f587473048f?w=1200', 'Living area with natural light', 0),
('a0000001-0000-0000-0000-000000000001', 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=1200', 'Modern kitchen', 1),
('a0000001-0000-0000-0000-000000000001', 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200', 'Bathroom', 2),

-- Listing 2 photos
('a0000002-0000-0000-0000-000000000002', 'https://images.unsplash.com/photo-1603072388139-565853396b38?w=1200', 'Spacious loft with city views', 0),
('a0000002-0000-0000-0000-000000000002', 'https://images.unsplash.com/photo-1556020685-ae41abfc9365?w=1200', 'Open kitchen', 1),
('a0000002-0000-0000-0000-000000000002', 'https://images.unsplash.com/photo-1540518614846-7eded433c457?w=1200', 'Master bedroom', 2),

-- Listing 3 photos
('a0000003-0000-0000-0000-000000000003', 'https://images.unsplash.com/photo-1632077209523-e9dede9b6b31?w=1200', 'Bright corner unit', 0),
('a0000003-0000-0000-0000-000000000003', 'https://images.unsplash.com/photo-1567767292278-a4f21aa2d36e?w=1200', 'Bedroom', 1),

-- Listing 4 photos
('a0000004-0000-0000-0000-000000000004', 'https://images.unsplash.com/photo-1614622350812-96b09c78af77?w=1200', 'Minimalist bedroom', 0),
('a0000004-0000-0000-0000-000000000004', 'https://images.unsplash.com/photo-1556911220-bff31c812dba?w=1200', 'Shared living space', 1),

-- Listing 5 photos
('a0000005-0000-0000-0000-000000000005', 'https://images.unsplash.com/photo-1552189864-e05b02af1697?w=1200', 'Urban apartment living room', 0),
('a0000005-0000-0000-0000-000000000005', 'https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1200', 'Kitchen area', 1),

-- Listing 6 photos
('a0000006-0000-0000-0000-000000000006', 'https://images.unsplash.com/photo-1681684565407-01d2933ed16f?w=1200', 'Industrial loft space', 0),
('a0000006-0000-0000-0000-000000000006', 'https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=1200', 'Exposed brick wall', 1),
('a0000006-0000-0000-0000-000000000006', 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200', 'Rooftop terrace', 2),

-- Listing 7 photos
('a0000007-0000-0000-0000-000000000007', 'https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?w=1200', 'Cozy bedroom', 0),

-- Listing 8 photos
('a0000008-0000-0000-0000-000000000008', 'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=1200', 'Luxury apartment with views', 0),
('a0000008-0000-0000-0000-000000000008', 'https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=1200', 'Gourmet kitchen', 1);


-- ============================================================================
-- 4. ROOMMATE POSTS
-- ============================================================================

INSERT INTO public.roommate_posts (
    id,
    user_id,
    status,
    title,
    description,
    target_city,
    preferred_neighborhoods,
    budget_min,
    budget_max,
    move_in_date,
    lease_duration_months,
    looking_for_property_type,
    looking_for_roommates,
    preferred_roommate_count,
    created_at,
    updated_at
) VALUES
(
    'b0000001-0000-0000-0000-000000000001',
    '44444444-4444-4444-4444-444444444444',
    'active',
    'Meta Intern Seeking Summer Housing',
    'Hey! I''m Alex, a software engineering intern at Meta for summer 2025. Looking for a place in SF, preferably with other interns or young professionals. I''m clean, respectful, and social. Love hiking, cooking, and exploring the city on weekends.',
    'San Francisco',
    ARRAY['Mission District', 'SOMA', 'Castro', 'Hayes Valley'],
    1200,
    2000,
    '2025-05-15',
    4,
    'private_room',
    true,
    2,
    NOW() - INTERVAL '5 days',
    NOW()
),
(
    'b0000002-0000-0000-0000-000000000002',
    '55555555-5555-5555-5555-555555555555',
    'active',
    'Amazon PM Looking for Roommate',
    'Recent grad starting as a Product Manager at Amazon. Looking for a roommate to share a 2BR apartment. I work normal hours, keep things clean, and enjoy occasional social activities. Prefer someone also working in tech who understands the startup/tech lifestyle.',
    'San Francisco',
    ARRAY['Marina', 'Pacific Heights', 'Russian Hill'],
    1800,
    2500,
    '2025-06-01',
    12,
    'entire_place',
    true,
    1,
    NOW() - INTERVAL '3 days',
    NOW()
),
(
    'b0000003-0000-0000-0000-000000000003',
    '66666666-6666-6666-6666-666666666666',
    'active',
    'Berkeley Student Seeking Housing',
    'CS student at UC Berkeley looking for affordable housing near campus. Quiet, focused on studies, but friendly. Non-smoker, no pets. Prefer living with other students. Can move in anytime over summer.',
    'Berkeley',
    ARRAY['Southside', 'Downtown Berkeley', 'Northside'],
    800,
    1200,
    '2025-08-01',
    10,
    'private_room',
    true,
    3,
    NOW() - INTERVAL '1 day',
    NOW()
);


-- ============================================================================
-- 5. PERSONAL PREFERENCES
-- ============================================================================

INSERT INTO public.personal_preferences (
    user_id,
    target_city,
    budget_min,
    budget_max,
    move_in_date,
    lifestyle_preferences,
    preferred_neighborhoods,
    updated_at
) VALUES
(
    '44444444-4444-4444-4444-444444444444',
    'San Francisco',
    1200,
    2000,
    '2025-05-15',
    '{"cleanliness": "moderate", "noise_level": "moderate", "guests": "occasionally", "pets": "no", "smoking": "no", "work_schedule": "9-5"}',
    ARRAY['Mission District', 'SOMA', 'Castro'],
    NOW()
),
(
    '55555555-5555-5555-5555-555555555555',
    'San Francisco',
    1800,
    2500,
    '2025-06-01',
    '{"cleanliness": "very_clean", "noise_level": "quiet", "guests": "rarely", "pets": "no", "smoking": "no", "work_schedule": "flexible"}',
    ARRAY['Marina', 'Pacific Heights'],
    NOW()
),
(
    '66666666-6666-6666-6666-666666666666',
    'Berkeley',
    800,
    1200,
    '2025-08-01',
    '{"cleanliness": "moderate", "noise_level": "quiet", "guests": "rarely", "pets": "no", "smoking": "no", "work_schedule": "student"}',
    ARRAY['Southside', 'Downtown Berkeley'],
    NOW()
);


-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- After running the inserts, you can verify the data with these queries:

-- Count all listings
-- SELECT COUNT(*) as total_listings FROM public.listings;

-- View all active listings with host info
-- SELECT l.title, l.city, l.price_per_month, u.full_name as host_name 
-- FROM public.listings l 
-- JOIN public.users u ON l.host_user_id = u.id 
-- WHERE l.status = 'active'
-- ORDER BY l.created_at DESC;

-- View listings with photos
-- SELECT l.title, COUNT(p.id) as photo_count 
-- FROM public.listings l 
-- LEFT JOIN public.listing_photos p ON l.id = p.listing_id 
-- GROUP BY l.id, l.title;

-- View roommate posts with user info
-- SELECT rp.title, rp.target_city, rp.budget_min, rp.budget_max, u.full_name, u.company_name
-- FROM public.roommate_posts rp
-- JOIN public.users u ON rp.user_id = u.id
-- WHERE rp.status = 'active';

