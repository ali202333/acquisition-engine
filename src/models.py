"""Pydantic models for the acquisition engine."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class BusinessDiscovery(BaseModel):
    """Raw business data discovered via Google Maps."""

    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    categories: list[str] = Field(default_factory=list)
    place_id: str
    has_website: bool = False
    has_social_media: bool = False


class SEOAudit(BaseModel):
    """Website SEO / UX audit results."""

    has_ssl: bool = False
    mobile_friendly: bool = False
    page_speed_score: Optional[int] = None
    meta_description_present: bool = False
    has_contact_page: bool = False
    has_menu_online: bool = False
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0)


class SocialMediaAudit(BaseModel):
    """Social media presence audit."""

    instagram_handle: Optional[str] = None
    facebook_url: Optional[str] = None
    follower_count_estimate: Optional[int] = None
    last_post_date: Optional[datetime] = None
    engagement_estimate: Optional[str] = None
    platforms_found: list[str] = Field(default_factory=list)


class PainPoint(BaseModel):
    """A specific pain point identified for a business."""

    category: str = Field(
        ...,
        description="One of: no_website, poor_seo, no_menu, no_booking, low_social_media",
    )
    description: str
    severity: int = Field(..., ge=1, le=5)
    evidence: str

    @field_validator("category")
    @classmethod
    def _valid_category(cls, value: str) -> str:
        allowed = {"no_website", "poor_seo", "no_menu", "no_booking", "low_social_media"}
        if value not in allowed:
            raise ValueError(f"category must be one of {allowed}, got {value}")
        return value


class BusinessProfile(BaseModel):
    """Complete business profile with audits and pain points."""

    business: BusinessDiscovery
    seo: SEOAudit = Field(default_factory=SEOAudit)
    social: SocialMediaAudit = Field(default_factory=SocialMediaAudit)
    pain_points: list[PainPoint] = Field(default_factory=list)
    priority_score: float = Field(default=0.0, ge=0.0)


class DigitalStrategy(BaseModel):
    """AI-generated digital strategy for a business."""

    recommendations: list[str] = Field(default_factory=list)
    estimated_impact: str = ""
    proposed_services: list[str] = Field(default_factory=list)
    timeline: str = ""
    pricing_estimate_myr: float = Field(default=0.0, ge=0.0)


class OutreachPackage(BaseModel):
    """Final deliverables for outreach."""

    business_name: str
    proposal_md: str = ""
    email_subject: str = ""
    email_body: str = ""
    whatsapp_message: str = ""
    pdf_path: str = ""
