import os
import werkzeug

if not hasattr(werkzeug, "__version__"):
    try:
        import importlib.metadata
        werkzeug.__version__ = importlib.metadata.version("werkzeug")
    except Exception:
        werkzeug.__version__ = "3.1.3"

# SEC-04: Fail-fast se FLASK_SECRET_KEY non è configurata o è debole
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key or secret_key in ("dev_secret", "secret", "change_me") or len(secret_key) < 8:
    raise RuntimeError("ERRORE SICUREZZA: Definire una FLASK_SECRET_KEY robusta in .env!")

from backend import create_app
from backend.auth.oauth import get_spotify_oauth
from backend.utils import load_all_liked_tracks

# Inizializzazione applicazione tramite factory
app = create_app()


def ensure_token():
    """Verifica e aggiorna il token di accesso se necessario. Ritorna token_info o None."""
    try:
        sp_oauth = get_spotify_oauth()
    except Exception:
        return None
    cached_token = sp_oauth.cache_handler.get_cached_token()
    if not cached_token:
        return None
    token_info = sp_oauth.validate_token(cached_token)
    return token_info


def get_spotify_client():
    """Ritorna un client Spotipy autenticato per la sessione corrente o None."""
    token_info = ensure_token()
    if not token_info:
        return None
    import spotipy
    return spotipy.Spotify(auth=token_info.get("access_token"))


if __name__ == "__main__":
    is_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="127.0.0.1", port=port, debug=is_debug)
