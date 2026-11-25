"""Exception types raised by the standalone OAuth clients."""


class OAuthError(Exception):
    """Base exception for OAuth authentication failures.

    Args:
        message: Human-readable description of the authentication failure.
    """


class InvalidStateError(OAuthError):
    """Raised when an OAuth state value cannot be validated."""


class TokenExchangeError(OAuthError):
    """Raised when an OAuth provider rejects a token or profile request."""
