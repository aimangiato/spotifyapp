import os
import secrets
import werkzeug
if not hasattr(werkzeug, "__version__"):
    try:
        import importlib.metadata
        werkzeug.__version__ = importlib.metadata.version("werkzeug")
    except Exception:
        werkzeug.__version__ = "3.1.3"

from flask import Flask, session, redirect, request, jsonify, url_for, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import spotipy

try:
    from backend.utils import load_all_liked_tracks
    from backend.spotify_oauth import get_spotify_oauth
except ImportError:
    from utils import load_all_liked_tracks
    from spotify_oauth import get_spotify_oauth

load_dotenv()

app = Flask(__name__, static_folder="../frontend", static_url_path="/")

# SEC-04: Fail-fast se FLASK_SECRET_KEY non è configurata o è impostata su fallback debole
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key or secret_key in ("dev_secret", "secret", "change_me") or len(secret_key) < 8:
    raise RuntimeError("ERRORE SICUREZZA: Definire una FLASK_SECRET_KEY robusta in .env!")

app.secret_key = secret_key

# SEC-04: Configurazione hardening cookie di sessione
is_prod = os.environ.get("FLASK_ENV") == "production"
is_secure_cookie = os.environ.get("SESSION_COOKIE_SECURE", "1" if is_prod else "0").lower() in ("1", "true")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,           # Impedisce l'accesso al cookie via JavaScript (anti-XSS)
    SESSION_COOKIE_SECURE=is_secure_cookie, # True in produzione HTTPS, False per sviluppo HTTP locale
    SESSION_COOKIE_SAMESITE="Lax",          # Protezione contro richieste cross-site non sicure (anti-CSRF)
    PERMANENT_SESSION_LIFETIME=3600         # Scadenza sessione a 1 ora
)

# SEC-04: CORS ristretto alle origini note
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5000,http://127.0.0.1:5000"
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}}, supports_credentials=True)

# ---------- Auth routes ----------
@app.route("/login")
def login():
    """Avvia il flusso OAuth 2.0 con generazione di uno state crittografico anti-CSRF (SEC-03)."""
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url(state=state)
    return redirect(auth_url)

@app.route("/callback")
def callback():
    """Callback OAuth 2.0 con validazione rigorosa anti-CSRF e isolamento token in sessione (SEC-02, SEC-03)."""
    sp_oauth = get_spotify_oauth()

    # 1. Verifica State Anti-CSRF con confronto in tempo costante
    returned_state = request.args.get("state")
    saved_state = session.pop("oauth_state", None)

    if not returned_state or not saved_state or not secrets.compare_digest(returned_state, saved_state):
        return jsonify({
            "error": "invalid_state",
            "message": "Validazione anti-CSRF fallita: lo state non corrisponde."
        }), 400

    # 2. Verifica se Spotify ha ritornato un errore (es. autorizzazione negata dall'utente)
    spotify_error = request.args.get("error")
    if spotify_error:
        return jsonify({
            "error": "access_denied",
            "message": f"Autorizzazione rifiutata da Spotify: {spotify_error}"
        }), 403

    # 3. Verifica presenza del Code
    code = request.args.get("code")
    if not code:
        return jsonify({
            "error": "missing_code",
            "message": "Nessun codice fornito da Spotify"
        }), 400

    # 4. Scambio codice con token (salvato automaticamente nel cookie cifrato via FlaskSessionCacheHandler)
    token_info = sp_oauth.get_access_token(code)
    if not token_info:
        return jsonify({
            "error": "auth_failed",
            "message": "Impossibile recuperare il token"
        }), 400

    return redirect("/")

@app.route("/logout")
def logout():
    """Termina la sessione dell'utente invalidando i cookie locali."""
    session.clear()
    return redirect("/")

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
    return spotipy.Spotify(auth=token_info.get("access_token"))

# ---------- API endpoints ----------
@app.route("/api/me")
def me():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401
    user = sp.current_user()
    return jsonify(user)

@app.route("/api/search")
def search():
    q = request.args.get("q")
    t = request.args.get("type", "track")
    if not q:
        return jsonify({"error": "missing q param"}), 400
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401
    res = sp.search(q, type=t, limit=10)
    return jsonify(res)

@app.route("/api/create_playlist", methods=["POST"])
def create_playlist():
    payload = request.json or {}
    name = payload.get("name")
    public = payload.get("public", False)
    description = payload.get("description", "")
    if not name:
        return jsonify({"error": "missing name"}), 400
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401
    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(user_id, name, public=public, description=description)
    return jsonify(playlist)

