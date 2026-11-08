import os
import unittest
from unittest.mock import MagicMock, patch

os.environ["SPOTIPY_CLIENT_ID"] = "test_client_id"
os.environ["SPOTIPY_CLIENT_SECRET"] = "test_client_secret"
os.environ["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8080/callback"
os.environ["FLASK_SECRET_KEY"] = "super_secure_random_key_for_testing_123456"

import backend.app as app_module


class ApiEndpointsSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = app_module.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_unauthenticated_me_endpoint_returns_401(self):
        res = self.client.get("/api/me")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json(), {"error": "not_authenticated"})

    def test_unauthenticated_search_returns_401_or_400(self):
        # Missing query parameter
        res = self.client.get("/api/search")
        self.assertEqual(res.status_code, 400)
        # With query parameter but unauthenticated
        res = self.client.get("/api/search?q=radiohead")
        self.assertEqual(res.status_code, 401)

    def test_unauthenticated_playlists_endpoint_returns_401(self):
        res = self.client.get("/api/playlists")
        self.assertEqual(res.status_code, 401)

    def test_unauthenticated_liked_tracks_returns_401(self):
        res = self.client.get("/api/liked_tracks")
        self.assertEqual(res.status_code, 401)

    def test_unauthenticated_create_playlist_returns_401_or_400(self):
        # Missing name
        res = self.client.post("/api/create_playlist", json={})
        self.assertEqual(res.status_code, 400)
        # With name but unauthenticated
        res = self.client.post("/api/create_playlist", json={"name": "New Playlist"})
        self.assertEqual(res.status_code, 401)

    def test_logout_clears_session(self):
        with self.client as c:
            with c.session_transaction() as sess:
                sess["token_info"] = {"access_token": "dummy"}
                sess["custom_data"] = 123

            res = c.get("/logout")
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers["Location"], "/")

            with c.session_transaction() as sess_after:
                self.assertEqual(len(sess_after), 0)


if __name__ == "__main__":
    unittest.main()
