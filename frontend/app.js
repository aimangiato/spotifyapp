function showLoader() {
  const loader = document.getElementById('loader');
  if (loader) loader.classList.remove('hidden');
}

function hideLoader() {
  const loader = document.getElementById('loader');
  if (loader) loader.classList.add('hidden');
}

async function fetchWithLoader(url, options = {}) {
  showLoader();
  try {
    return await fetch(url, options);
  } finally {
    hideLoader();
  }
}

document.getElementById('login').onclick = () => {
  window.location = '/login';
};

async function getMe() {
  try {
    const r = await fetch('/api/v1/me', { credentials: 'include' });
    if (r.status === 200) {
      const data = await r.json();
      document.getElementById('user').innerText = `Logged in as ${data.display_name} (${data.id})`;
    } else {
      document.getElementById('user').innerText = 'Not logged in';
    }
  } catch (err) {
    document.getElementById('user').innerText = 'Not logged in';
  }
}

document.getElementById('create-pl').onclick = async () => {
  const nameInput = document.getElementById('pl-name');
  const name = nameInput.value.trim();
  if (!name) {
    alert("Inserisci un nome valido per la playlist");
    return;
  }

  try {
    const r = await fetch('/api/v1/playlists', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, public: false, description: 'Created via App' })
    });

    const res = await r.json();
    if (r.status === 201) {
      alert(`Playlist creata con successo: ${res.name}`);
      nameInput.value = '';
      loadPlaylists();
    } else {
      alert(`Errore: ${res.message || res.error}`);
    }
  } catch (err) {
    alert(`Errore di connessione: ${err}`);
  }
};

async function loadPlaylists() {
  try {
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
  } catch (err) {
    alert(`Errore nel caricamento delle playlist: ${err}`);
  }
}

document.getElementById('load-playlists').onclick = loadPlaylists;

window.editPlaylist = (id) => {
  window.location = `/edit.html?playlist_id=${id}`;
};

getMe();
