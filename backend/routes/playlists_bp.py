from flask import Blueprint, request, jsonify
from backend.auth.decorators import require_auth
from backend.services.playlist_service import PlaylistService
from backend.schemas.playlist_schemas import (
    CreatePlaylistSchema,
    UpdatePlaylistSchema,
    ModifyTracksSchema,
)

playlists_bp = Blueprint("playlists", __name__)

create_schema = CreatePlaylistSchema()
update_schema = UpdatePlaylistSchema()
modify_tracks_schema = ModifyTracksSchema()


@playlists_bp.route("", methods=["GET"])
@require_auth
def list_playlists(sp):
    """Restituisce le playlist dell'utente con paginazione ottimizzata a singola chiamata (PERF-01)."""
    service = PlaylistService(sp)
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    data = service.get_user_playlists(limit=limit, offset=offset)
    return jsonify(data), 200


@playlists_bp.route("", methods=["POST"])
def create_playlist():
    """Crea una nuova playlist Spotify (RESTful 201 Created). Valida prima il payload con Marshmallow."""
    payload = create_schema.load(request.get_json() or {})

    @require_auth
    def _create(sp):
        service = PlaylistService(sp)
        created = service.create_playlist(
            name=payload["name"],
            public=payload.get("public", False),
            description=payload.get("description", "")
        )
        return jsonify(created), 201

    return _create()


@playlists_bp.route("/<playlist_id>", methods=["GET"])
@require_auth
def get_playlist(sp, playlist_id):
    """Restituisce i dettagli e i brani di una singola playlist (PERF-04)."""
    service = PlaylistService(sp)
    data = service.get_playlist_details(playlist_id)
    return jsonify(data), 200


@playlists_bp.route("/<playlist_id>", methods=["PATCH"])
def update_playlist(playlist_id):
    """Modifica i dettagli di una playlist (nome, privacy, descrizione). Valida prima il payload."""
    payload = update_schema.load(request.get_json() or {})

    @require_auth
    def _update(sp):
        service = PlaylistService(sp)
        res = service.update_playlist_details(playlist_id, **payload)
        return jsonify(res), 200

    return _update()


@playlists_bp.route("/<playlist_id>/tracks", methods=["POST"])
def add_tracks(playlist_id):
    """Aggiunge brani a una playlist con chunking automatico (PERF-03). Valida prima il payload."""
    payload = modify_tracks_schema.load(request.get_json() or {})

    @require_auth
    def _add(sp):
        service = PlaylistService(sp)
        try:
            res = service.add_tracks_to_playlist(playlist_id, payload["track_ids"])
        except ValueError as e:
            return jsonify({
                "error": "duplicate_tracks",
                "message": str(e)
            }), 400

        return jsonify(res), 200

    return _add()


@playlists_bp.route("/<playlist_id>/tracks", methods=["DELETE"])
def remove_tracks(playlist_id):
    """Rimuove brani da una playlist con chunking automatico (PERF-03). Valida prima il payload."""
    payload = modify_tracks_schema.load(request.get_json() or {})

    @require_auth
    def _remove(sp):
        service = PlaylistService(sp)
        res = service.remove_tracks_from_playlist(playlist_id, payload["track_ids"])
        return jsonify(res), 200

    return _remove()
