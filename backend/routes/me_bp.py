from flask import Blueprint, request, jsonify
from backend.auth.decorators import require_auth
from backend.services.track_service import TrackService
from backend.schemas.playlist_schemas import LikedTracksQuerySchema, ModifyTracksSchema

me_bp = Blueprint("me", __name__)

liked_query_schema = LikedTracksQuerySchema()
modify_tracks_schema = ModifyTracksSchema()


@me_bp.route("", methods=["GET"])
@require_auth
def get_current_user(sp):
    """Restituisce il profilo dell'utente autenticato."""
    user = sp.current_user()
    return jsonify({
        "id": user.get("id"),
        "display_name": user.get("display_name", user.get("id")),
        "email": user.get("email"),
        "images": user.get("images", [])
    }), 200


@me_bp.route("/tracks", methods=["GET"])
@require_auth
def get_user_liked_tracks(sp):
    """Restituisce i brani preferiti dell'utente con paginazione on-demand (PERF-02)."""
    query_params = liked_query_schema.load(request.args.to_dict())
    service = TrackService(sp)
    result = service.get_liked_tracks(
        limit=query_params["limit"],
        offset=query_params["offset"],
        query=query_params.get("q", "")
    )
    return jsonify(result), 200


@me_bp.route("/tracks", methods=["DELETE"])
@require_auth
def remove_user_liked_tracks(sp):
    """Rimuove brani dai preferiti dell'utente."""
    payload = modify_tracks_schema.load(request.get_json() or {})
    service = TrackService(sp)
    result = service.remove_saved_tracks(payload["track_ids"])
    return jsonify(result), 200
