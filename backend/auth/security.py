import secrets


def generate_state() -> str:
    """Generate a URL-safe CSRF state token."""
    return secrets.token_urlsafe(32)


def verify_state(saved_state: str | None, incoming_state: str | None) -> bool:
    """Constant-time compare two non-empty OAuth state values."""
    if not isinstance(saved_state, str) or not isinstance(incoming_state, str):
        return False
    if not saved_state or not incoming_state:
        return False
    return secrets.compare_digest(saved_state, incoming_state)
