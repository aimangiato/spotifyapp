import os
from flask import session
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from dotenv import load_dotenv

load_dotenv()

SCOPE = (
    "user-library-read "
    "user-library-modify "
    "playlist-read-private "
    "playlist-modify-private "
    "playlist-modify-public "
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing"
)

def get_spotify_oauth():
    """Ritorna l'istanza SpotifyOAuth vincolata alla sessione Flask del client (SEC-02)."""
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI")

    if not client_id or not client_secret or not redirect_uri:
        raise ValueError("Variabili d'ambiente SPOTIPY mancanti in .env")

    cache_handler = FlaskSessionCacheHandler(session)

    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_handler=cache_handler,
        show_dialog=True
    )
