# OAuth authentication package

This directory contains framework-agnostic OAuth 2.0 business logic for Google and Meta (Facebook).

## Install

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## Test

Run from the repository root:

```powershell
python -m pytest -q backend/tests
```

The provider clients are async and use `httpx.AsyncClient`. Routes or controllers can create an OAuth client, generate a login URL, validate the callback state with `verify_state`, and call `get_user_profile(code)`.
