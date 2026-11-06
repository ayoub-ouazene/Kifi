# OAuth Authentication Integration Guide

## Overview

`backend/auth/` is a standalone, framework-agnostic Python package for the OAuth 2.0 authorization-code flow with Google and Meta (Facebook). It contains no web framework, route registration, database access, session management, or server startup code.

The package provides:

- Provider-specific authorization URLs.
- Async authorization-code exchange using `httpx`.
- Normalized `OAuthUserProfile` objects using Pydantic v2.
- CSRF protection through an application-managed `state` value.

The clients currently use state protection. PKCE should also be added by the routing layer when the application requires PKCE: generate a verifier/challenge pair, persist the verifier alongside the state, include the challenge in the authorization request, and send the verifier during token exchange. The current provider client interfaces do not accept PKCE parameters, so PKCE support requires extending those interfaces before enabling it in production.

## For the Backend Engineer: routing integration

The following example uses FastAPI terminology only to demonstrate integration. This package does not initialize FastAPI or depend on it.

### 1. Configure provider credentials

Set the provider-specific values in the deployment environment. Never expose client secrets to browsers or commit `.env` files.

### 2. Create provider clients

Instantiate `GoogleOAuth` and `MetaOAuth` with the matching credentials and registered callback URI. The callback URI must exactly match the URI configured at Google or Meta.

### 3. Implement `GET /auth/{provider}/login`

1. Validate that `provider` is `google` or `meta`.
2. Call `generate_state()`.
3. Store the state in a short-lived, secure, HTTP-only cookie. A server-side session/cache keyed by a browser identifier is also acceptable.
4. Build the provider URL with `get_login_url(state)`.
5. Redirect the browser to that URL.
6. If using PKCE, persist the code verifier with the state and include the code challenge in the authorization request.

### 4. Implement `GET /auth/{provider}/callback`

1. Read `code`, `state`, and provider error parameters from the query string.
2. Reject missing or provider-error callbacks.
3. Read the saved state cookie/session value and call `verify_state(saved_state, incoming_state)`.
4. Delete the state cookie after one callback attempt, whether valid or invalid.
5. On mismatch, return an authorization error and do not exchange the code.
6. Select the provider client and call `await client.get_user_profile(code)`.
7. Upsert the returned profile into the application database (see the database section).
8. Create the application session or JWT for the resulting internal user ID.
9. Redirect to the frontend using a safe, allow-listed destination. Do not put provider access tokens or client secrets in the URL.

### Example route pseudocode

```python
from auth import GoogleOAuth, MetaOAuth, generate_state, verify_state
from auth.exceptions import TokenExchangeError


def get_client(provider: str):
    if provider == "google":
        return GoogleOAuth(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)
    if provider == "meta":
        return MetaOAuth(META_APP_ID, META_APP_SECRET, META_REDIRECT_URI)
    raise ValueError("Unsupported OAuth provider")


# GET /auth/{provider}/login
async def login(provider: str, response):
    client = get_client(provider)
    state = generate_state()

    # Use secure=True in HTTPS deployments. Set samesite="lax", max_age=600,
    # httponly=True, and path="/auth" (or the narrowest callback path).
    response.set_cookie(
        "oauth_state",
        state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return redirect(client.get_login_url(state))


# GET /auth/{provider}/callback
async def callback(provider: str, code: str | None, state: str | None, request, response):
    saved_state = request.cookies.get("oauth_state")
    response.delete_cookie("oauth_state", path="/auth")

    if not verify_state(saved_state, state):
        raise InvalidStateError("OAuth state validation failed")
    if not code:
        raise OAuthError("Provider did not return an authorization code")

    try:
        profile = await get_client(provider).get_user_profile(code)
    except TokenExchangeError as exc:
        # Log provider/status context server-side; return a generic client error.
        raise OAuthError("OAuth authentication failed") from exc

    user = await upsert_oauth_account(profile)  # Application/database service.
    app_token = issue_application_session(user.id)
    return redirect(f"https://app.example.com/auth/complete?token={app_token}")
```

In a real route, prefer an application session cookie over putting a JWT in a query string. If a redirect token is unavoidable, use a one-time short-lived exchange code instead of the JWT itself.

## For the Database Engineer

### Normalized profile structure

`OAuthUserProfile` is a Pydantic v2 model with this exact shape:

