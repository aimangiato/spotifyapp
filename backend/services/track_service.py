from typing import Optional, Dict, Any, List


class TrackService:
    """Service layer per la gestione dei brani musicali e manipolazioni difensive."""

    def __init__(self, sp):
        self.sp = sp

    @staticmethod
    def extract_track_data(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Estrae i metadati della traccia in modo rigorosamente null-safe (PERF-04)."""
        if not item or not isinstance(item, dict):
            return None

        track = item.get("track")
        if not track or not isinstance(track, dict) or not track.get("id"):
            return None

        # Safe extraction per le immagini copertina
        album = track.get("album") or {}
        images = album.get("images") or []
        cover_url = images[0]["url"] if len(images) > 0 and isinstance(images[0], dict) and "url" in images[0] else None

        # Safe extraction per gli artisti
        artists = track.get("artists") or []
        artist_names = ", ".join(
            artist["name"] for artist in artists if isinstance(artist, dict) and "name" in artist
        ) or "Artista sconosciuto"

        return {
            "id": track["id"],
            "name": track.get("name", "Traccia senza titolo"),
            "artist": artist_names,
            "coverart": cover_url,
            "duration_ms": track.get("duration_ms", 0),
            "uri": track.get("uri", f"spotify:track:{track['id']}")
        }

    def get_liked_tracks(self, limit: int = 20, offset: int = 0, query: str = "") -> dict:
        """Paginazione on-demand dei brani preferiti senza memorizzazione di stato globale (PERF-02)."""
        clean_query = query.strip().lower() if query else ""

        if not clean_query:
            results = self.sp.current_user_saved_tracks(limit=limit, offset=offset)
            items = results.get("items", [])
            total = results.get("total", 0)

            formatted_tracks = []
            for item in items:
                track_dto = self.extract_track_data(item)
                if track_dto:
                    formatted_tracks.append(track_dto)

            return {
                "items": formatted_tracks,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total
            }

        # Ricerca con filtro per query
        # Recupera in batch controllati per evitare starvation o blocchi infiniti
        all_matches = []
        batch_limit = 50
        curr_offset = 0
        max_scan = 200  # Limite difensivo di scansione per prevenire 504 Gateway Timeout

        while curr_offset < max_scan:
            results = self.sp.current_user_saved_tracks(limit=batch_limit, offset=curr_offset)
            items = results.get("items", [])
            if not items:
                break

            for item in items:
                track_dto = self.extract_track_data(item)
                if track_dto:
                    name_match = clean_query in track_dto["name"].lower()
                    artist_match = clean_query in track_dto["artist"].lower()
                    if name_match or artist_match:
                        all_matches.append(track_dto)

            curr_offset += batch_limit
            if curr_offset >= results.get("total", 0):
                break

        paginated = all_matches[offset:offset + limit]
        return {
            "items": paginated,
            "total": len(all_matches),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < len(all_matches)
        }

    def remove_saved_tracks(self, track_ids: List[str]) -> dict:
        """Rimuove uno o più brani dai preferiti dell'utente."""
        if not track_ids:
            return {"status": "no_op", "removed_count": 0}
        self.sp.current_user_saved_tracks_delete(track_ids)
        return {"status": "ok", "removed_count": len(track_ids)}
