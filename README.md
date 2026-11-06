# Kifi

Kifi contains a standalone, framework-agnostic Python OAuth 2.0 authentication package for Google and Meta (Facebook).

## Backend authentication package

The package is located in [backend/auth](backend/auth) and does not initialize a web framework or HTTP server. It exposes async provider clients that can be called from application routes later.

### Supported providers

- Google OAuth 2.0 and OpenID Connect userinfo
- Meta (Facebook) OAuth 2.0 and Graph API profile lookup

### Setup

Use Python 3.11 or newer, then install runtime and development dependencies:

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
```

Copy the environment template and fill in provider credentials when integrating with routes:

```powershell
Copy-Item backend/.env.example backend/.env
```

Never commit `backend/.env` or provider secrets. The committed template is [backend/.env.example](backend/.env.example).

### Example usage

```python
from auth import GoogleOAuth, generate_state, verify_state

oauth = GoogleOAuth(
    client_id="...",
    client_secret="...",
    redirect_uri="https://example.com/auth/google/callback",
)
state = generate_state()
login_url = oauth.get_login_url(state)

# In the callback route, verify the saved state before exchanging the code.
if verify_state(saved_state, incoming_state):
    profile = await oauth.get_user_profile(code)
```

`MetaOAuth` follows the same interface with `app_id`, `app_secret`, and `redirect_uri`.

### Run tests

From the repository root:

```powershell
python -m pytest -q backend/tests
```

The tests mock provider HTTP requests with `respx`; they do not contact Google or Meta.
