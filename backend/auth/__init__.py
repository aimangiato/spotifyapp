# backend/auth/__init__.py
from backend.auth.oauth import get_spotify_oauth
from backend.auth.decorators import require_auth

__all__ = ["get_spotify_oauth", "require_auth"]
