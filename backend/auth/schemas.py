from typing import Optional, Literal

from pydantic import BaseModel


class OAuthUserProfile(BaseModel):
    provider: Literal["google", "meta"]
    provider_user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
