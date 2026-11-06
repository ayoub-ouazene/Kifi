import httpx
import pytest
import respx

from auth.exceptions import TokenExchangeError
from auth.google import GoogleOAuth


@pytest.fixture
def google():
    return GoogleOAuth("id", "secret", "https://example.com/callback")


def test_google_login_url(google):
    url = google.get_login_url("state value")
    assert "accounts.google.com/o/oauth2/v2/auth" in url
    assert "scope=openid+email+profile" in url
    assert "state=state+value" in url


@pytest.mark.asyncio
@respx.mock
async def test_google_profile(google):
    respx.post(google.token_url).mock(return_value=httpx.Response(200, json={"access_token": "token"}))
    respx.get(google.userinfo_url).mock(return_value=httpx.Response(200, json={"sub": "1", "email": "a@b.com", "name": "A", "picture": "https://x"}))
    profile = await google.get_user_profile("code")
    assert profile.provider == "google"
    assert profile.provider_user_id == "1"
    assert profile.email == "a@b.com"
    assert profile.avatar_url == "https://x"


@pytest.mark.asyncio
@respx.mock
async def test_google_non_200(google):
    respx.post(google.token_url).mock(return_value=httpx.Response(400))
    with pytest.raises(TokenExchangeError):
        await google.get_user_profile("code")
