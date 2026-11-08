"""
Modulo di utility per l'interazione con l'API Spotify.
Tutte le funzioni sono pure e stateless per garantire l'isolamento dei dati multi-tenant.
"""

def load_all_liked_tracks(sp):
    """
    Recupera tutti i brani preferiti dell'utente autenticato direttamente dalle API Spotify.
    Funzione pura senza memorizzazione in cache globale (SEC-01: fix data-leakage multi-tenant).
    """
    all_tracks = []
    offset = 0
    limit = 50

    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        items = results.get("items", [])
        if not items:
            break

        for item in items:
            track = item.get("track")
            if not track:
                continue
            all_tracks.append({
                "id": track.get("id"),
                "name": track.get("name"),
                "artist": ", ".join(a["name"] for a in track.get("artists", []) if "name" in a),
            })

        offset += limit
        if offset >= results.get("total", 0):
            break

    return all_tracks
