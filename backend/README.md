# OAuth authentication package

This directory contains framework-agnostic OAuth 2.0 business logic for Google and Meta (Facebook).

## Install

Use Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Run from `backend/`:

```powershell
uv sync
```

## Test

Run from `backend/`:

```powershell
uv run pytest -q
```

Or from the repository root:

```powershell
uv run --project backend pytest -q backend/tests
```

## Lint & Docstrings

Run from `backend/`:

```powershell
uv run ruff check auth tests
uv run pydocstyle --convention=google auth
```

The provider clients are async and use `httpx.AsyncClient`. Routes or controllers can create an OAuth client, generate a login URL, validate the callback state with `verify_state`, and call `get_user_profile(code)`.
