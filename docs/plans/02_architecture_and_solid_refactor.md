# Piano 02: Ristrutturazione Architetturale a 3 Livelli & Principi SOLID

## 🎯 Obiettivo
Decomporre il monolite `app.py` (attualmente responsabile di routing, sessioni, chiamate API di terze parti, manipolazione dati, validazione e serving statico) in un'architettura modulare a 3 livelli conforme ai principi **SOLID**.

---

## 🏛️ Allineamento con i Principi SOLID

| Principio | Stato Precedente | Stato Target (Post-Refactoring) |
|---|---|---|
| **S** - Single Responsibility | `app.py` fa tutto (routing, logica di business, auth, gestione token, formato risposte). | **Separazione netta:** Blueprints gestiscono HTTP, Services contengono la logica di business, Schemas gestiscono validazione/serializzazione. |
| **O** - Open/Closed | Modificare una logica (es. aggiunta controlli di ownership) richiede di modificare il controller. | Nuove validazioni o estensioni di business avvengono tramite nuovi Services o Schemi senza alterare le route. |
| **L** - Liskov Substitution | Nessuna interfaccia; dipendenza diretta dal client concreto `spotipy.Spotify`. | Services ricevono il client Spotify tramite dependency injection, rendendolo sostituibile con un mock nei test. |
| **I** - Interface Segregation | I route handler accedono all'intero client Spotipy globale. | I Services espongono solo i metodi necessari al rispettivo dominio (`get_user_playlists`, `add_tracks_to_playlist`). |
| **D** - Dependency Inversion | Le route dipendono da `os.environ`, `session` e funzioni globali. | Iniezione delle dipendenze centralizzata tramite decorator `@require_auth` e Service constructors. |

---

## 📐 Struttura Modulare Target

```
backend/
├── __init__.py               # create_app() - Application Factory
├── config.py                 # Gestione centralizzata configurazioni
├── auth/
│   ├── __init__.py
│   ├── oauth.py              # Wrapper configurazione OAuth con session cache
│   └── decorators.py         # Decoratore @require_auth con client injection
├── services/
│   ├── __init__.py
│   ├── auth_service.py       # Gestione autenticazione, refresh token, user session
│   ├── playlist_service.py   # Logica playlist: creazione, recupero, modifica
│   └── track_service.py      # Gestione brani, deduplicazione, safe navigation
├── schemas/
│   ├── __init__.py
│   ├── common.py             # Schema risposte d'errore
│   └── playlist_schemas.py   # Schemi Marshmallow per validazione payload
└── routes/
    ├── __init__.py
    ├── auth_bp.py            # Endpoints /login, /callback, /logout
    ├── me_bp.py              # Endpoints /api/v1/me, /api/v1/me/tracks
    └── playlists_bp.py       # Endpoints /api/v1/playlists/...
```

---

## 🛠️ Componenti Chiave da Implementare

### 1. Application Factory & Configurazione (`backend/config.py` e `backend/__init__.py`)

#### `backend/config.py`
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("FLASK_SECRET_KEY non impostata in .env")

    SPOTIPY_CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
    SPOTIPY_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
    SPOTIPY_REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI")
    
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 3600
    
    ALLOWED_ORIGINS = os.environ.get(
        "ALLOWED_ORIGINS", 
        "http://localhost:8080,http://127.0.0.1:8080"
    ).split(",")
```

#### `backend/__init__.py`
```python
from flask import Flask, jsonify
from flask_cors import CORS
from marshmallow import ValidationError
from spotipy.exceptions import SpotifyException

from backend.config import Config
from backend.routes.auth_bp import auth_bp
from backend.routes.me_bp import me_bp
from backend.routes.playlists_bp import playlists_bp

def create_app(config_class=Config):
    app = Flask(__name__, static_folder="../frontend", static_url_path="/")
    app.config.from_object(config_class)

    # CORS
    CORS(app, resources={r"/api/*": {"origins": app.config["ALLOWED_ORIGINS"]}}, supports_credentials=True)

    # Registrazione Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(me_bp, url_prefix="/api/v1/me")
    app.register_blueprint(playlists_bp, url_prefix="/api/v1/playlists")

    # Global Error Handlers
    register_error_handlers(app)

    # Frontend serving route
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

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
            "message": e.msg,
            "status_code": status
        }), status
```

---

### 2. Autenticazione & Decoratore `@require_auth` (`backend/auth/decorators.py`)

Elimina la duplicazione di `get_spotify_client()` e `ensure_token()` in tutte le route, iniettando direttamente l'istanza autenticata `sp` nella funzione handler:

```python
from functools import wraps
from flask import session, jsonify
import spotipy
from backend.auth.oauth import get_spotify_oauth

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        sp_oauth = get_spotify_oauth()
        token_info = sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token())

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
```

---

### 3. Validazione con Marshmallow (`backend/schemas/playlist_schemas.py`)

Evita i controlli manuali (`if not name:`, `data["track_ids"]`) e gli accessi rischiosi a dizionario:

```python
from marshmallow import Schema, fields, validate

class CreatePlaylistSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    public = fields.Bool(load_default=False)
    description = fields.Str(load_default="", validate=validate.Length(max=300))

class UpdatePlaylistSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=100))
    public = fields.Bool()
    description = fields.Str(validate=validate.Length(max=300))

class ModifyTracksSchema(Schema):
    track_ids = fields.List(
        fields.Str(validate=validate.Regexp(r"^[0-9A-Za-z]{22}$")),
        required=True,
        validate=validate.Length(min=1, max=100, error="Fornire tra 1 e 100 ID di traccia.")
    )

class LikedTracksQuerySchema(Schema):
    offset = fields.Int(load_default=0, validate=validate.Range(min=0))
    limit = fields.Int(load_default=20, validate=validate.Range(min=1, max=50))
    q = fields.Str(load_default="")
```

---

### 4. Service Layer (`backend/services/playlist_service.py`)

Incapsula tutta la logica Spotify, separandola dall'HTTP:

```python
class PlaylistService:
    def __init__(self, sp):
        self.sp = sp

    def get_user_playlists(self, limit=50, offset=0):
        results = self.sp.current_user_playlists(limit=limit, offset=offset)
        playlists = []
        for pl in results.get("items", []):
            playlists.append({
                "id": pl["id"],
                "name": pl["name"],
                "tracks_total": pl.get("tracks", {}).get("total", 0),
                "is_public": pl.get("public", False)
            })
        return {
            "items": playlists,
            "total": results.get("total", len(playlists)),
            "limit": limit,
            "offset": offset
        }

    def create_playlist(self, name: str, public: bool = False, description: str = ""):
        user_id = self.sp.current_user()["id"]
        return self.sp.user_playlist_create(user_id, name=name, public=public, description=description)

    def update_playlist_details(self, playlist_id: str, **kwargs):
        # Filtra solo i campi valorizzati
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return {"status": "no_changes"}
        self.sp.playlist_change_details(playlist_id, **update_data)
        return {"status": "ok"}
```

---

### 5. Controller / Blueprint (`backend/routes/playlists_bp.py`)

I controller rimangono estremamente snelli (solo parsing, delega al service e ritorno JSON):

```python
from flask import Blueprint, request, jsonify
from backend.auth.decorators import require_auth
from backend.services.playlist_service import PlaylistService
from backend.schemas.playlist_schemas import CreatePlaylistSchema, UpdatePlaylistSchema

playlists_bp = Blueprint("playlists", __name__)

create_schema = CreatePlaylistSchema()
update_schema = UpdatePlaylistSchema()

@playlists_bp.route("", methods=["GET"])
@require_auth
def list_playlists(sp):
    service = PlaylistService(sp)
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    data = service.get_user_playlists(limit=limit, offset=offset)
    return jsonify(data), 200

@playlists_bp.route("", methods=["POST"])
@require_auth
def create_playlist(sp):
    payload = create_schema.load(request.get_json() or {})
    service = PlaylistService(sp)
    created = service.create_playlist(
        name=payload["name"],
        public=payload["public"],
        description=payload["description"]
    )
    return jsonify(created), 201

@playlists_bp.route("/<playlist_id>", methods=["PATCH"])
@require_auth
def update_playlist(sp, playlist_id):
    payload = update_schema.load(request.get_json() or {})
    service = PlaylistService(sp)
    res = service.update_playlist_details(playlist_id, **payload)
    return jsonify(res), 200
```

---

## ✅ Piano di Verifica del Piano 02

1. **Verifica Validazione Marshmallow:**
   - Eseguire una `POST /api/v1/playlists` con body vuoto o con nome vuoto `{"name": ""}`.
   - **Risultato atteso:** HTTP 400 con JSON strutturato:
     ```json
     {
       "error": "validation_error",
       "message": "Dati di input non validi",
       "details": { "name": ["Shorter than minimum length 1."] }
     }
     ```
2. **Verifica `@require_auth`:**
   - Chiamare qualsiasi endpoint `/api/v1/...` senza cookie di sessione.
   - **Risultato atteso:** HTTP 401 immediato con `{"error": "unauthorized"}` senza crash.
3. **Verifica Eccezioni Upstream:**
   - Tentare la modifica di una playlist inesistente `POST /api/v1/playlists/INVALID_ID/tracks`.
   - **Risultato atteso:** Gestione controllata tramite `handle_spotify_error` con ritorno del codice 404 senza stack trace non gestito.
