import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configurazione centralizzata dell'applicazione Flask."""
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    if not SECRET_KEY or SECRET_KEY in ("dev_secret", "secret", "change_me") or len(SECRET_KEY) < 8:
        raise RuntimeError("ERRORE SICUREZZA: Definire una FLASK_SECRET_KEY robusta in .env!")

    SPOTIPY_CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
    SPOTIPY_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
    SPOTIPY_REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI")

    # Session & Cookie hardening (SEC-04)
    SESSION_COOKIE_HTTPONLY = True
    is_prod = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", "1" if is_prod else "0"
    ).lower() in ("1", "true")
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 3600

    # CORS settings
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "ALLOWED_ORIGINS",
            "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5000,http://127.0.0.1:5000"
        ).split(",")
        if origin.strip()
    ]


class TestConfig(Config):
    """Configurazione per l'ambiente di test."""
    TESTING = True
    SECRET_KEY = "super_secure_random_key_for_testing_123456"
    SPOTIPY_CLIENT_ID = "test_client_id"
    SPOTIPY_CLIENT_SECRET = "test_client_secret"
    SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8080/callback"
    SESSION_COOKIE_SECURE = False
