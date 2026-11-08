const params = new URLSearchParams(window.location.search);
const playlistId = params.get("playlist_id");
const PLACEHOLDER_COVER = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" fill="%23555"><rect width="100%" height="100%" fill="%23222"/><text x="50%" y="50%" fill="%23888" dominant-baseline="middle" text-anchor="middle" font-size="10">No Cover</text></svg>';

let likedOffset = 0;
let currentQuery = "";
let existingTrackIds = new Set();
let selectedPlaylistTracks = new Set();
let selectedLikedTracks = new Set();

async function loadPlaylistInfo() {
  if (!playlistId) {
    alert("Nessun ID playlist specificato.");
    return;
  }

  try {
    const r = await fetch(`/api/v1/playlists/${playlistId}`, { credentials: 'include' });
    const data = await r.json();

    if (!r.ok) {
      alert("Errore nel caricamento della playlist: " + (data.message || data.error));
      return;
    }

    document.getElementById("playlist-name").textContent = data.name;
    const publicToggle = document.getElementById("public-toggle");
    if (publicToggle) {
      publicToggle.checked = Boolean(data.public);
    }

    existingTrackIds = new Set(data.existing_ids || []);

    const list = document.getElementById("playlist-tracks");
    list.innerHTML = "";
    selectedPlaylistTracks.clear();

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
  } catch (err) {
    alert("Errore di connessione: " + err);
  }
}

// Rimozione tracce (DELETE semantico RESTful)
document.getElementById("remove-selected-btn").onclick = async () => {
  if (selectedPlaylistTracks.size === 0) {
    alert("Seleziona almeno una traccia da rimuovere!");
    return;
  }

  const trackIds = Array.from(selectedPlaylistTracks);
  try {
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
      alert("Errore nella rimozione: " + (err.message || err.error));
    }
  } catch (err) {
    alert("Errore di connessione: " + err);
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
  if (currentQuery) {
    url.searchParams.set("q", currentQuery);
  }

  try {
    const r = await fetch(url, { credentials: 'include' });
    const data = await r.json();

    if (!r.ok) {
      console.error("Errore nel caricamento dei preferiti:", data);
      return;
    }

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
        if (e.target.checked) {
          selectedLikedTracks.add(id);
        } else {
          selectedLikedTracks.delete(id);
        }
      });

      list.appendChild(div);
    });

    likedOffset += tracks.length;
    const showMoreBtn = document.getElementById("show-more");
    if (showMoreBtn) {
      showMoreBtn.style.display = data.has_more ? "block" : "none";
    }
  } catch (err) {
    console.error("Errore di connessione:", err);
  }
}

// Aggiunta tracce alla playlist (POST semantico RESTful)
document.getElementById("add-selected-btn").onclick = async () => {
  if (selectedLikedTracks.size === 0) {
    alert("Seleziona almeno una traccia!");
    return;
  }

  const trackIds = Array.from(selectedLikedTracks);
  try {
    const res = await fetch(`/api/v1/playlists/${playlistId}/tracks`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track_ids: trackIds })
    });

    if (res.ok) {
      const autoRemoveCheck = document.getElementById("auto-remove-check");
      if (autoRemoveCheck && autoRemoveCheck.checked) {
        // Rimuove dai preferiti via DELETE /api/v1/me/tracks
        try {
          await fetch("/api/v1/me/tracks", {
            method: "DELETE",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ track_ids: trackIds })
          });
        } catch (rmErr) {
          console.error("Errore rimozione dai preferiti:", rmErr);
        }
      }

      alert("Brani aggiunti con successo!");
      selectedLikedTracks.clear();
      await loadPlaylistInfo();
      await loadLikedTracks(true);
    } else {
      const err = await res.json();
      alert("Errore nell'aggiunta: " + (err.message || err.error));
    }
  } catch (err) {
    alert("Errore di connessione: " + err);
  }
};

// Ridenominazione playlist (PATCH semantico RESTful)
document.getElementById("rename-btn").onclick = async () => {
  const currentName = document.getElementById("playlist-name").textContent;
  const newName = prompt("Nuovo nome playlist:", currentName);
  if (!newName || newName.trim() === "" || newName.trim() === currentName) return;

  try {
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
  } catch (err) {
    alert("Errore di connessione: " + err);
  }
};

const publicToggle = document.getElementById("public-toggle");
if (publicToggle) {
  publicToggle.onchange = async (e) => {
    try {
      const isPublic = e.target.checked;
      const r = await fetch(`/api/v1/playlists/${playlistId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public: isPublic })
      });
      if (!r.ok) {
        const err = await r.json();
        alert("Errore modifica stato pubblico: " + (err.message || err.error));
        e.target.checked = !isPublic;
      }
    } catch (err) {
      alert("Errore di connessione: " + err);
    }
  };
}

document.getElementById("show-more").onclick = () => loadLikedTracks(false);

let searchTimeout = null;
document.getElementById("search-bar").oninput = (e) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    currentQuery = e.target.value.trim();
    loadLikedTracks(true);
  }, 300);
};

loadPlaylistInfo();
loadLikedTracks(true);
