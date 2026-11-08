from typing import List, Generator, Optional
from backend.services.track_service import TrackService


def chunk_list(items: List[str], chunk_size: int = 100) -> Generator[List[str], None, None]:
    """Generatore per suddividere liste in blocchi di dimensione massima chunk_size (PERF-03)."""
    if not items or chunk_size <= 0:
        return
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


class PlaylistService:
    """Service layer per la gestione delle playlist Spotify e operazioni batch."""

    def __init__(self, sp):
        self.sp = sp

    def get_user_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        """Recupera le playlist dell'utente con una singola chiamata HTTP ottimizzata (PERF-01)."""
        results = self.sp.current_user_playlists(limit=limit, offset=offset)

        playlists = []
        for pl in results.get("items", []):
            if not pl:
                continue
            playlists.append({
                "id": pl.get("id"),
                "name": pl.get("name", "Senza titolo"),
                "tracks_total": pl.get("tracks", {}).get("total", 0) if isinstance(pl.get("tracks"), dict) else 0,
                "is_public": pl.get("public", False),
                "owner": pl.get("owner", {}).get("display_name", "") if isinstance(pl.get("owner"), dict) else ""
            })

        total = results.get("total", len(playlists))
        return {
            "items": playlists,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total
        }

    def create_playlist(self, name: str, public: bool = False, description: str = "") -> dict:
        """Crea una nuova playlist per l'utente autenticato."""
        user = self.sp.current_user()
        user_id = user["id"]
        return self.sp.user_playlist_create(
            user_id,
            name=name,
            public=public,
            description=description
        )

    def get_playlist_details(self, playlist_id: str, limit: int = 100, offset: int = 0) -> dict:
        """Recupera le informazioni e i brani di una playlist in modo difensivo e paginato (PERF-04, PERF-05)."""
        playlist = self.sp.playlist(
            playlist_id,
            fields="id,name,public,description,tracks.total,tracks.items(track(id,name,artists(name),album(images),duration_ms,uri))"
        )

        tracks_items = playlist.get("tracks", {}).get("items", []) if isinstance(playlist.get("tracks"), dict) else []
        tracks = []
        existing_ids = []

        for item in tracks_items:
            track_dto = TrackService.extract_track_data(item)
            if track_dto:
                tracks.append(track_dto)
                existing_ids.append(track_dto["id"])

        total_tracks = playlist.get("tracks", {}).get("total", len(tracks)) if isinstance(playlist.get("tracks"), dict) else len(tracks)

        return {
            "id": playlist.get("id", playlist_id),
            "name": playlist.get("name", "Playlist senza nome"),
            "public": playlist.get("public", False),
            "description": playlist.get("description", ""),
            "tracks": tracks,
            "existing_ids": existing_ids,
            "total": total_tracks
        }

    def update_playlist_details(self, playlist_id: str, **kwargs) -> dict:
        """Aggiorna i metadati della playlist (nome, stato pubblico, descrizione)."""
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return {"status": "no_changes"}

        self.sp.playlist_change_details(playlist_id, **update_data)
        return {"status": "ok", **update_data}

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> dict:
        """Aggiunge brani a una playlist con chunking sicuro <= 100 ed evitando duplicati (PERF-03)."""
        if not track_ids:
            return {"status": "success", "tracks_added": 0}

        uris_to_add = [
            f"spotify:track:{tid}" if not tid.startswith("spotify:track:") else tid
            for tid in track_ids
        ]

        # Verifica duplicati leggendo i brani correnti
        existing_uris = set()
        offset = 0
        limit = 100

        while True:
            batch = self.sp.playlist_items(
                playlist_id,
                fields="items.track.uri,total",
                offset=offset,
                limit=limit
            )
            items = batch.get("items", []) if isinstance(batch, dict) else []
            if not items:
                break

            for item in items:
                if item and isinstance(item, dict) and item.get("track") and isinstance(item["track"], dict):
                    uri = item["track"].get("uri")
                    if uri:
                        existing_uris.add(uri)

            offset += limit
            if offset >= batch.get("total", 0):
                break

        duplicate_uris = [uri for uri in uris_to_add if uri in existing_uris]
        if duplicate_uris:
            raise ValueError(f"{len(duplicate_uris)} brani selezionati sono già presenti nella playlist.")

        # Chunking a blocchi di max 100 URI
        added_count = 0
        for batch in chunk_list(uris_to_add, chunk_size=100):
            self.sp.playlist_add_items(playlist_id, batch)
            added_count += len(batch)

        return {
            "status": "success",
            "tracks_added": added_count
        }

    def remove_tracks_from_playlist(self, playlist_id: str, track_ids: List[str]) -> dict:
        """Rimuove brani da una playlist con chunking sicuro <= 100 (PERF-03)."""
        if not track_ids:
            return {"status": "ok", "tracks_removed": 0}

        removed_count = 0
        for batch in chunk_list(track_ids, chunk_size=100):
            self.sp.playlist_remove_all_occurrences_of_items(playlist_id, batch)
            removed_count += len(batch)

        return {
            "status": "ok",
            "tracks_removed": removed_count
        }
