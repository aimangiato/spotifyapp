import os
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()



def get_spotify_oauth():
    scope = (
        "user-library-read "  # <-- questo serve per /me/tracks
        "user-library-modify "
        "playlist-read-private "
        "playlist-modify-private "
        "playlist-modify-public "
        "user-read-playback-state "
        "user-modify-playback-state "
        "user-read-currently-playing"
    )
    return SpotifyOAuth(
        client_id=os.environ['SPOTIPY_CLIENT_ID'],
        client_secret=os.environ['SPOTIPY_CLIENT_SECRET'],
        redirect_uri=os.environ['SPOTIPY_REDIRECT_URI'],
        scope=scope,
        show_dialog=True
    )