@app.route("/api/add_tracks", methods=["POST"])
def add_tracks():
    payload = request.json or {}
    playlist_id = payload.get("playlist_id")
    track_ids = payload.get("track_ids")  # array di ID tipo "3n3Ppam7vgaVa1iaRUc9Lp"

    if not playlist_id or not track_ids:
        return jsonify({"error": "missing playlist_id or track_ids"}), 400

    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    # Converti ID in URI
    uris_to_add = [f"spotify:track:{tid}" for tid in track_ids]

    # --- Recupera TUTTE le tracce della playlist (con paginazione) ---
    existing_uris = []
    limit = 100
    offset = 0

    while True:
        batch = sp.playlist_items(
            playlist_id,
            fields="items.track.uri,total",
            offset=offset,
            limit=limit
        )
        items = batch.get("items", [])
        if not items:
            break

        existing_uris.extend([item["track"]["uri"] for item in items if item.get("track")])
        offset += limit
        if offset >= batch.get("total", 0):
            break

    # --- Controllo duplicati ---
    duplicate_uris = [uri for uri in uris_to_add if uri in existing_uris]
    if duplicate_uris:
        return jsonify({
            "error": "duplicate_tracks",
            "duplicate_uris": duplicate_uris
        }), 400

    # --- Aggiungi ---
    res = sp.playlist_add_items(playlist_id, uris_to_add)
    return jsonify(res)

@app.route("/api/playlists")
def playlists():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    playlists_data = []
    results = sp.current_user_playlists(limit=50)

    for pl in results.get("items", []):
        playlist_id = pl["id"]
        name = pl["name"]
        total_tracks = pl.get("tracks", {}).get("total", 0)

        # Cerchiamo una data indicativa: data della prima traccia, se esiste
        created_at = None
        try:
            tracks_info = sp.playlist_items(playlist_id, limit=1, fields="items(added_at)")
            if tracks_info.get("items"):
                created_at = tracks_info["items"][0].get("added_at")
        except Exception:
            pass

        playlists_data.append({
            "id": playlist_id,
            "name": name,
            "tracks_total": total_tracks,
            "created_at": created_at
        })

    return jsonify(playlists_data)

@app.route("/api/remove_tracks", methods=["POST"])
def remove_tracks():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    data = request.get_json() or {}
    playlist_id = data.get("playlist_id")
    track_ids = data.get("track_ids", [])
    if not playlist_id or not track_ids:
        return jsonify({"error": "missing playlist_id or track_ids"}), 400

    sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)
    return jsonify({"status": "ok"})

@app.route("/api/update_playlist", methods=["POST"])
def update_playlist():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    data = request.get_json() or {}
    playlist_id = data.get("playlist_id")
    if not playlist_id:
        return jsonify({"error": "missing playlist_id"}), 400

    sp.playlist_change_details(
        playlist_id,
        name=data.get("name"),
        public=data.get("public")
    )
    return jsonify({"status": "ok"})

@app.route("/edit/<playlist_id>")
def edit_page(playlist_id):
    return render_template("edit.html", playlist_id=playlist_id)

@app.route("/api/playlist/<playlist_id>")
def playlist_info(playlist_id):
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    playlist = sp.playlist(playlist_id, fields="name,public,tracks.items(track(name,artists(name),id,album(images)))")
    tracks = []
    for t in playlist.get("tracks", {}).get("items", []):
        track_obj = t.get("track")
        if not track_obj:
            continue
        images = track_obj.get("album", {}).get("images", [])
        coverart = images[0]["url"] if images else None
        tracks.append({
            "id": track_obj.get("id"),
            "name": track_obj.get("name"),
            "artist": ", ".join(a.get("name", "") for a in track_obj.get("artists", [])),
            "coverart": coverart
        })

    return jsonify({
        "name": playlist.get("name"),
        "public": playlist.get("public"),
        "tracks": tracks
    })

@app.route("/api/liked_tracks")
def liked_tracks():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    offset = int(request.args.get("offset", 0))
    query = request.args.get("q", "").lower()
    limit = 20

    # --- Caso 1: nessuna query → usa API Spotify con offset nativo ---
    if not query:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        tracks = []
        for item in results.get("items", []):
            track = item.get("track")
            if not track:
                continue
            images = track.get("album", {}).get("images", [])
            coverart = images[0]["url"] if images else None
            tracks.append({
                "id": track.get("id"),
                "name": track.get("name"),
                "artist": ", ".join(a.get("name", "") for a in track.get("artists", [])),
                "coverart": coverart
            })
        return jsonify(tracks)

    # --- Caso 2: query presente → ricerca globale su tutti i liked (funzione pura) ---
    all_liked = load_all_liked_tracks(sp)

    filtered = [
        t for t in all_liked
        if query in t.get("name", "").lower() or query in t.get("artist", "").lower()
    ]

    paginated = filtered[offset:offset + limit]
    return jsonify(paginated)

@app.route("/api/playlist/<playlist_id>/rename", methods=["POST"])
def rename_playlist(playlist_id):
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401
    data = request.get_json() or {}
    new_name = data.get("name")
    if not new_name:
        return jsonify({"error": "missing_track_name"}), 400

    sp.playlist_change_details(playlist_id, name=new_name)
    return jsonify({"status": "ok", "name": new_name})

# Serve frontend
@app.route("/")
def index():
    return app.send_static_file("index.html")

# SEC-05: Disattivazione debugger Werkzeug e RCE
if __name__ == "__main__":
    is_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="127.0.0.1", port=port, debug=is_debug)
