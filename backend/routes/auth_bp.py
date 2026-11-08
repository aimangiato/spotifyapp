from flask import Blueprint, request, session, redirect, jsonify
from backend.services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    """Avvia il flusso OAuth 2.0 con generazione di uno state crittografico anti-CSRF (SEC-03)."""
    auth_service = AuthService()
    state = auth_service.generate_state()
    session["oauth_state"] = state
    auth_url = auth_service.get_authorize_url(state=state)
    return redirect(auth_url)


@auth_bp.route("/callback")
def callback():
    """Callback OAuth 2.0 con validazione rigorosa anti-CSRF e salvataggio token in sessione (SEC-02, SEC-03)."""
    auth_service = AuthService()

    # 1. Verifica State Anti-CSRF in tempo costante
    returned_state = request.args.get("state")
    saved_state = session.pop("oauth_state", None)

    if not auth_service.validate_state(returned_state, saved_state):
        return jsonify({
            "error": "invalid_state",
            "message": "Validazione anti-CSRF fallita: lo state non corrisponde."
        }), 400

    # 2. Gestione errori restituiti da Spotify
    spotify_error = request.args.get("error")
    if spotify_error:
        return jsonify({
            "error": "access_denied",
            "message": f"Autorizzazione rifiutata da Spotify: {spotify_error}"
        }), 403

    # 3. Verifica presenza authorization code
    code = request.args.get("code")
    if not code:
        return jsonify({
            "error": "missing_code",
            "message": "Nessun codice fornito da Spotify"
        }), 400

    # 4. Scambio authorization code con access token
    try:
        token_info = auth_service.get_access_token(code)
        if not token_info:
            return jsonify({
                "error": "auth_failed",
                "message": "Impossibile recuperare il token"
            }), 400
    except Exception as e:
        return jsonify({
            "error": "auth_failed",
            "message": f"Errore durante lo scambio del token: {str(e)}"
        }), 400

    return redirect("/")


@auth_bp.route("/logout")
def logout():
    """Termina la sessione utente eliminando cookie e dati di autenticazione."""
    AuthService.clear_session()
    return redirect("/")
