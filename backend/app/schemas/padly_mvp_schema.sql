-- ============================================================================
-- Padly MVP Database Schema for Supabase (PostgreSQL)
-- Minimal viable product - Core features only
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "cube";           -- Required for earthdistance
CREATE EXTENSION IF NOT EXISTS "earthdistance";  -- Required for ll_to_earth

-- ============================================================================
-- ENUMS
-- ============================================================================

-- User roles
CREATE TYPE user_role AS ENUM ('renter', 'host', 'admin');

-- Verification status
CREATE TYPE verification_status AS ENUM ('unverified', 'email_verified', 'admin_verified');

-- Verification type
CREATE TYPE verification_type AS ENUM ('school', 'company');

-- Listing status
CREATE TYPE listing_status AS ENUM ('active', 'inactive', 'draft');

-- Lease type
CREATE TYPE lease_type AS ENUM ('fixed_term', 'open_ended');

-- Property type
CREATE TYPE property_type AS ENUM ('entire_place', 'private_room', 'shared_room');

-- Roommate post status
CREATE TYPE post_status AS ENUM ('active', 'inactive', 'matched');

-- ============================================================================
-- TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) Users (Core identity)
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Authentication (synced with Supabase Auth)
    auth_id UUID UNIQUE, -- References auth.users(id)
    email TEXT UNIQUE NOT NULL,
    
    -- Profile
    full_name TEXT NOT NULL,
    bio TEXT,
    profile_picture_url TEXT,
    
    -- Role
    role user_role NOT NULL DEFAULT 'renter',
    
    -- Professional/Academic Context
    company_name TEXT,
    school_name TEXT,
    role_title TEXT, -- e.g., "Software Engineer Intern"
    
    -- Verification
    verification_status verification_status NOT NULL DEFAULT 'unverified',
    verification_type verification_type,
    verified_email TEXT, -- The actual verified email (e.g., user@stanford.edu)
    verified_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE users IS 'Core user profiles for renters, hosts, and admins';
COMMENT ON COLUMN users.verified_email IS 'The school or company email used for verification';

-- ----------------------------------------------------------------------------
-- 2) Personal Preferences (Housing needs and lifestyle)
-- ----------------------------------------------------------------------------
CREATE TABLE personal_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    
    -- Housing Search Parameters
    target_city TEXT,
    budget_min DECIMAL(10, 2),
    budget_max DECIMAL(10, 2),
    move_in_date DATE,
    
    -- Lifestyle Preferences (JSONB for flexibility)
    -- Example: {
    --   "cleanliness": "very_clean",
    --   "noise_level": "quiet",
    --   "social_level": "occasionally_social",
    --   "pets": false,
    --   "smoking": false,
    --   "overnight_guests": "rarely",
    --   "work_schedule": "9_to_5"
    -- }
    lifestyle_preferences JSONB,
    
    -- Additional preferences
    preferred_neighborhoods TEXT[], -- Array of neighborhood names
    
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE personal_preferences IS 'Housing needs and lifestyle preferences for renters';

-- ----------------------------------------------------------------------------
-- 3) Listings (Housing offerings from hosts)
-- ----------------------------------------------------------------------------
CREATE TABLE listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    host_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Status
    status listing_status NOT NULL DEFAULT 'draft',
    
    -- Basic Information
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    property_type property_type NOT NULL,
    
    -- Lease Information
    lease_type lease_type NOT NULL,
    lease_duration_months INTEGER, -- NULL for open_ended, value for fixed_term
    
    -- Property Details
    number_of_bedrooms INTEGER,
    number_of_bathrooms DECIMAL(3, 1), -- Supports 1.5, 2.5 baths
    area_sqft INTEGER,
    furnished BOOLEAN DEFAULT FALSE,
    
    -- Pricing
    price_per_month DECIMAL(10, 2) NOT NULL,
    utilities_included BOOLEAN DEFAULT FALSE,
    deposit_amount DECIMAL(10, 2),
    
    -- Location
    address_line_1 TEXT,
    address_line_2 TEXT,
    city TEXT NOT NULL,
    state_province TEXT,
    postal_code TEXT,
    country TEXT DEFAULT 'USA',
    
    -- Geolocation (for maps)
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Availability
    available_from DATE NOT NULL,
    available_to DATE, -- NULL for open-ended
    
    -- Amenities (JSONB for flexibility)
    -- Example: {
    --   "wifi": true,
    --   "parking": true,
    --   "laundry": "in_unit",
    --   "air_conditioning": true,
    --   "heating": true,
    --   "dishwasher": true,
    --   "pets_allowed": false,
    --   "gym": false,
    --   "pool": false
    -- }
    amenities JSONB,
    
    -- Additional Details
    house_rules TEXT,
    shared_spaces TEXT[], -- e.g., ['kitchen', 'living_room', 'bathroom']
    
    -- Engagement Metrics
    view_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE listings IS 'Housing listings from hosts (landlords or subletters)';
