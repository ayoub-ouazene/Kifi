"""Public API for the standalone OAuth authentication package."""

from .exceptions import InvalidStateError, OAuthError, TokenExchangeError
from .google import GoogleOAuth
from .meta import MetaOAuth
from .schemas import OAuthUserProfile
from .security import generate_state, verify_state

__all__ = [
    "GoogleOAuth",
    "InvalidStateError",
    "MetaOAuth",
    "OAuthError",
    "OAuthUserProfile",
    "TokenExchangeError",
    "generate_state",
    "verify_state",
]
