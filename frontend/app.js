function showLoader() {
  document.getElementById('loader').classList.remove('hidden');
}

function hideLoader() {
  document.getElementById('loader').classList.add('hidden');
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
  const r = await fetch('/api/me', { credentials: 'include' });
  if (r.status === 200) {
    const data = await r.json();
    document.getElementById('user').innerText = `Logged in as ${data.display_name} (${data.id})`;
  } else {
    document.getElementById('user').innerText = 'Not logged in';
  }
}

document.getElementById('create-pl').onclick = async () => {
  const name = document.getElementById('pl-name').value;
  const r = await fetch('/api/create_playlist', {
    method:'POST',
    credentials:'include',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, public:false, description:'Created via demo'})
  });
  const res = await r.json();
  console.log(res);
  alert('Created playlist: ' + (res.name || JSON.stringify(res)));
};

document.getElementById('load-playlists').onclick = async () => {
  const r = await fetchWithLoader('/api/playlists', { credentials: 'include' });
  if (r.status !== 200) {
    alert('Devi prima fare login!');
    return;
  }
  const data = await r.json();
  const container = document.getElementById('playlists');
  container.innerHTML = ''; // pulisce precedente contenuto

  if (data.length === 0) {
    container.innerHTML = '<p>Nessuna playlist trovata.</p>';
    return;
  }

  data.forEach(pl => {
    const div = document.createElement('div');
    div.className = 'playlist';
    div.innerHTML = `
      <strong>${pl.name}</strong><br>
      ${pl.created_at ? new Date(pl.created_at).toLocaleString() : 'Data non disponibile'}<br>
      ${pl.tracks_total} tracce
      <button onclick="editPlaylist('${pl.id}')">Edit</button>
      <hr>
    `;
    container.appendChild(div);
  });

  window.editPlaylist = (id) => {
    window.location = `/edit.html?playlist_id=${id}`;
  };
};


getMe();
