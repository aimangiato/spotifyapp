# Piano 04: Ridisegno API RESTful & Migrazione Frontend

## 🎯 Obiettivo
Eliminare l'incoerenza degli endpoint verb-based in stile RPC, adottare standard RESTful moderni con versionamento (`/api/v1/...`), uniformare gli schemi di risposta JSON ed eseguire la migrazione coordinata del frontend (`frontend/app.js` e `frontend/edit.js`).

---

## 🗺️ Matrice di Migrazione degli Endpoint

| Endpoint Legacy (Obsoleto) | Metodo | Nuovo Endpoint RESTful (v1) | Metodo | Stato / Azione |
|---|---|---|---|---|
| `/api/me` | GET | `/api/v1/me` | GET | **Preservato e versionato** |
| `/api/create_playlist` | POST | `/api/v1/playlists` | **POST** | **Ridisegnato RESTful (Ritorna 201 Created)** |
| `/api/playlists` | GET | `/api/v1/playlists` | GET | **Preservato con envelope di paginazione** |
| `/api/playlist/<id>` | GET | `/api/v1/playlists/<id>` | GET | **Preservato e reso consistente al plurale** |
| `/api/update_playlist` | POST | `/api/v1/playlists/<id>` | **PATCH** | **Unificato** |
| `/api/playlist/<id>/rename` | POST | `/api/v1/playlists/<id>` | **PATCH** | **Deprecato ed eliminato (duplicato)** |
| `/api/add_tracks` | POST | `/api/v1/playlists/<id>/tracks` | **POST** | **Ridisegnato come sotto-risorsa REST** |
| `/api/remove_tracks` | POST | `/api/v1/playlists/<id>/tracks` | **DELETE** | **Ridisegnato con metodo semantico DELETE** |
| `/api/liked_tracks` | GET | `/api/v1/me/tracks` | GET | **Ridisegnato: risorsa appartenente a /me** |
| `/api/remove_from_liked` | POST | `/api/v1/me/tracks` | **DELETE** | **Ridisegnato con metodo semantico DELETE** |
| `/edit/<playlist_id>` | GET | *Nessuno* | - | **ELIMINATO (rotta morta con template mancante)** |

---

## 📦 Standardizzazione Envelope di Risposta e Errori

Tutte le risposte del backend seguiranno convenzioni coerenti.

### 1. Risposta di Successo con Paginazione
```json
{
  "items": [ ... ],
  "total": 142,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

### 2. Risposta di Errore Standardizzata
```json
{
  "error": "error_code_in_snake_case",
  "message": "Messaggio comprensibile per l'utente finale",
  "details": {}
}
```

---

## 💻 Modifiche Dettagliate al Frontend

### 1. Migrazione `frontend/app.js`

#### Prima (Legacy)
```javascript
// Chiamate a endpoint RPC con parsing inconsistente
const r = await fetch('/api/create_playlist', { ... });
const r = await fetchWithLoader('/api/playlists', { ... });
```

#### Dopo (Nuovo Standard RESTful)
```javascript
// frontend/app.js

async function getMe() {
  const r = await fetch('/api/v1/me', { credentials: 'include' });
  if (r.status === 200) {
    const data = await r.json();
    document.getElementById('user').innerText = `Logged in as ${data.display_name} (${data.id})`;
  } else {
    document.getElementById('user').innerText = 'Not logged in';
  }
}

document.getElementById('create-pl').onclick = async () => {
  const name = document.getElementById('pl-name').value;
  if (!name.trim()) {
    alert("Inserisci un nome valido per la playlist");
    return;
  }

  const r = await fetch('/api/v1/playlists', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name.trim(), public: false, description: 'Created via App' })
  });
  
  const res = await r.json();
  if (r.status === 201) {
    alert(`Playlist creata con successo: ${res.name}`);
    document.getElementById('pl-name').value = '';
    loadPlaylists();
  } else {
    alert(`Errore: ${res.message || res.error}`);
  }
};

