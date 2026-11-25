"""Security helpers for OAuth authorization-request state protection."""

import secrets


def generate_state() -> str:
    """Generate a cryptographically secure OAuth CSRF state value.

    Returns:
        A URL-safe token generated from 32 random bytes.
    """
    return secrets.token_urlsafe(32)


def verify_state(saved_state: str | None, incoming_state: str | None) -> bool:
    """Compare saved and callback state values using constant-time comparison.

    Args:
        saved_state: State stored by the application before redirecting the user.
        incoming_state: State returned by the OAuth provider in the callback.

    Returns:
        ``True`` only when both values are non-empty strings and match exactly;
        otherwise ``False``. ``None`` and empty values are always rejected.
    """
    if not isinstance(saved_state, str) or not isinstance(incoming_state, str):
        return False
    if not saved_state or not incoming_state:
        return False
    return secrets.compare_digest(saved_state, incoming_state)
