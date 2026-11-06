class OAuthError(Exception):
    """Base exception for OAuth authentication failures."""


class InvalidStateError(OAuthError):
    """Raised when an OAuth state value cannot be validated."""


class TokenExchangeError(OAuthError):
    """Raised when an OAuth provider rejects a token or profile request."""
