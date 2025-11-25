from functools import lru_cache
import time

LIKED_CACHE_TTL = 60 * 5  # 5 minuti
_last_cache_time = 0
_cached_liked_tracks = []


def load_all_liked_tracks(sp):
    global _last_cache_time, _cached_liked_tracks

    # Cache valida?
    if time.time() - _last_cache_time < LIKED_CACHE_TTL:
        return _cached_liked_tracks

    all_tracks = []
    offset = 0
    limit = 50

    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        items = results.get("items", [])
        if not items:
            break

        for item in items:
            track = item["track"]
            all_tracks.append({
                "id": track["id"],
                "name": track["name"],
                "artist": ", ".join(a["name"] for a in track["artists"]),
                "coverart": track["album"]["images"][0]["url"]
            })

        offset += limit
        if offset >= results["total"]:
            break

    _cached_liked_tracks = all_tracks
    _last_cache_time = time.time()
    return all_tracks
