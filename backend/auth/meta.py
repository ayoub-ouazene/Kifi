"""Meta (Facebook) OAuth 2.0 authorization-code client."""

from urllib.parse import urlencode

import httpx

from .exceptions import TokenExchangeError
from .schemas import OAuthUserProfile


class MetaOAuth:
    """Framework-agnostic Meta (Facebook) OAuth 2.0 client.

    Args:
        app_id: Meta application ID.
        app_secret: Meta application secret.
        redirect_uri: Callback URI registered for the Meta application.

    Attributes:
        authorization_url: Meta authorization endpoint.
        token_url: Meta access-token endpoint.
        profile_url: Meta Graph API profile endpoint.
    """

    authorization_url = "https://www.facebook.com/v20.0/dialog/oauth"
    token_url = "https://graph.facebook.com/v20.0/oauth/access_token"
    profile_url = "https://graph.facebook.com/v20.0/me"

    def __init__(self, app_id: str, app_secret: str, redirect_uri: str) -> None:
        """Initialize a Meta OAuth client.

        Args:
            app_id: Meta application ID.
            app_secret: Meta application secret.
            redirect_uri: Registered callback URI.
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri

    def get_login_url(self, state: str) -> str:
        """Build the Meta authorization URL.

        Args:
            state: Application-generated CSRF state value.

        Returns:
            URL-encoded Meta authorization endpoint URL.
        """
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "email,public_profile",
            "response_type": "code",
        }
        return f"{self.authorization_url}?{urlencode(params)}"

    async def get_user_profile(self, code: str) -> OAuthUserProfile:
        """Exchange a Meta authorization code and fetch the user profile.

        Args:
            code: Single-use authorization code from the callback request.

        Returns:
            Normalized profile containing Meta ``id``, optional email, name,
            and large profile picture URL.

        Raises:
            TokenExchangeError: If token exchange, profile retrieval, or the
                provider response is unsuccessful.
        """
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