COMMENT ON COLUMN listings.lease_duration_months IS 'Duration in months for fixed-term leases, NULL for open-ended';

-- ----------------------------------------------------------------------------
-- 4) Listing Photos
-- ----------------------------------------------------------------------------
CREATE TABLE listing_photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    photo_url TEXT NOT NULL,
    caption TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE listing_photos IS 'Photos associated with listings';

-- ----------------------------------------------------------------------------
-- 5) Roommate Posts (Users advertising themselves)
-- ----------------------------------------------------------------------------
CREATE TABLE roommate_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Status
    status post_status NOT NULL DEFAULT 'active',
    
    -- Title and Description
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    
    -- Housing Preferences
    target_city TEXT NOT NULL,
    preferred_neighborhoods TEXT[],
    budget_min DECIMAL(10, 2) NOT NULL,
    budget_max DECIMAL(10, 2) NOT NULL,
    move_in_date DATE NOT NULL,
    lease_duration_months INTEGER, -- Preferred duration
    
    -- What they're looking for
    looking_for_property_type property_type,
    looking_for_roommates BOOLEAN DEFAULT TRUE, -- True if looking to share with others
    preferred_roommate_count INTEGER, -- How many roommates they want
    
    -- Engagement Metrics
    view_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE roommate_posts IS 'Posts from renters advertising themselves to find housing or roommates';

-- ----------------------------------------------------------------------------
-- 6) Roommate Groups (Users teaming up to find housing together)
-- ----------------------------------------------------------------------------
CREATE TABLE roommate_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    creator_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Group Info
    group_name TEXT NOT NULL,
    description TEXT,
    
    -- Housing Search Parameters
    target_city TEXT NOT NULL,
    budget_per_person_min DECIMAL(10, 2),
    budget_per_person_max DECIMAL(10, 2),
    target_move_in_date DATE,
    target_group_size INTEGER NOT NULL DEFAULT 2,
    
    -- Status
    status post_status NOT NULL DEFAULT 'active',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE roommate_groups IS 'Groups of renters coordinating to find housing together';

