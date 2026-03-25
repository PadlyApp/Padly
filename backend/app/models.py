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


# NOTE: Preference enums removed - they were defined for a more complex
# preference structure that doesn't exist in the current database.
# The database uses a simple JSONB field (lifestyle_preferences) for flexibility.


# ============================================================================
# PERSONAL PREFERENCES MODELS
# ============================================================================
# NOTE: These models match the actual database schema.
# The database stores preferences in a simple structure with lifestyle_preferences as JSONB.

class PersonalPreferencesBase(BaseModel):
    """Base personal preferences model matching database schema"""
    # Frontend hard constraints (Preferences page source-of-truth).
    target_country: Optional[str] = None  # ISO alpha-2 code (US/CA)
    target_city: Optional[str] = None
    target_state_province: Optional[str] = None
    budget_min: Optional[float] = None  # Accept float from frontend
    budget_max: Optional[float] = None  # Accept float from frontend
    required_bedrooms: Optional[int] = None
    target_bathrooms: Optional[float] = None  # Accept float from frontend
    target_deposit_amount: Optional[float] = None  # Accept float from frontend
    furnished_preference: Optional[str] = None  # required | preferred | no_preference
    gender_policy: Optional[str] = None  # same_gender_only | mixed_ok
    move_in_date: Optional[str] = None  # Accept ISO string from frontend
    target_lease_type: Optional[str] = None
    target_lease_duration_months: Optional[int] = None

    # Frontend soft constraints.
    target_house_rules: Optional[str] = None
    preferred_neighborhoods: Optional[list] = None  # Array field
    lifestyle_preferences: Optional[dict] = None  # JSONB field for flexible preferences
    
    # Legacy compatibility fields (not directly edited by current frontend form).
    target_furnished: Optional[bool] = None
    target_utilities_included: Optional[bool] = None
    
    model_config = ConfigDict(extra='forbid')


class PersonalPreferencesCreate(PersonalPreferencesBase):
    """Model for creating personal preferences"""
    user_id: str


class PersonalPreferencesUpdate(PersonalPreferencesBase):
    """Model for updating personal preferences - inherits forbid config"""
    pass


class PersonalPreferencesResponse(PersonalPreferencesBase):
    """Model for personal preferences response"""
    user_id: str
    updated_at: Optional[datetime] = None

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
    target_country: Optional[str] = None
    target_state_province: Optional[str] = None
    target_city: str

    # Keep legacy + personal-aligned naming in sync at API level.
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    budget_per_person_min: Optional[Decimal] = None
    budget_per_person_max: Optional[Decimal] = None

    move_in_date: Optional[date] = None
    target_move_in_date: Optional[date] = None
    target_group_size: int = 2

    # Personal-aligned hard/soft fields
    required_bedrooms: Optional[int] = None
    target_bedrooms: Optional[int] = None
    target_bathrooms: Optional[Decimal] = None
    target_deposit_amount: Optional[Decimal] = None
    furnished_preference: Optional[str] = None  # required | preferred | no_preference
    target_furnished: Optional[bool] = None
    furnished_is_hard: Optional[bool] = None
    target_utilities_included: Optional[bool] = None
    gender_policy: Optional[str] = None  # same_gender_only | mixed_ok
    target_lease_type: Optional[str] = None
    target_lease_duration_months: Optional[int] = None
    target_house_rules: Optional[str] = None
    preferred_neighborhoods: Optional[List[str]] = None
    lifestyle_preferences: Optional[dict] = None


class RoommateGroupCreate(RoommateGroupBase):
    """Model for creating a roommate group"""
    creator_user_id: Optional[str] = None  # Made optional - set by endpoint
    status: PostStatus = PostStatus.ACTIVE


class RoommateGroupUpdate(BaseModel):
    """Model for updating a roommate group"""
    group_name: Optional[str] = None
    description: Optional[str] = None
    target_country: Optional[str] = None
    target_state_province: Optional[str] = None
    target_city: Optional[str] = None

    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    budget_per_person_min: Optional[Decimal] = None
    budget_per_person_max: Optional[Decimal] = None

    move_in_date: Optional[date] = None
    target_move_in_date: Optional[date] = None
    target_group_size: Optional[int] = None
    required_bedrooms: Optional[int] = None
    target_bedrooms: Optional[int] = None
    target_bathrooms: Optional[Decimal] = None
    target_deposit_amount: Optional[Decimal] = None
    furnished_preference: Optional[str] = None
    target_furnished: Optional[bool] = None
    furnished_is_hard: Optional[bool] = None
    target_utilities_included: Optional[bool] = None
    gender_policy: Optional[str] = None
    target_lease_type: Optional[str] = None
    target_lease_duration_months: Optional[int] = None
    target_house_rules: Optional[str] = None
    preferred_neighborhoods: Optional[List[str]] = None
    lifestyle_preferences: Optional[dict] = None
    status: Optional[PostStatus] = None

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
