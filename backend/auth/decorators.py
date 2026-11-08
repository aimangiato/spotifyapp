from functools import wraps
from flask import jsonify
import spotipy
from backend.auth.oauth import get_spotify_oauth


def require_auth(f):
    """Decoratore per iniettare l'istanza autenticata spotipy.Spotify come primo argomento."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            sp_oauth = get_spotify_oauth()
        except Exception:
            return jsonify({
                "error": "unauthorized",
                "message": "Autenticazione richiesta o configurazione non valida."
            }), 401

        cached_token = sp_oauth.cache_handler.get_cached_token()
        if not cached_token:
            return jsonify({
                "error": "unauthorized",
                "message": "Autenticazione richiesta o sessione scaduta."
            }), 401

        token_info = sp_oauth.validate_token(cached_token)
        if not token_info:
            return jsonify({
                "error": "unauthorized",
                "message": "Autenticazione richiesta o sessione scaduta."
            }), 401

        # Istanziazione del client Spotify con il token valido
        sp = spotipy.Spotify(auth=token_info["access_token"])

        # Iniezione del client sp come primo argomento
        return f(sp, *args, **kwargs)

    return decorated_function