-- ----------------------------------------------------------------------------
-- 7) Group Members
-- ----------------------------------------------------------------------------
CREATE TABLE group_members (
    group_id UUID NOT NULL REFERENCES roommate_groups(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_creator BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (group_id, user_id)
);

COMMENT ON TABLE group_members IS 'Members of roommate groups';

-- ============================================================================
-- INDEXES (Optimized for common queries)
-- ============================================================================

-- Users
CREATE INDEX idx_users_verification ON users(verification_status, verification_type);
CREATE INDEX idx_users_company ON users(company_name) WHERE company_name IS NOT NULL;
CREATE INDEX idx_users_school ON users(school_name) WHERE school_name IS NOT NULL;
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- Personal Preferences
CREATE INDEX idx_prefs_city_budget ON personal_preferences(target_city, budget_min, budget_max);
CREATE INDEX idx_prefs_move_in ON personal_preferences(move_in_date) WHERE move_in_date IS NOT NULL;

-- Listings
CREATE INDEX idx_listings_status_city ON listings(status, city) WHERE status = 'active';
CREATE INDEX idx_listings_price ON listings(price_per_month);
CREATE INDEX idx_listings_dates ON listings(available_from, available_to);
CREATE INDEX idx_listings_property_type ON listings(property_type);
CREATE INDEX idx_listings_lease_type ON listings(lease_type);
CREATE INDEX idx_listings_host ON listings(host_user_id);
CREATE INDEX idx_listings_created ON listings(created_at DESC);

-- Geospatial index for map searches (using earthdistance extension)
CREATE INDEX idx_listings_location
ON listings
USING GIST (ll_to_earth(latitude::double precision, longitude::double precision))
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Listing Photos
CREATE INDEX idx_photos_listing ON listing_photos(listing_id, sort_order);

-- Roommate Posts
CREATE INDEX idx_posts_status_city ON roommate_posts(status, target_city) WHERE status = 'active';
CREATE INDEX idx_posts_budget ON roommate_posts(budget_min, budget_max);
CREATE INDEX idx_posts_move_in ON roommate_posts(move_in_date);
CREATE INDEX idx_posts_user ON roommate_posts(user_id);
CREATE INDEX idx_posts_created ON roommate_posts(created_at DESC);

-- Roommate Groups
CREATE INDEX idx_groups_status_city ON roommate_groups(status, target_city);
CREATE INDEX idx_groups_creator ON roommate_groups(creator_user_id);
CREATE INDEX idx_groups_move_in ON roommate_groups(target_move_in_date);

-- Group Members
CREATE INDEX idx_group_members_user ON group_members(user_id);

-- ============================================================================
-- TRIGGERS (Automatic timestamp updates)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
CREATE TRIGGER update_users_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_personal_preferences_timestamp
    BEFORE UPDATE ON personal_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_listings_timestamp
    BEFORE UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_roommate_posts_timestamp
    BEFORE UPDATE ON roommate_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_roommate_groups_timestamp
    BEFORE UPDATE ON roommate_groups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE personal_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE listing_photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE roommate_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE roommate_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- Users Policies
-- ----------------------------------------------------------------------------

-- Everyone can view public profiles
CREATE POLICY "Public profiles viewable" 
    ON users FOR SELECT 
    USING (true);

-- Users can update their own profile
CREATE POLICY "Users can update own profile" 
    ON users FOR UPDATE 
    USING (auth.uid() = auth_id)
    WITH CHECK (auth.uid() = auth_id);

-- Users can insert their own profile (for initial setup)
CREATE POLICY "Users can create own profile"
    ON users FOR INSERT
    WITH CHECK (auth.uid() = auth_id);

-- ----------------------------------------------------------------------------
-- Personal Preferences Policies
-- ----------------------------------------------------------------------------

-- Users can view their own preferences
CREATE POLICY "Users view own preferences" 
    ON personal_preferences FOR SELECT 
    USING (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

-- Users can insert their own preferences
CREATE POLICY "Users insert own preferences"
    ON personal_preferences FOR INSERT
    WITH CHECK (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

-- Users can update their own preferences
CREATE POLICY "Users update own preferences"
    ON personal_preferences FOR UPDATE
    USING (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id))
    WITH CHECK (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

-- Users can delete their own preferences
CREATE POLICY "Users delete own preferences"
    ON personal_preferences FOR DELETE
    USING (auth.uid() = (SELECT auth_id FROM users WHERE id = user_id));

-- ----------------------------------------------------------------------------
-- Listings Policies
-- ----------------------------------------------------------------------------

-- Everyone can view active listings
CREATE POLICY "Active listings viewable" 
    ON listings FOR SELECT 
    USING (
        status = 'active' 
        OR host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Hosts can create listings
CREATE POLICY "Hosts create listings"
    ON listings FOR INSERT
    WITH CHECK (
        host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Hosts can update their own listings (with WITH CHECK)
CREATE POLICY "Hosts update own listings"
    ON listings FOR UPDATE
    USING (
        host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    )
    WITH CHECK (
        host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Hosts can delete their own listings
CREATE POLICY "Hosts delete own listings"
    ON listings FOR DELETE
    USING (
        host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- ----------------------------------------------------------------------------
-- Listing Photos Policies
-- ----------------------------------------------------------------------------

-- Photos viewable if listing is viewable
CREATE POLICY "Photos viewable with listing" 
    ON listing_photos FOR SELECT 
    USING (
        EXISTS (
            SELECT 1 FROM listings 
            WHERE listings.id = listing_photos.listing_id 
            AND (
                listings.status = 'active' 
                OR listings.host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
            )
        )
    );

-- Listing owners can manage photos (with WITH CHECK for ALL)
CREATE POLICY "Hosts manage listing photos"
    ON listing_photos FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM listings 
            WHERE listings.id = listing_photos.listing_id 
            AND listings.host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM listings 
            WHERE listings.id = listing_photos.listing_id 
            AND listings.host_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
        )
    );

-- ----------------------------------------------------------------------------
-- Roommate Posts Policies
-- ----------------------------------------------------------------------------

-- Everyone can view active posts
CREATE POLICY "Active posts viewable" 
    ON roommate_posts FOR SELECT 
    USING (
        status = 'active' 
        OR user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Users can create their own posts
CREATE POLICY "Users create own posts"
    ON roommate_posts FOR INSERT
    WITH CHECK (
        user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Users can update their own posts (with WITH CHECK)
CREATE POLICY "Users update own posts"
    ON roommate_posts FOR UPDATE
    USING (
        user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    )
    WITH CHECK (
        user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Users can delete their own posts
CREATE POLICY "Users delete own posts"
    ON roommate_posts FOR DELETE
    USING (
        user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- ----------------------------------------------------------------------------
-- Roommate Groups Policies
-- ----------------------------------------------------------------------------

-- Everyone can view active groups
CREATE POLICY "Groups viewable" 
    ON roommate_groups FOR SELECT 
    USING (true);

-- Users can create groups
CREATE POLICY "Users create groups"
    ON roommate_groups FOR INSERT
    WITH CHECK (
        creator_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Creators can update their groups (with WITH CHECK)
CREATE POLICY "Creators update groups"
    ON roommate_groups FOR UPDATE
    USING (
        creator_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    )
    WITH CHECK (
        creator_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Creators can delete their groups
CREATE POLICY "Creators delete groups"
    ON roommate_groups FOR DELETE
    USING (
        creator_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- ----------------------------------------------------------------------------
-- Group Members Policies
-- ----------------------------------------------------------------------------

-- Everyone can view group members
CREATE POLICY "Group members viewable" 
    ON group_members FOR SELECT 
    USING (true);

-- Users can join groups
CREATE POLICY "Users join groups"
    ON group_members FOR INSERT
    WITH CHECK (
        user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- Group creators can remove members, or users can leave themselves
CREATE POLICY "Creators manage members"
    ON group_members FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM roommate_groups 
            WHERE roommate_groups.id = group_members.group_id 
            AND roommate_groups.creator_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
        )
        OR user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- Active verified renters directory
CREATE VIEW verified_renters AS
SELECT 
    u.id,
    u.full_name,
    u.profile_picture_url,
    u.company_name,
    u.school_name,
    u.role_title,
    u.verification_status,
    u.verification_type,
    pp.target_city,
    pp.budget_min,
    pp.budget_max,
    pp.move_in_date,
    pp.lifestyle_preferences,
    u.created_at
FROM users u
LEFT JOIN personal_preferences pp ON u.id = pp.user_id
WHERE u.role = 'renter'
AND u.verification_status IN ('email_verified', 'admin_verified');

COMMENT ON VIEW verified_renters IS 'Directory of verified renters with their preferences';

-- Active listings with host info
CREATE VIEW active_listings_view AS
SELECT 
    l.*,
    u.full_name as host_name,
    u.company_name as host_company,
    u.school_name as host_school,
    u.verification_status as host_verification,
    COALESCE(photo_count.count, 0) as photo_count
FROM listings l
JOIN users u ON l.host_user_id = u.id
LEFT JOIN (
    SELECT listing_id, COUNT(*) as count
    FROM listing_photos
    GROUP BY listing_id
) photo_count ON l.id = photo_count.listing_id
WHERE l.status = 'active';

COMMENT ON VIEW active_listings_view IS 'Active listings with host details and photo counts';

-- Active roommate posts with user info
CREATE VIEW active_roommate_posts_view AS
SELECT 
    rp.*,
    u.full_name,
    u.profile_picture_url,
    u.company_name,
    u.school_name,
    u.role_title,
    u.verification_status,
    pp.lifestyle_preferences
FROM roommate_posts rp
JOIN users u ON rp.user_id = u.id
LEFT JOIN personal_preferences pp ON u.id = pp.user_id
WHERE rp.status = 'active';

COMMENT ON VIEW active_roommate_posts_view IS 'Active roommate posts with user details';

-- Active groups with member count
CREATE VIEW active_groups_view AS
SELECT 
    rg.*,
    u.full_name as creator_name,
    u.verification_status as creator_verification,
    COALESCE(member_count.count, 0) as current_member_count
FROM roommate_groups rg
JOIN users u ON rg.creator_user_id = u.id
LEFT JOIN (
    SELECT group_id, COUNT(*) as count
    FROM group_members
    GROUP BY group_id
) member_count ON rg.id = member_count.group_id
WHERE rg.status = 'active';

COMMENT ON VIEW active_groups_view IS 'Active roommate groups with member counts';

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Check if date ranges overlap (for availability matching)
CREATE OR REPLACE FUNCTION date_ranges_overlap(
    start1 DATE,
    end1 DATE,
    start2 DATE,
    end2 DATE
)
RETURNS BOOLEAN AS $$
BEGIN
    IF start1 IS NULL OR start2 IS NULL THEN
        RETURN TRUE;
    END IF;
    
    IF end1 IS NULL AND end2 IS NULL THEN
        RETURN TRUE;
    END IF;
    
    IF end1 IS NULL THEN
        RETURN start1 <= COALESCE(end2, start1);
    END IF;
    
    IF end2 IS NULL THEN
        RETURN start2 <= end1;
    END IF;
    
    RETURN start1 <= end2 AND start2 <= end1;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION date_ranges_overlap IS 'Check if two date ranges overlap, handles NULL (open-ended) dates';

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================