import secrets
from flask import session
from backend.auth.oauth import get_spotify_oauth


class AuthService:
    """Service layer per la gestione di autenticazione OAuth 2.0 e state anti-CSRF."""

    def __init__(self, sp_oauth_factory=None):
        if sp_oauth_factory is not None:
            self.sp_oauth_factory = sp_oauth_factory
        else:
            def _factory():
                try:
                    import backend.app as app_mod
                    if hasattr(app_mod, "get_spotify_oauth"):
                        return app_mod.get_spotify_oauth()
                except Exception:
                    pass
                return get_spotify_oauth()
            self.sp_oauth_factory = _factory

    @staticmethod
    def generate_state() -> str:
        """Genera un token casuale crittograficamente sicuro di almeno 32 caratteri."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_state(state: str, expected_state: str) -> bool:
        """Valida lo state OAuth in tempo costante contro attacchi CSRF."""
        if not state or not expected_state:
            return False
        return secrets.compare_digest(state, expected_state)

    def get_authorize_url(self, state: str = None) -> str:
        """Genera l'URL di autorizzazione Spotify con parametro state anti-CSRF."""
        sp_oauth = self.sp_oauth_factory()
        return sp_oauth.get_authorize_url(state=state)

    def get_access_token(self, code: str):
        """Scambia il codice di autorizzazione con il token e lo memorizza nella sessione."""
        sp_oauth = self.sp_oauth_factory()
        return sp_oauth.get_access_token(code)

    @staticmethod
    def clear_session():
        """Pulisce la sessione Flask (logout)."""
        session.clear()
