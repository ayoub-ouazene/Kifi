import httpx
import pytest
import respx
from auth.exceptions import TokenExchangeError
from auth.meta import MetaOAuth


@pytest.fixture
def meta():
    return MetaOAuth("id", "secret", "https://example.com/callback")


def test_meta_login_url(meta):
    url = meta.get_login_url("state value")
    assert "facebook.com/v20.0/dialog/oauth" in url
    assert "scope=email%2Cpublic_profile" in url
    assert "state=state+value" in url


@pytest.mark.asyncio
@respx.mock
async def test_meta_profile(meta):
    respx.get(meta.token_url).mock(return_value=httpx.Response(200, json={"access_token": "token"}))
    respx.get(meta.profile_url).mock(return_value=httpx.Response(200, json={"id": "1", "email": "a@b.com", "name": "A", "picture": {"data": {"url": "https://x"}}}))
    profile = await meta.get_user_profile("code")
    assert profile.provider == "meta"
    assert profile.provider_user_id == "1"
    assert profile.email == "a@b.com"
    assert profile.avatar_url == "https://x"


@pytest.mark.asyncio
@respx.mock
async def test_meta_profile_without_email(meta):
    respx.get(meta.token_url).mock(return_value=httpx.Response(200, json={"access_token": "token"}))
    respx.get(meta.profile_url).mock(return_value=httpx.Response(200, json={"id": "2", "name": "A"}))
    profile = await meta.get_user_profile("code")
    assert profile.email is None
    assert profile.avatar_url is None


@pytest.mark.asyncio
@respx.mock
async def test_meta_non_200(meta):
    respx.get(meta.token_url).mock(return_value=httpx.Response(400))
    with pytest.raises(TokenExchangeError):
        await meta.get_user_profile("code")