| Field | Type | Meaning |
|---|---|---|
| `provider` | `"google" | "meta"` | OAuth provider name |
| `provider_user_id` | `str` | Google `sub` or Meta `id` |
| `email` | `str | None` | Provider email; Meta may omit it |
| `name` | `str | None` | Provider display name |
| `avatar_url` | `str | None` | Provider profile image URL |

Provider IDs are the authoritative external identity keys. Email is useful for account linking but must not be treated as the provider identity key.

### Recommended PostgreSQL schema

```sql
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT,
    display_name    TEXT,
    avatar_url      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE oauth_accounts (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider          TEXT NOT NULL CHECK (provider IN ('google', 'meta')),
    provider_user_id  TEXT NOT NULL,
    email             TEXT,
    display_name      TEXT,
    avatar_url        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_user_id)
);

CREATE INDEX users_email_idx ON users (lower(email)) WHERE email IS NOT NULL;
CREATE INDEX oauth_accounts_user_id_idx ON oauth_accounts (user_id);
```

Use a separate `oauth_accounts` row for every provider. This supports one internal user linked to Google and Meta simultaneously. If the product requires globally unique emails, add a case-insensitive unique index on `users`, after deciding how to handle legacy duplicate records.

### Account-linking upsert algorithm

Run the complete workflow in one database transaction:

1. Receive `OAuthUserProfile` from the provider client.
2. Normalize the provider identifier and provider name. Do not alter the provider ID beyond validation; preserve it exactly as returned.
3. Look up `oauth_accounts` by `(provider, provider_user_id)` using a row lock where supported.
4. If the OAuth account exists:
   - Load its `users` row.
   - Update provider-controlled profile fields such as provider email, display name, and avatar URL according to product policy.
   - Update `updated_at`.
   - Return the existing internal user.
5. If no OAuth account exists and the profile has an email:
   - Look up an existing user by normalized, case-insensitive email.
   - If exactly one user matches, link a new `oauth_accounts` row to that user.
   - Require explicit confirmation or an existing authenticated session before linking if account takeover risk is a concern. An email from a provider should only be trusted as verified when the provider response/claims have been validated according to provider policy.
6. If no OAuth account and no matching user exist:
   - Create a new `users` row using the available email, name, and avatar.
   - Create the corresponding `oauth_accounts` row.
7. If Meta returns no email:
   - Never attempt email matching.
   - Create or use the account solely by `(provider, provider_user_id)`.
   - Allow the user to add or verify an email later through the normal account settings flow.
8. Handle unique-constraint races by retrying the lookup after a transaction conflict. Never create two internal users for the same `(provider, provider_user_id)`.
9. Commit and return the internal `users.id` to the session/JWT service.

Pseudo-SQL for the provider identity lookup:

```sql
SELECT user_id
FROM oauth_accounts
WHERE provider = $1 AND provider_user_id = $2
FOR UPDATE;
```

Do not store provider client secrets, authorization codes, or raw access tokens in these tables. If refresh tokens are required later, design a separate encrypted secret store and apply key rotation and access controls.

## Environment variables reference

All redirect URIs must exactly match the callback URLs registered in the provider console, including scheme, host, path, and trailing slash behavior.

| Variable | Required | Example | Matching redirect URI |
|---|---:|---|---|
| `GOOGLE_CLIENT_ID` | Yes | `123456789.apps.googleusercontent.com` | Google Cloud Console OAuth client |
| `GOOGLE_CLIENT_SECRET` | Yes | `replace-with-secret` | Same Google OAuth client |
| `GOOGLE_REDIRECT_URI` | Yes | `https://api.example.com/auth/google/callback` | Must equal the Google authorized redirect URI |
| `META_APP_ID` | Yes | `123456789012345` | Meta Developer App |
| `META_APP_SECRET` | Yes | `replace-with-secret` | Same Meta Developer App |
| `META_REDIRECT_URI` | Yes | `https://api.example.com/auth/meta/callback` | Must equal the Meta Valid OAuth Redirect URI |

For local development, use explicitly registered HTTPS or localhost callback URIs, for example:

```dotenv
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
META_REDIRECT_URI=http://localhost:8000/auth/meta/callback
```

Keep development, staging, and production credentials and redirect URIs separate.
