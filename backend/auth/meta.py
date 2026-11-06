from urllib.parse import urlencode

import httpx

from .exceptions import TokenExchangeError
from .schemas import OAuthUserProfile


class MetaOAuth:
    """Framework-agnostic Meta (Facebook) OAuth 2.0 client."""

    authorization_url = "https://www.facebook.com/v20.0/dialog/oauth"
    token_url = "https://graph.facebook.com/v20.0/oauth/access_token"
    profile_url = "https://graph.facebook.com/v20.0/me"

    def __init__(self, app_id: str, app_secret: str, redirect_uri: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri

    def get_login_url(self, state: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "email,public_profile",
            "response_type": "code",
        }
        return f"{self.authorization_url}?{urlencode(params)}"

    async def get_user_profile(self, code: str) -> OAuthUserProfile:
        async with httpx.AsyncClient() as client:
            token_response = await client.get(
                self.token_url,
                params={
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
            )
            if token_response.status_code != 200:
                raise TokenExchangeError(
                    f"Meta token exchange failed: HTTP {token_response.status_code}"
                )
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise TokenExchangeError("Meta token response did not include access_token")

            profile_response = await client.get(
                self.profile_url,
                params={"fields": "id,name,email,picture.type(large)"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_response.status_code != 200:
                raise TokenExchangeError(
                    f"Meta profile request failed: HTTP {profile_response.status_code}"
                )
            profile = profile_response.json()

        picture = profile.get("picture") or {}
        picture_data = picture.get("data") or {}
        return OAuthUserProfile(
            provider="meta",
            provider_user_id=profile["id"],
            email=profile.get("email"),
            name=profile.get("name"),
            avatar_url=picture_data.get("url"),
        )