async function loadPlaylists() {
  const r = await fetchWithLoader('/api/v1/playlists', { credentials: 'include' });
  if (r.status !== 200) {
    alert('Devi prima fare login!');
    return;
  }
  
  const data = await r.json();
  const playlists = data.items || [];
  const container = document.getElementById('playlists');
  container.innerHTML = '';

  if (playlists.length === 0) {
    container.innerHTML = '<p>Nessuna playlist trovata.</p>';
    return;
  }

  playlists.forEach(pl => {
    const div = document.createElement('div');
    div.className = 'playlist';
    div.innerHTML = `
      <strong>${pl.name}</strong><br>
      ${pl.tracks_total} tracce
      <button onclick="editPlaylist('${pl.id}')">Edit</button>
      <hr>
    `;
    container.appendChild(div);
  });
}

document.getElementById('load-playlists').onclick = loadPlaylists;

window.editPlaylist = (id) => {
  window.location = `/edit.html?playlist_id=${id}`;
};
```

---

### 2. Migrazione `frontend/edit.js`

#### Principali Correzioni
1. Aggiornamento URL: `/api/v1/playlists/${playlistId}`, `/api/v1/playlists/${playlistId}/tracks` (POST/DELETE), `/api/v1/me/tracks`.
2. Fallback visivo su `coverart` nulla (placeholder per album senza immagine).
3. Payload unificato con parametro `track_ids` (plurale) su tutti i metodi.

```javascript
// frontend/edit.js

const params = new URLSearchParams(window.location.search);
const playlistId = params.get("playlist_id");
const PLACEHOLDER_COVER = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" fill="%23555"><rect width="100%" height="100%" fill="%23222"/><text x="50%" y="50%" fill="%23888" dominant-baseline="middle" text-anchor="middle" font-size="10">No Cover</text></svg>';

let likedOffset = 0;
let currentQuery = "";
let existingTrackIds = new Set();
let selectedPlaylistTracks = new Set();
let selectedLikedTracks = new Set();

async function loadPlaylistInfo() {
  const r = await fetch(`/api/v1/playlists/${playlistId}`, { credentials: 'include' });
  const data = await r.json();

  if (!r.ok) {
    alert("Errore nel caricamento della playlist: " + (data.message || data.error));
    return;
  }

  document.getElementById("playlist-name").textContent = data.name;
  existingTrackIds = new Set(data.existing_ids || []);

  const list = document.getElementById("playlist-tracks");
  list.innerHTML = "";

  (data.tracks || []).forEach(track => {
    const div = document.createElement("div");
    div.classList.add("track-item");

    div.innerHTML = `
      <img src="${track.coverart || PLACEHOLDER_COVER}" class="track-cover" alt="Cover">
      <div class="track-info">
          <strong>${track.name}</strong> — ${track.artist}
      </div>
      <input type="checkbox" class="playlist-checkbox" data-id="${track.id}">
    `;

    list.appendChild(div);

    div.querySelector(".playlist-checkbox").addEventListener("change", (e) => {
      const id = e.target.dataset.id;
      if (e.target.checked) {
        selectedPlaylistTracks.add(id);
      } else {
        selectedPlaylistTracks.delete(id);
      }
    });
  });
}

// Rimozione tracce (DELETE semantico)
document.getElementById("remove-selected-btn").onclick = async () => {
  if (selectedPlaylistTracks.size === 0) {
    alert("Seleziona almeno una traccia da rimuovere!");
    return;
  }

  const trackIds = Array.from(selectedPlaylistTracks);
  const r = await fetch(`/api/v1/playlists/${playlistId}/tracks`, {
    method: "DELETE",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_ids: trackIds })
  });

  if (r.ok) {
    alert("Tracce rimosse con successo!");
    selectedPlaylistTracks.clear();
    await loadPlaylistInfo();
    await loadLikedTracks(true);
  } else {
    const err = await r.json();
    alert("Errore: " + (err.message || err.error));
  }
};

