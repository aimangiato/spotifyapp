const params = new URLSearchParams(window.location.search);
const playlistId = params.get("playlist_id");

let likedOffset = 0;
let currentQuery = "";

async function loadPlaylistInfo() {
  const r = await fetch(`/api/playlist/${playlistId}`);
  const data = await r.json();

  if (data.error) {
    console.error("Errore:", data.error);
    return;
  }

  // Nome playlist
  document.getElementById("playlist-name").textContent = data.name;

  // Lista brani
  const list = document.getElementById("playlist-tracks");
  list.innerHTML = "";

  data.tracks.forEach(track => {
    const div = document.createElement("div");
    div.classList.add("track-item");

    div.innerHTML = `
      <span>${track.name} — ${track.artist}</span>
      <button data-id="${track.id}" class="remove">Rimuovi</button>
    `;

    list.appendChild(div);
  });
}


let selectedLikedTracks = new Set();

async function loadLikedTracks() {
  const r = await fetch(`/api/liked_tracks?offset=${likedOffset}&q=${encodeURIComponent(currentQuery)}`);
  const data = await r.json();

  const list = document.getElementById("liked-tracks");

  data.forEach(t => {
    const div = document.createElement("div");

    div.className = "track-item";

    div.innerHTML = `
      <label>
        <input type="checkbox" class="liked-checkbox" data-id="${t.id}">
        <strong>${t.name}</strong> — ${t.artist}
      </label>
    `;

    // Quando selezioni/deselezioni la traccia
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
  likedOffset += 20;
}

document.getElementById("add-selected-btn").onclick = async () => {
  if (selectedLikedTracks.size === 0) {
    alert("Seleziona almeno una traccia!");
    return;
  }

  const trackIds = Array.from(selectedLikedTracks);

  const res = await fetch(`/api/add_tracks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({playlist_id: playlistId, track_ids: trackIds })
  });

  const data = await res.json();

  if (res.ok) {
    alert("Brani aggiunti!");
    selectedLikedTracks.clear();
    document.querySelectorAll(".liked-checkbox").forEach(cb => cb.checked = false);
    await loadPlaylistInfo(); // aggiorna playlist
  } else {
    alert("Errore nell'aggiunta dei brani: " + data.error);
  }
};


document.getElementById("show-more").onclick = loadLikedTracks;
document.getElementById("search-bar").oninput = (e) => {
  currentQuery = e.target.value;
  likedOffset = 0;
  document.getElementById("liked-tracks").innerHTML = "";
  loadLikedTracks();
};

document.getElementById("rename-btn").onclick = async () => {
  const currentName = document.getElementById("playlist-name").textContent;

  const newName = prompt("Nuovo nome playlist:", currentName)
  if(!newName || newName.trim() === "") return;

  const r = await fetch(`/api/playlist/${playlistId}/rename`, {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify({name: newName})

  });

  const data = await r.json();

  if(data.error){
    alert("Errore: " + data.error);
    return;
  }
  alert("Nome modificato con successo!");
  document.getElementById("playlist-name").textContent = data.name;
};

loadPlaylistInfo();
loadLikedTracks();
