"""
Database Schemas for Property Sale Website

Each Pydantic model represents a collection in MongoDB. The collection name
is the lowercase of the class name, e.g. Property -> "property".

These schemas are returned by the /schema endpoint and used for validation.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

# Admin user for logging into the admin panel
class AdminUser(BaseModel):
    email: EmailStr = Field(..., description="Admin email")
    password_hash: str = Field(..., description="BCrypt password hash")
    name: Optional[str] = Field(None, description="Display name")
    is_active: bool = Field(True, description="Active status")

# Site-wide settings editable by admin
class SiteSettings(BaseModel):
    site_name: str = Field(..., description="Website name")
    hero_headline: str = Field(..., description="Homepage hero headline")
    hero_subtitle: Optional[str] = Field(None, description="Homepage hero subtitle")
    contact_email: Optional[EmailStr] = Field(None, description="Contact email shown on site")
    phone: Optional[str] = Field(None, description="Contact phone")

# Property listed for sale
class Property(BaseModel):
    title: str = Field(..., description="Property title")
    description: Optional[str] = Field(None, description="Property description")
    price: float = Field(..., ge=0, description="Listing price in USD")
    address: str = Field(..., description="Street address")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State/Region")
    country: str = Field(..., description="Country")
    bedrooms: Optional[int] = Field(None, ge=0, description="Bedrooms")
    bathrooms: Optional[float] = Field(None, ge=0, description="Bathrooms")
    square_feet: Optional[int] = Field(None, ge=0, description="Area in sqft")
    images: List[str] = Field(default_factory=list, description="Image URLs")
    status: str = Field("available", description="available | pending | sold")
    featured: bool = Field(False, description="Showcase on homepage")
    listed_at: Optional[datetime] = Field(None, description="When listed")

# Offers made on properties
class Offer(BaseModel):
    property_id: str = Field(..., description="Related property _id as string")
    buyer_name: str = Field(..., description="Buyer full name")
    buyer_email: EmailStr = Field(..., description="Buyer email")
    amount: float = Field(..., ge=0, description="Offer amount in USD")
    message: Optional[str] = Field(None, description="Optional message")
    status: str = Field("pending", description="pending | accepted | rejected")
