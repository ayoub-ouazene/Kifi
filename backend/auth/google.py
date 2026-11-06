from urllib.parse import urlencode

import httpx

from .exceptions import TokenExchangeError
from .schemas import OAuthUserProfile


class GoogleOAuth:
    """Framework-agnostic Google OAuth 2.0 client."""

    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_login_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account",
            "state": state,
        }
        return f"{self.authorization_url}?{urlencode(params)}"

    async def get_user_profile(self, code: str) -> OAuthUserProfile:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                self.token_url,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                raise TokenExchangeError(
                    f"Google token exchange failed: HTTP {token_response.status_code}"
                )
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise TokenExchangeError("Google token response did not include access_token")

            profile_response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_response.status_code != 200:
                raise TokenExchangeError(
                    f"Google profile request failed: HTTP {profile_response.status_code}"
                )
            profile = profile_response.json()

        return OAuthUserProfile(
            provider="google",
            provider_user_id=profile["sub"],
            email=profile.get("email"),
            name=profile.get("name"),
            avatar_url=profile.get("picture"),
        )