// Caricamento preferiti paginato
async function loadLikedTracks(reset = false) {
  if (reset) {
    likedOffset = 0;
    document.getElementById("liked-tracks").innerHTML = "";
    selectedLikedTracks.clear();
  }

  const url = new URL("/api/v1/me/tracks", window.location.origin);
  url.searchParams.set("offset", likedOffset);
  url.searchParams.set("limit", 20);
  if (currentQuery) url.searchParams.set("q", currentQuery);

  const r = await fetch(url, { credentials: 'include' });
  const data = await r.json();

  const list = document.getElementById("liked-tracks");
  const tracks = data.items || [];

  tracks.forEach(t => {
    const div = document.createElement("div");
    div.className = "track-item";
    const alreadyInPlaylist = existingTrackIds.has(t.id);

    div.innerHTML = `
      <img src="${t.coverart || PLACEHOLDER_COVER}" class="track-cover" alt="Cover">
      <div class="track-info">
          <strong>${t.name}</strong> — ${t.artist}
      </div>
      <input type="checkbox" class="liked-checkbox" data-id="${t.id}" ${alreadyInPlaylist ? "checked disabled" : ""}>
    `;

    div.querySelector(".liked-checkbox").addEventListener("change", (e) => {
      const id = e.target.dataset.id;
      if (e.target.checked) selectedLikedTracks.add(id);
      else selectedLikedTracks.delete(id);
    });

    list.appendChild(div);
  });

  likedOffset += tracks.length;
  document.getElementById("show-more").style.display = data.has_more ? "block" : "none";
}

// Aggiunta tracce alla playlist
document.getElementById("add-selected-btn").onclick = async () => {
  if (selectedLikedTracks.size === 0) {
    alert("Seleziona almeno una traccia!");
    return;
  }

  const trackIds = Array.from(selectedLikedTracks);
  const res = await fetch(`/api/v1/playlists/${playlistId}/tracks`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_ids: trackIds })
  });

  if (res.ok) {
    alert("Brani aggiunti con successo!");
    selectedLikedTracks.clear();
    await loadPlaylistInfo();
    await loadLikedTracks(true);
  } else {
    const err = await res.json();
    alert("Errore nell'aggiunta: " + (err.message || err.error));
  }
};

// Ridenominazione playlist (PATCH semantico)
document.getElementById("rename-btn").onclick = async () => {
  const currentName = document.getElementById("playlist-name").textContent;
  const newName = prompt("Nuovo nome playlist:", currentName);
  if (!newName || newName.trim() === "" || newName === currentName) return;

  const r = await fetch(`/api/v1/playlists/${playlistId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: newName.trim() })
  });

  const data = await r.json();
  if (r.ok) {
    alert("Nome modificato con successo!");
    document.getElementById("playlist-name").textContent = newName.trim();
  } else {
    alert("Errore: " + (data.message || data.error));
  }
};
```

---

## ✅ Piano di Verifica del Piano 04

1. **Verifica End-to-End Interfaccia Web:**
   - Navigare su `http://localhost:8080/`.
   - Eseguire login con Spotify.
   - Creare una nuova playlist e verificare che appaia immediatamente con HTTP 201.
   - Cliccare su "Edit" e verificare il caricamento dei brani preferiti e delle tracce della playlist con URL `/api/v1/...`.
2. **Verifica Status Code RESTful:**
   - Tramite DevTools Network tab, verificare che:
     - `POST /api/v1/playlists` ritorni `201 Created`.
     - `PATCH /api/v1/playlists/<id>` ritorni `200 OK`.
     - `DELETE /api/v1/playlists/<id>/tracks` ritorni `200` o `204`.
3. **Verifica Rotte Obsolete Rimosse:**
   - Verificare che chiamate dirette a `/edit/123` o `/api/create_playlist` ritornino HTTP 404 (o redirect di compatibilità se abilitati).
