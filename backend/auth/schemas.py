"""Pydantic schemas shared by OAuth providers and application routes."""

from typing import Literal

from pydantic import BaseModel, Field


class OAuthUserProfile(BaseModel):
    """Normalized identity data returned by a supported OAuth provider.

    Attributes:
        provider: Provider identifier, either ``"google"`` or ``"meta"``.
        provider_user_id: Stable provider-issued user identifier. Google maps
            its ``sub`` claim here; Meta maps its ``id`` field here.
        email: Provider email address when available. Meta may omit this value.
        name: Provider display name when available.
        avatar_url: Provider-hosted profile image URL when available.
    """

    provider: Literal["google", "meta"] = Field(
        description="OAuth provider identifier: 'google' or 'meta'."
    )
    provider_user_id: str = Field(
        description="Stable provider user ID (Google sub or Meta id)."
    )
    email: str | None = Field(
        default=None, description="Provider email address, if available."
    )
    name: str | None = Field(default=None, description="Provider display name, if available.")
    avatar_url: str | None = Field(
        default=None, description="Profile image URL, if available."
    )
