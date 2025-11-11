"""
Pydantic models for request/response validation
These models match the database schema and provide type safety
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    """User role types"""
    RENTER = "renter"
    HOST = "host"
    ADMIN = "admin"


class VerificationStatus(str, Enum):
    """User verification status"""
    UNVERIFIED = "unverified"
    EMAIL_VERIFIED = "email_verified"
    ADMIN_VERIFIED = "admin_verified"


class VerificationType(str, Enum):
    """Type of verification"""
    SCHOOL = "school"
    COMPANY = "company"


class ListingStatus(str, Enum):
    """Listing status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class LeaseType(str, Enum):
    """Lease type"""
    FIXED_TERM = "fixed_term"
    OPEN_ENDED = "open_ended"


class PropertyType(str, Enum):
    """Property type"""
    ENTIRE_PLACE = "entire_place"
    PRIVATE_ROOM = "private_room"
    SHARED_ROOM = "shared_room"


class PostStatus(str, Enum):
    """Roommate post status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MATCHED = "matched"


# ============================================================================
# USER MODELS
# ============================================================================

class UserBase(BaseModel):
    """Base user model with common fields"""
    email: EmailStr
    full_name: str
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    role: UserRole = UserRole.RENTER
    company_name: Optional[str] = None
    school_name: Optional[str] = None
    role_title: Optional[str] = None


class UserCreate(UserBase):
    """Model for creating a new user"""
    auth_id: Optional[str] = None  # From Supabase Auth


class UserUpdate(BaseModel):
    """Model for updating user information"""
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    company_name: Optional[str] = None
    school_name: Optional[str] = None
    role_title: Optional[str] = None
    role: Optional[UserRole] = None

    model_config = ConfigDict(extra='forbid')


class UserResponse(UserBase):
    """Model for user response"""
    id: str
    auth_id: Optional[str] = None
    verification_status: VerificationStatus
    verification_type: Optional[VerificationType] = None
    verified_email: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_active_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# PREFERENCE ENUMS
# ============================================================================

class CleanlinessLevel(str, Enum):
    """Cleanliness preferences"""
    VERY_CLEAN = "very_clean"
    MODERATELY_CLEAN = "moderately_clean"
    RELAXED = "relaxed"


class NoiseLevel(str, Enum):
    """Noise level preferences"""
    VERY_QUIET = "very_quiet"
    QUIET = "quiet"
    MODERATE = "moderate"
    LIVELY = "lively"


class SocialLevel(str, Enum):
    """Social interaction preferences"""
    PRIVATE = "private"
    OCCASIONALLY_SOCIAL = "occasionally_social"
    SOCIAL = "social"
    VERY_SOCIAL = "very_social"


class GuestPolicy(str, Enum):
    """Guest frequency preferences"""
    NO_GUESTS = "no_guests"
    RARELY = "rarely"
    OCCASIONALLY = "occasionally"
    FREQUENTLY = "frequently"


class WorkSchedule(str, Enum):
    """Work schedule types"""
    TRADITIONAL_9_TO_5 = "traditional_9_to_5"
    REMOTE = "remote"
    NIGHT_SHIFT = "night_shift"
    FLEXIBLE = "flexible"
    STUDENT = "student"


class SleepSchedule(str, Enum):
    """Sleep schedule preferences"""
    EARLY_BIRD = "early_bird"
    AVERAGE = "average"
    NIGHT_OWL = "night_owl"


class CookingFrequency(str, Enum):
    """Cooking frequency"""
    DAILY = "daily"
    OFTEN = "often"
    OCCASIONALLY = "occasionally"
    RARELY = "rarely"


class TemperaturePreference(str, Enum):
    """Temperature preferences"""
    COOL = "cool"
    MODERATE = "moderate"
    WARM = "warm"


# ============================================================================
# PERSONAL PREFERENCES MODELS
# ============================================================================

class HousingPreferences(BaseModel):
    """Housing/Property hard and soft constraints"""
    # Hard Constraints
    lease_type: Optional[LeaseType] = None
    move_in_date: Optional[date] = None
    move_out_date: Optional[date] = None
    min_bedrooms: Optional[int] = None
    max_bedrooms: Optional[int] = None
    min_bathrooms: Optional[Decimal] = None
    furnished_required: Optional[bool] = None
    pets_allowed: Optional[bool] = None
    smoking_allowed: Optional[bool] = None
    parking_required: Optional[bool] = None
    accessibility_required: Optional[bool] = None
    
    # Soft Constraints (Amenities & Features)
    laundry_in_unit: Optional[bool] = None
    laundry_in_building: Optional[bool] = None
    dishwasher: Optional[bool] = None
    air_conditioning: Optional[bool] = None
    heating: Optional[bool] = None
    outdoor_space: Optional[bool] = None  # balcony, patio, yard
    gym_access: Optional[bool] = None
    pool_access: Optional[bool] = None
    storage_space: Optional[bool] = None
    high_speed_internet: Optional[bool] = None
    utilities_included: Optional[bool] = None


class RoommatePreferences(BaseModel):
    """Roommate compatibility preferences"""
    # Demographics
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    gender_preference: Optional[str] = None  # "male", "female", "any", "non-binary"
    occupation_types: Optional[List[str]] = None  # ["student", "professional", "remote_worker"]
    
    # Lifestyle Compatibility
    cleanliness_level: Optional[CleanlinessLevel] = None
    noise_tolerance: Optional[NoiseLevel] = None
    social_preference: Optional[SocialLevel] = None
    guest_policy: Optional[GuestPolicy] = None
    work_schedule: Optional[WorkSchedule] = None
    sleep_schedule: Optional[SleepSchedule] = None
    cooking_frequency: Optional[CookingFrequency] = None
    temperature_preference: Optional[TemperaturePreference] = None
    
    # Substance & Lifestyle
    smoking_ok: Optional[bool] = None
    alcohol_ok: Optional[bool] = None
    pets_ok: Optional[bool] = None
    has_pets: Optional[bool] = None
    pet_types: Optional[List[str]] = None  # ["dog", "cat", "other"]
    
    # Diet & Values
    dietary_preferences: Optional[List[str]] = None  # ["vegetarian", "vegan", "halal", "kosher"]
    languages_spoken: Optional[List[str]] = None
    lgbtq_friendly: Optional[bool] = None


class PersonalPreferencesBase(BaseModel):
    """Base personal preferences model with comprehensive filters"""
    # Basic Search Parameters
    target_city: Optional[str] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    # preferred_neighborhoods: Removed - not used in current implementation
    
    # Housing Preferences
    housing_preferences: Optional[HousingPreferences] = None
    
    # Roommate Preferences
    roommate_preferences: Optional[RoommatePreferences] = None
    
    # Legacy field for backward compatibility
    lifestyle_preferences: Optional[dict] = None


class PersonalPreferencesCreate(PersonalPreferencesBase):
    """Model for creating personal preferences"""
    user_id: str


class PersonalPreferencesUpdate(PersonalPreferencesBase):
    """Model for updating personal preferences"""
    model_config = ConfigDict(extra='forbid')


class PersonalPreferencesResponse(PersonalPreferencesBase):
    """Model for personal preferences response"""
    user_id: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# LISTING MODELS
# ============================================================================

class ListingBase(BaseModel):
    """Base listing model"""
    title: str
    description: str
    property_type: PropertyType
    lease_type: LeaseType
    lease_duration_months: Optional[int] = None
    number_of_bedrooms: Optional[int] = None
    number_of_bathrooms: Optional[Decimal] = None
    area_sqft: Optional[int] = None
    furnished: bool = False
    price_per_month: Decimal
    utilities_included: bool = False
    deposit_amount: Optional[Decimal] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: str
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "USA"
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    available_from: date
    available_to: Optional[date] = None
    amenities: Optional[dict] = None
    house_rules: Optional[str] = None
    shared_spaces: Optional[List[str]] = None


class ListingCreate(ListingBase):
    """Model for creating a new listing"""
    host_user_id: str
    status: ListingStatus = ListingStatus.DRAFT


class ListingUpdate(BaseModel):
    """Model for updating a listing"""
    title: Optional[str] = None
    description: Optional[str] = None
    property_type: Optional[PropertyType] = None
    lease_type: Optional[LeaseType] = None
    lease_duration_months: Optional[int] = None
    number_of_bedrooms: Optional[int] = None
    number_of_bathrooms: Optional[Decimal] = None
    area_sqft: Optional[int] = None
    furnished: Optional[bool] = None
    price_per_month: Optional[Decimal] = None
    utilities_included: Optional[bool] = None
    deposit_amount: Optional[Decimal] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    available_from: Optional[date] = None
    available_to: Optional[date] = None
    amenities: Optional[dict] = None
    house_rules: Optional[str] = None
    shared_spaces: Optional[List[str]] = None
    status: Optional[ListingStatus] = None

    model_config = ConfigDict(extra='forbid')


class ListingResponse(ListingBase):
    """Model for listing response"""
    id: str
    host_user_id: str
    status: ListingStatus
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# LISTING PHOTOS MODELS
# ============================================================================

class ListingPhotoBase(BaseModel):
    """Base listing photo model"""
    photo_url: str
    caption: Optional[str] = None
    sort_order: int = 0


class ListingPhotoCreate(ListingPhotoBase):
    """Model for creating a listing photo"""
    listing_id: str


class ListingPhotoResponse(ListingPhotoBase):
    """Model for listing photo response"""
    id: str
    listing_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ROOMMATE POST MODELS
# ============================================================================

class RoommatePostBase(BaseModel):
    """Base roommate post model"""
    title: str
    description: str
    target_city: str
    preferred_neighborhoods: Optional[List[str]] = None
    budget_min: Decimal
    budget_max: Decimal
    move_in_date: date
    lease_duration_months: Optional[int] = None
    looking_for_property_type: Optional[PropertyType] = None
    looking_for_roommates: bool = True
    preferred_roommate_count: Optional[int] = None


class RoommatePostCreate(RoommatePostBase):
    """Model for creating a roommate post"""
    user_id: str
    status: PostStatus = PostStatus.ACTIVE


class RoommatePostUpdate(BaseModel):
    """Model for updating a roommate post"""
    title: Optional[str] = None
    description: Optional[str] = None
    target_city: Optional[str] = None
    preferred_neighborhoods: Optional[List[str]] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    move_in_date: Optional[date] = None
    lease_duration_months: Optional[int] = None
    looking_for_property_type: Optional[PropertyType] = None
    looking_for_roommates: Optional[bool] = None
    preferred_roommate_count: Optional[int] = None
    status: Optional[PostStatus] = None

    model_config = ConfigDict(extra='forbid')


class RoommatePostResponse(RoommatePostBase):
    """Model for roommate post response"""
    id: str
    user_id: str
    status: PostStatus
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ROOMMATE GROUP MODELS
# ============================================================================

class RoommateGroupBase(BaseModel):
    """Base roommate group model"""
    group_name: str
    description: Optional[str] = None
    target_city: str
    budget_per_person_min: Optional[Decimal] = None
    budget_per_person_max: Optional[Decimal] = None
    target_move_in_date: Optional[date] = None
    target_group_size: int = 2
    
    # Housing preferences for the group
    target_lease_duration_months: Optional[int] = None
    target_bedrooms: Optional[int] = None
    target_bathrooms: Optional[Decimal] = None
    target_furnished: Optional[bool] = None
    target_utilities_included: Optional[bool] = None
    target_deposit_amount: Optional[Decimal] = None
    target_state_province: Optional[str] = None
    target_country: Optional[str] = None
    target_house_rules: Optional[str] = None
    target_lease_type: Optional[LeaseType] = None


class RoommateGroupCreate(RoommateGroupBase):
    """Model for creating a roommate group"""
    creator_user_id: str
    status: PostStatus = PostStatus.ACTIVE


class RoommateGroupUpdate(BaseModel):
    """Model for updating a roommate group"""
    group_name: Optional[str] = None
    description: Optional[str] = None
    target_city: Optional[str] = None
    budget_per_person_min: Optional[Decimal] = None
    budget_per_person_max: Optional[Decimal] = None
    target_move_in_date: Optional[date] = None
    target_group_size: Optional[int] = None
    status: Optional[PostStatus] = None
    
    # Housing preferences for the group
    target_lease_duration_months: Optional[int] = None
    target_bedrooms: Optional[int] = None
    target_bathrooms: Optional[Decimal] = None
    target_furnished: Optional[bool] = None
    target_utilities_included: Optional[bool] = None
    target_deposit_amount: Optional[Decimal] = None
    target_state_province: Optional[str] = None
    target_country: Optional[str] = None
    target_house_rules: Optional[str] = None
    target_lease_type: Optional[LeaseType] = None

    model_config = ConfigDict(extra='forbid')


class RoommateGroupResponse(RoommateGroupBase):
    """Model for roommate group response"""
    id: str
    creator_user_id: str
    status: PostStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# GROUP MEMBER MODELS
# ============================================================================

class GroupMemberBase(BaseModel):
    """Base group member model"""
    group_id: str
    user_id: str
    is_creator: bool = False


class GroupMemberCreate(GroupMemberBase):
    """Model for adding a member to a group"""
    pass


class GroupMemberResponse(GroupMemberBase):
    """Model for group member response"""
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# RESPONSE WRAPPERS
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response"""
    status: str = "success"
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    status: str = "error"
    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    status: str = "success"
    count: int
    page: int = 1
    page_size: int = 20
    total_pages: int
    data: List[dict]
