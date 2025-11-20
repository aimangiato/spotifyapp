import os
from flask import Flask, session, redirect, request, jsonify, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import spotipy

from backend.utils import load_all_liked_tracks
from spotify_oauth import get_spotify_oauth

load_dotenv()

app = Flask(__name__, static_folder="../frontend", static_url_path="/")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret")
CORS(app, supports_credentials=True)

# ---------- Auth routes ----------
@app.route("/login")
def login():
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route("/callback")
def callback():
    sp_oauth = get_spotify_oauth()
    code = request.args.get('code')
    if not code:
        return "No code provided", 400
    token_info = sp_oauth.get_access_token(code)
    # token_info is a dict with access_token, refresh_token, expires_at...
    session['token_info'] = token_info
    return redirect("/")

def ensure_token():
    """Ensure we have a valid access token; refresh if necessary. Returns token_info or None."""
    sp_oauth = get_spotify_oauth()
    token_info = session.get('token_info', None)
    if not token_info:
        return None
    # If token expired, refresh
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info
    return token_info

def get_spotify_client():
    token_info = ensure_token()
    if not token_info:
        return None
    return spotipy.Spotify(auth=token_info['access_token'])

# ---------- API endpoints ----------
@app.route("/api/me")
def me():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error":"not_authenticated"}), 401
    user = sp.current_user()
    return jsonify(user)

@app.route("/api/search")
def search():
    q = request.args.get('q')
    t = request.args.get('type', 'track')
    if not q:
        return jsonify({"error":"missing q param"}), 400
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error":"not_authenticated"}), 401
    res = sp.search(q, type=t, limit=10)
    return jsonify(res)

@app.route("/api/create_playlist", methods=["POST"])
def create_playlist():
    payload = request.json or {}
    name = payload.get("name")
    public = payload.get("public", False)
    description = payload.get("description", "")
    if not name:
        return jsonify({"error":"missing name"}), 400
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error":"not_authenticated"}), 401
    user_id = sp.current_user()['id']
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

        existing_uris.extend([item["track"]["uri"] for item in items if item["track"]])
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

    for pl in results['items']:
        playlist_id = pl['id']
        name = pl['name']
        total_tracks = pl['tracks']['total']

        # cerchiamo una data indicativa: data della prima traccia, se esiste
        created_at = None
        try:
            tracks_info = sp.playlist_items(playlist_id, limit=1, fields="items(added_at)")
            if tracks_info['items']:
                created_at = tracks_info['items'][0]['added_at']
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

    data = request.get_json()
    sp.playlist_remove_all_occurrences_of_items(data["playlist_id"], data["track_ids"])
    return jsonify({"status": "ok"})


@app.route("/api/update_playlist", methods=["POST"])
def update_playlist():
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    data = request.get_json()
    sp.playlist_change_details(
        data["playlist_id"],
        name=data.get("name"),
        public=data.get("public")
    )
    return jsonify({"status": "ok"})

from flask import render_template, request

@app.route("/edit/<playlist_id>")
def edit_page(playlist_id):
    return render_template("edit.html", playlist_id=playlist_id)


@app.route("/api/playlist/<playlist_id>")
def playlist_info(playlist_id):
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401

    playlist = sp.playlist(playlist_id, fields="name,public,tracks.items(track(name,artists(name),id))")
    tracks = [
        {
            "id": t["track"]["id"],
            "name": t["track"]["name"],
            "artist": ", ".join(a["name"] for a in t["track"]["artists"])
        }
        for t in playlist["tracks"]["items"]
    ]
    return jsonify({
        "name": playlist["name"],
        "public": playlist["public"],
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
        for item in results["items"]:
            track = item["track"]
            tracks.append({
                "id": track["id"],
                "name": track["name"],
                "artist": ", ".join(a["name"] for a in track["artists"])
            })
        return jsonify(tracks)

    # --- Caso 2: query presente → ricerca globale su tutti i liked ---
    all_liked = load_all_liked_tracks(sp)

    # Filtra localmente (global search)
    filtered = [
        t for t in all_liked
        if query in t["name"].lower() or query in t["artist"].lower()
    ]

    # Paginazione custom
    paginated = filtered[offset:offset+limit]

    return jsonify(paginated)


@app.route("/api/playlist/<playlist_id>/rename", methods=["POST"])
def rename_playlist(playlist_id):
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "not_authenticated"}), 401
    data = request.get_json()
    new_name = data.get("name")
    if not new_name:
        return jsonify({"error": "missing_track_name"}), 400

    sp.playlist_change_details(playlist_id, name=new_name)

    return jsonify({"status": "ok", "name": new_name})


# Serve frontend
@app.route("/")
def index():
    return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(port=5000, debug=True)
