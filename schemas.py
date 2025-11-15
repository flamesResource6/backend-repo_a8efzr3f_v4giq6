"""
Database Schemas for Women’s Travel Safety Platform (MVP)

Each Pydantic model represents a MongoDB collection. The collection name
is the lowercase of the class name (e.g., User -> "user").
"""
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

# -------------------------
# Core Collections
# -------------------------

class User(BaseModel):
    """Users collection schema
    Collection name: "user"
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    photo: Optional[str] = Field(None, description="Avatar/photo URL")
    saved_places: List[str] = Field(default_factory=list, description="Saved place IDs")
    saved_cities: List[str] = Field(default_factory=list, description="Saved city names")


class Place(BaseModel):
    """Places collection schema
    Collection name: "place"
    """
    name: str = Field(..., description="Place name")
    city: str = Field(..., description="City name")
    type: str = Field(..., description="Type: hotel | restaurant | neighborhood")
    safety_score: float = Field(3.5, ge=0, le=5, description="Safety score 0-5")
    description: str = Field(..., description="Short 150-character safety description")
    main_tags: List[str] = Field(default_factory=list, description="Key safety tags")


class Review(BaseModel):
    """Reviews collection schema
    Collection name: "review"
    """
    user_id: str = Field(..., description="Reviewer user ID")
    place_id: str = Field(..., description="Reviewed place ID")
    rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    safety_tags: List[str] = Field(default_factory=list, description="Selected safety tags")
    comment: Optional[str] = Field(None, description="Free-text feedback")
    night_safe: bool = Field(..., description="Was it safe at night?")
    harassment: bool = Field(..., description="Any harassment encountered?")


class QuizResult(BaseModel):
    """Quiz Results collection schema
    Collection name: "quizresult"
    """
    user_id: Optional[str] = Field(None, description="User ID (if logged in)")
    persona: str = Field(..., description="Safety persona label")
    recommendations: List[str] = Field(default_factory=list, description="Recommended safe cities")
    answers: dict = Field(default_factory=dict, description="Raw quiz answers for reference")


# The Flames database viewer can introspect these models via GET /schema
# in the FastAPI app and use them for CRUD operations.
