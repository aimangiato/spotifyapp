import os
import unittest
from unittest.mock import MagicMock, patch
import importlib

# Ensure environment has keys for tests
os.environ["SPOTIPY_CLIENT_ID"] = "test_client_id"
os.environ["SPOTIPY_CLIENT_SECRET"] = "test_client_secret"
os.environ["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8080/callback"
os.environ["FLASK_SECRET_KEY"] = "super_secure_random_key_for_testing_123456"

import backend.utils as utils
import backend.spotify_oauth as spotify_oauth
import backend.app as app_module
from spotipy.cache_handler import FlaskSessionCacheHandler


class SecurityAndAuthHardeningTests(unittest.TestCase):
    def setUp(self):
        self.app = app_module.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    # =========================================================================
    # SEC-01: No global cache or data leakage in backend/utils.py
    # =========================================================================
    def test_sec01_no_global_variables_in_utils(self):
        """Verifica che le variabili globali di cache siano state eliminate da backend/utils.py."""
        self.assertFalse(hasattr(utils, "_cached_liked_tracks"), "_cached_liked_tracks must not exist")
        self.assertFalse(hasattr(utils, "_last_cache_time"), "_last_cache_time must not exist")
        self.assertFalse(hasattr(utils, "LIKED_CACHE_TTL"), "LIKED_CACHE_TTL must not exist")

    def test_sec01_load_all_liked_tracks_is_pure_and_isolated(self):
        """Verifica che load_all_liked_tracks sia pura e non condivida dati tra chiamate diverse."""
        mock_sp_user_a = MagicMock()
        mock_sp_user_a.current_user_saved_tracks.return_value = {
            "total": 1,
            "items": [
                {
                    "track": {
                        "id": "track_a",
                        "name": "Song A",
                        "artists": [{"name": "Artist A"}],
                    }
                }
            ],
        }

        mock_sp_user_b = MagicMock()
        mock_sp_user_b.current_user_saved_tracks.return_value = {
            "total": 1,
            "items": [
                {
                    "track": {
                        "id": "track_b",
                        "name": "Song B",
                        "artists": [{"name": "Artist B"}],
                    }
                }
            ],
        }

        tracks_a = utils.load_all_liked_tracks(mock_sp_user_a)
        tracks_b = utils.load_all_liked_tracks(mock_sp_user_b)

        self.assertEqual(len(tracks_a), 1)
        self.assertEqual(tracks_a[0]["name"], "Song A")
        self.assertEqual(len(tracks_b), 1)
        self.assertEqual(tracks_b[0]["name"], "Song B")
        self.assertNotEqual(tracks_a, tracks_b, "User A and User B tracks must be isolated!")

    # =========================================================================
    # SEC-02: Isolamento credenziali tramite FlaskSessionCacheHandler
    # =========================================================================
    def test_sec02_spotify_oauth_uses_flask_session_cache_handler(self):
        """Verifica che get_spotify_oauth utilizzi FlaskSessionCacheHandler e non il file .cache."""
        with self.app.test_request_context("/"):
            sp_oauth = spotify_oauth.get_spotify_oauth()
            self.assertIsInstance(sp_oauth.cache_handler, FlaskSessionCacheHandler)
            # Verifica che nessun file .cache sia presente su disco
            self.assertFalse(os.path.exists(".cache"), ".cache file must never be created on disk")

    def test_sec02_spotify_oauth_raises_on_missing_env(self):
        """Verifica che get_spotify_oauth sollevi ValueError se mancano le variabili d'ambiente."""
        with patch.dict(os.environ, {"SPOTIPY_CLIENT_ID": ""}):
            with self.app.test_request_context("/"):
                with self.assertRaises(ValueError):
                    spotify_oauth.get_spotify_oauth()

    # =========================================================================
    # SEC-03: OAuth 2.0 State Anti-CSRF
    # =========================================================================
    def test_sec03_login_sets_state_in_session_and_redirects_with_state(self):
        """Verifica che /login generi un parametro state crittografico e lo includa nel redirect."""
        with self.client as c:
            response = c.get("/login")
            self.assertEqual(response.status_code, 302)
            redirect_url = response.headers["Location"]
            self.assertIn("state=", redirect_url)

            # Verifica che lo state sia memorizzato nella sessione
            with c.session_transaction() as sess:
                saved_state = sess.get("oauth_state")
                self.assertIsNotNone(saved_state)
                self.assertGreater(len(saved_state), 20)
                self.assertIn(f"state={saved_state}", redirect_url)

    def test_sec03_callback_fails_without_state(self):
        """Verifica che /callback rifiuti richieste senza parametro state (HTTP 400)."""
        response = self.client.get("/callback?code=fake_code")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["error"], "invalid_state")

    def test_sec03_callback_fails_with_mismatched_state(self):
        """Verifica che /callback rifiuti richieste con state non corrispondente (attacco CSRF)."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["oauth_state"] = "legitimate_session_state_token"

            response = c.get("/callback?code=fake_code&state=attacker_state_token")
            self.assertEqual(response.status_code, 400)
            data = response.get_json()
            self.assertEqual(data["error"], "invalid_state")

    def test_sec03_callback_fails_with_missing_code(self):
        """Verifica che /callback rifiuti richieste con state valido ma senza code."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["oauth_state"] = "valid_state_123"

            response = c.get("/callback?state=valid_state_123")
            self.assertEqual(response.status_code, 400)
            data = response.get_json()
            self.assertEqual(data["error"], "missing_code")

    def test_sec03_callback_handles_spotify_access_denied(self):
        """Verifica che /callback gestisca l'errore di accesso negato da Spotify."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["oauth_state"] = "valid_state_123"

            response = c.get("/callback?state=valid_state_123&error=access_denied")
            self.assertEqual(response.status_code, 403)
            data = response.get_json()
            self.assertEqual(data["error"], "access_denied")

    @patch("backend.app.get_spotify_oauth")
    def test_sec03_callback_success_with_valid_state_and_code(self, mock_get_oauth):
        """Verifica che /callback accetti codici validi con state corrispondente e reindirizzi a /."""
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_access_token.return_value = {
            "access_token": "valid_token",
            "refresh_token": "valid_refresh",
            "expires_at": 9999999999,
            "scope": "user-library-read"
        }
        mock_get_oauth.return_value = mock_oauth_instance

        with self.client as c:
            with c.session_transaction() as sess:
                sess["oauth_state"] = "test_matching_state"

            response = c.get("/callback?state=test_matching_state&code=valid_test_code")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/")

            # Verifica che lo state sia stato consumato dalla sessione (anti-replay)
            with c.session_transaction() as sess_after:
                self.assertNotIn("oauth_state", sess_after)

    # =========================================================================
    # SEC-04: Hardening Secret Key, Cookie e CORS
    # =========================================================================
    def test_sec04_secret_key_rejection(self):
        """Verifica che il backend rifiuti di avviarsi se FLASK_SECRET_KEY manca o è 'dev_secret'."""
        try:
            with patch.dict(os.environ, {"FLASK_SECRET_KEY": "dev_secret"}):
                with self.assertRaises(RuntimeError) as ctx:
                    importlib.reload(app_module)
                self.assertIn("ERRORE SICUREZZA", str(ctx.exception))

            with patch.dict(os.environ, {"FLASK_SECRET_KEY": ""}):
                with self.assertRaises(RuntimeError) as ctx:
                    importlib.reload(app_module)
                self.assertIn("ERRORE SICUREZZA", str(ctx.exception))
        finally:
            os.environ["FLASK_SECRET_KEY"] = "super_secure_random_key_for_testing_123456"
            importlib.reload(app_module)

    def test_sec04_cookie_security_flags(self):
        """Verifica che le impostazioni dei cookie di sessione siano conformi ai requisiti di hardening."""
        config = self.app.config
        self.assertTrue(config.get("SESSION_COOKIE_HTTPONLY"), "SESSION_COOKIE_HTTPONLY must be True")
        self.assertEqual(config.get("SESSION_COOKIE_SAMESITE"), "Lax", "SESSION_COOKIE_SAMESITE must be Lax")
        self.assertEqual(config.get("PERMANENT_SESSION_LIFETIME"), 3600, "Session lifetime must be 1 hour")

    # =========================================================================
    # SEC-05: Disattivazione debugger Werkzeug
    # =========================================================================
    def test_sec05_debug_disabled_by_default(self):
        """Verifica che FLASK_DEBUG default sia disattivato per prevenire RCE."""
        debug_env = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
        self.assertFalse(debug_env, "FLASK_DEBUG must be disabled by default")


if __name__ == "__main__":
    unittest.main()
