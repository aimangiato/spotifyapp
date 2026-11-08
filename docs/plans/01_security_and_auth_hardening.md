# Piano 01: Hardening Sicurezza, Autenticazione & Isolamento Sessioni

## 🎯 Obiettivo
Eliminare le 5 vulnerabilità di sicurezza critiche identificate nella review del backend, garantendo che i token Spotify, le sessioni utente e i dati delle librerie musicali siano strettamente isolati e protetti da accessi non autorizzati e attacchi CSRF.

---

## 🔍 Vulnerabilità Indirizzate

| ID | Vulnerabilità | File & Righe | Livello di Rischio |
|---|---|---|---|
| **SEC-01** | Fuga dati multi-tenant via cache globale in memoria | `backend/utils.py` (L4-7, L13-14, L39-40) | **CRITICO** |
| **SEC-02** | Collisione credenziali tramite file `.cache` condiviso su disco | `backend/spotify_oauth.py` (L20-26) | **CRITICO** |
| **SEC-03** | OAuth 2.0 vulnerabile a CSRF (Assenza parametro `state`) | `backend/app.py` (L17-32) | **CRITICO** |
| **SEC-04** | Fallback insicuro su chiave segreta `"dev_secret"` e cookie non protetti | `backend/app.py` (L13) | **CRITICO** |
| **SEC-05** | Esecuzione arbitraria di codice (RCE) via `debug=True` hardcoded | `backend/app.py` (L305) | **CRITICO** |

---

## 🛠️ Modifiche Dettagliate e Specifiche Tecniche

### 1. Eliminazione Cache Globale e Fuga Dati Multi-Tenant (`backend/utils.py`)

#### Problema
In `backend/utils.py`, `_cached_liked_tracks` e `_last_cache_time` sono variabili globali a livello di modulo. Qualsiasi utente che effettua una ricerca sui brani preferiti visualizza i brani dell'ultimo utente che ha popolato la cache nei 5 minuti precedenti.

#### Azione Correttiva
Rimuovere completamente ogni riferimento alle variabili globali `_cached_liked_tracks` e `_last_cache_time`. La funzione `load_all_liked_tracks` deve essere eliminata o sostituita da una funzione pura senza stato globale.

```python
# ELIMINARE COMPLETAMENTE DA backend/utils.py:
# LIKED_CACHE_TTL = 60 * 5
# _last_cache_time = 0
# _cached_liked_tracks = []
# global _last_cache_time, _cached_liked_tracks
```

---

### 2. Isolamento dei Token con `FlaskSessionCacheHandler` (`backend/spotify_oauth.py`)

#### Problema
`SpotifyOAuth` di Spotipy, se istanziato senza un gestore di cache, memorizza il token nel file `.cache` nella working directory del server. Ogni login sovrascrive il file condiviso.

#### Azione Correttiva
Configurare `FlaskSessionCacheHandler(session)` in modo che ogni token venga salvato e letto esclusivamente dal cookie di sessione cifrato del singolo client browser.

```python
# backend/spotify_oauth.py
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
    """Ritorna l'istanza SpotifyOAuth vincolata alla sessione Flask del client."""
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
```

---

### 3. Protezione Anti-CSRF nel Flusso OAuth (`backend/app.py`)

#### Problema
`/login` e `/callback` non usano il parametro crittografico `state`. Un utente malintenzionato può eseguire il login forzato di una vittima con il proprio codice di autorizzazione.

#### Azione Correttiva
1. Generare una stringa crittograficamente sicura con `secrets.token_urlsafe(32)`.
2. Salvarla in `session["oauth_state"]`.
3. Passarla a `sp_oauth.get_authorize_url(state=state)`.
4. In `/callback`, estrarre `state` dal query param e confrontarlo in tempo costante con `session.pop("oauth_state", None)`.

```python
import secrets
from flask import request, session, redirect, jsonify

@app.route("/login")
def login():
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url(state=state)
    return redirect(auth_url)

@app.route("/callback")
def callback():
    sp_oauth = get_spotify_oauth()
    
    # 1. Verifica State Anti-CSRF
    returned_state = request.args.get("state")
    saved_state = session.pop("oauth_state", None)

    if not returned_state or not saved_state or returned_state != saved_state:
        return jsonify({
            "error": "invalid_state",
            "message": "Validazione anti-CSRF fallita: lo state non corrisponde."
        }), 400

    # 2. Verifica presenza del Code
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "missing_code", "message": "Nessun codice fornito da Spotify"}), 400

    # 3. Scambio codice con token (salvato automaticamente in session da FlaskSessionCacheHandler)
    token_info = sp_oauth.get_access_token(code)
    if not token_info:
        return jsonify({"error": "auth_failed", "message": "Impossibile recuperare il token"}), 400

    return redirect("/")
```

---

### 4. Hardening di Sessione, Cookie e CORS (`backend/app.py`)

#### Problema
`app.secret_key` usa il fallback `"dev_secret"`. I cookie non hanno flag di protezione. CORS accetta credenziali senza restrizione esplicita sulle origini consentite.

#### Azione Correttiva
```python
import os
from flask import Flask
from flask_cors import CORS

app = Flask(__name__, static_folder="../frontend", static_url_path="/")

# Fail-fast se FLASK_SECRET_KEY non è configurata
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key or secret_key == "dev_secret":
    raise RuntimeError("ERRORE SICUREZZA: Definire una FLASK_SECRET_KEY robusta in .env!")

app.secret_key = secret_key

# Configurazione hardening cookie
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,       # Impedisce l'accesso al cookie via document.cookie (anti-XSS)
    SESSION_COOKIE_SECURE=False,        # Impostare a True in produzione con HTTPS attivo
    SESSION_COOKIE_SAMESITE="Lax",      # Protezione contro richieste cross-site non sicure
    PERMANENT_SESSION_LIFETIME=3600     # Scadenza sessione a 1 ora
)

# CORS ristretto alle origini note
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",")
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}}, supports_credentials=True)
```

---

### 5. Disattivazione Debugger Interattivo in Esecuzione (`backend/app.py`)

#### Problema
`app.run(port=8080, debug=True)` espone la console interattiva di Werkzeug in caso di crash.

#### Azione Correttiva
```python
if __name__ == "__main__":
    is_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    app.run(host="127.0.0.1", port=8080, debug=is_debug)
```

---

## ✅ Piano di Verifica del Piano 01

1. **Test Isolamento Credenziali:**
   - Aprire due finestre browser in incognito (Utente A e Utente B).
   - Eseguire il login con Utente A. Verificare che nessun file `.cache` venga generato o aggiornato nella cartella del server.
   - Eseguire il login con Utente B. Verificare tramite `/api/me` che Utente A continui a vedere il proprio profilo e Utente B veda il suo.
2. **Test Protezione CSRF:**
   - Eseguire una richiesta manuale a `/callback?code=FAKE_CODE` senza `state`.
   - **Risultato atteso:** HTTP 400 con messaggio `"Validazione anti-CSRF fallita"`.
3. **Test Segreto e Cookie:**
   - Rimuovere temporaneamente `FLASK_SECRET_KEY` da `.env`: verificare che l'applicazione rifiuti di avviarsi lanciando l'eccezione `RuntimeError`.
   - Ispezionare il cookie `session` nei DevTools del browser e verificare i flag `HttpOnly` e `SameSite=Lax`.
