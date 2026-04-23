from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserProfileRead(BaseModel):
    id: str
    display_name: str
    bio: str
    avatar_url: str | None
    is_public: bool
    follower_count: int
    following_count: int
    created_at_public: bool
    serendipity_enabled: bool = False
    thought_count: int
    cluster_count: int
    top_clusters: list[str]
    notification_prefs: dict = Field(default_factory=dict)
    onboarding_v2_completed: bool = False
    created_at: datetime | None = None


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)
    is_public: bool | None = None
    created_at_public: bool | None = None


class UserSearchResult(BaseModel):
    id: str
    display_name: str
    bio: str
    avatar_url: str | None
    follower_count: int
    following_count: int
    top_clusters: list[str]
    relationship_following: bool = False


class NotificationPreferencesUpdate(BaseModel):
    email_weekly_report: bool | None = None
    email_new_follower: bool | None = None
    push_replies: bool | None = None
    push_insights: bool | None = None
    push_influence_updates: bool | None = None
    push_new_follower: bool | None = None
    push_weekly_report: bool | None = None


class NotificationPreferencesRead(BaseModel):
    notification_prefs: dict = Field(default_factory=dict)


class ThoughtVisibilityUpdate(BaseModel):
    visibility: str = Field(pattern="^(public|private)$")


class OnboardingStateUpdate(BaseModel):
    completed: bool


class OnboardingStateRead(BaseModel):
    completed: bool


class DiscoverySettingsUpdate(BaseModel):
    serendipity_enabled: bool


class DiscoverySettingsRead(BaseModel):
    serendipity_enabled: bool
