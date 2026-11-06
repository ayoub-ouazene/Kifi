"""Environment-backed OAuth configuration helpers."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class OAuthConfig:
    """Optional OAuth settings loaded from environment variables.

    Attributes:
        google_client_id: Google OAuth client ID.
        google_client_secret: Google OAuth client secret.
        google_redirect_uri: Google callback URI.
        meta_app_id: Meta application ID.
        meta_app_secret: Meta application secret.
        meta_redirect_uri: Meta callback URI.
    """
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: str | None = os.getenv("GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = os.getenv("GOOGLE_REDIRECT_URI")
    meta_app_id: str | None = os.getenv("META_APP_ID")
    meta_app_secret: str | None = os.getenv("META_APP_SECRET")
    meta_redirect_uri: str | None = os.getenv("META_REDIRECT_URI")


settings = OAuthConfig()
