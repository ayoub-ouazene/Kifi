"""Environment-backed OAuth configuration helpers."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class OAuthConfig:
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: str | None = os.getenv("GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = os.getenv("GOOGLE_REDIRECT_URI")
    meta_app_id: str | None = os.getenv("META_APP_ID")
    meta_app_secret: str | None = os.getenv("META_APP_SECRET")
    meta_redirect_uri: str | None = os.getenv("META_REDIRECT_URI")


settings = OAuthConfig()
