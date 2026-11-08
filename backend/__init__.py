import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from marshmallow import ValidationError
from spotipy.exceptions import SpotifyException

from backend.config import Config
from backend.routes.auth_bp import auth_bp
from backend.routes.me_bp import me_bp
from backend.routes.playlists_bp import playlists_bp
from backend.auth.decorators import require_auth
from backend.services.playlist_service import PlaylistService
from backend.services.track_service import TrackService
from backend.schemas.playlist_schemas import CreatePlaylistSchema


def create_app(config_class=Config):
    """Application factory per l'applicazione Spotify."""
    app = Flask(__name__, static_folder="../frontend", static_url_path="/")
    app.config.from_object(config_class)

    # Validazione fail-fast di FLASK_SECRET_KEY
    secret_key = app.config.get("SECRET_KEY")
    if not secret_key or secret_key in ("dev_secret", "secret", "change_me") or len(secret_key) < 8:
        raise RuntimeError("ERRORE SICUREZZA: Definire una FLASK_SECRET_KEY robusta in .env!")

    app.secret_key = secret_key

    # Hardening sessione e cookie (SEC-04)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", 3600)

    # CORS ristretto alle origini consentite
    allowed_origins = app.config.get(
        "ALLOWED_ORIGINS",
        ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5000", "http://127.0.0.1:5000"]
    )
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

    # Registrazione Blueprints RESTful v1
    app.register_blueprint(auth_bp)
    app.register_blueprint(me_bp, url_prefix="/api/v1/me")
    app.register_blueprint(playlists_bp, url_prefix="/api/v1/playlists")

    # Global Error Handlers
    register_error_handlers(app)

    # Frontend serving routes
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    # Compatibility layer per endpoint legacy (/api/...)
    register_legacy_routes(app)

    return app


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        return jsonify({
            "error": "validation_error",
            "message": "Dati di input non validi",
            "details": e.messages
        }), 400

    @app.errorhandler(SpotifyException)
    def handle_spotify_error(e):
        status = e.http_status if e.http_status else 502
        return jsonify({
            "error": "upstream_spotify_error",
            "message": e.msg if hasattr(e, "msg") else str(e),
            "status_code": status
        }), status


def register_legacy_routes(app):
    """Rotte legacy (/api/...) per garantire retrocompatibilità verso test e vecchi client."""
    @app.route("/api/me")
    def legacy_me():
        from backend.auth.oauth import get_spotify_oauth
        try:
            sp_oauth = get_spotify_oauth()
            cached_token = sp_oauth.cache_handler.get_cached_token()
            token_info = sp_oauth.validate_token(cached_token) if cached_token else None
        except Exception:
            token_info = None

        if not token_info:
            return jsonify({"error": "not_authenticated"}), 401

        import spotipy
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user = sp.current_user()
        return jsonify(user)

    @app.route("/api/playlists")
    @require_auth
    def legacy_playlists(sp):
        service = PlaylistService(sp)
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        return jsonify(service.get_user_playlists(limit=limit, offset=offset)["items"])

    @app.route("/api/liked_tracks")
    @require_auth
    def legacy_liked_tracks(sp):
        service = TrackService(sp)
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        query = request.args.get("q", "")
        res = service.get_liked_tracks(limit=limit, offset=offset, query=query)
        return jsonify(res["items"])

    @app.route("/api/create_playlist", methods=["POST"])
    def legacy_create_playlist():
        data = request.get_json() or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "missing_name"}), 400

        @require_auth
        def _execute(sp):
            service = PlaylistService(sp)
            return jsonify(service.create_playlist(name=name)), 200

        return _execute()

    @app.route("/api/search")
    def legacy_search():
        query = request.args.get("q")
        if not query:
            return jsonify({"error": "missing query"}), 400
        from backend.auth.oauth import get_spotify_oauth
        try:
            sp_oauth = get_spotify_oauth()
            cached = sp_oauth.cache_handler.get_cached_token()
            token_info = sp_oauth.validate_token(cached) if cached else None
        except Exception:
            token_info = None
        if not token_info:
            return jsonify({"error": "not_authenticated"}), 401
        return jsonify({"status": "ok"})
