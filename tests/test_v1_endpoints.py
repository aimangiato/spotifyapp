import os
import unittest
from unittest.mock import MagicMock, patch

os.environ["SPOTIPY_CLIENT_ID"] = "test_client_id"
os.environ["SPOTIPY_CLIENT_SECRET"] = "test_client_secret"
os.environ["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8080/callback"
os.environ["FLASK_SECRET_KEY"] = "super_secure_random_key_for_testing_123456"

from backend import create_app


class V1RestfulEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_unauthenticated_v1_me_returns_401(self):
        res = self.client.get("/api/v1/me")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertEqual(data["error"], "unauthorized")

    def test_unauthenticated_v1_playlists_returns_401(self):
        res = self.client.get("/api/v1/playlists")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertEqual(data["error"], "unauthorized")

    def test_unauthenticated_v1_create_playlist_returns_401_or_400(self):
        # Body invalido: name vuoto -> 400 validation_error
        res = self.client.post("/api/v1/playlists", json={"name": ""})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data["error"], "validation_error")

    @patch("backend.auth.decorators.get_spotify_oauth")
    def test_authenticated_v1_create_playlist_success_201(self, mock_oauth):
        mock_oauth_inst = MagicMock()
        mock_oauth_inst.cache_handler.get_cached_token.return_value = {"access_token": "token123"}
        mock_oauth_inst.validate_token.return_value = {"access_token": "token123"}
        mock_oauth.return_value = mock_oauth_inst

        with patch("spotipy.Spotify") as mock_spotify_cls:
            mock_sp = MagicMock()
            mock_spotify_cls.return_value = mock_sp
            mock_sp.current_user.return_value = {"id": "user_abc"}
            mock_sp.user_playlist_create.return_value = {
                "id": "new_pl_id",
                "name": "My New Playlist",
                "public": False
            }

            res = self.client.post(
                "/api/v1/playlists",
                json={"name": "My New Playlist", "public": False}
            )
            self.assertEqual(res.status_code, 201)
            data = res.get_json()
            self.assertEqual(data["id"], "new_pl_id")
            self.assertEqual(data["name"], "My New Playlist")

    @patch("backend.auth.decorators.get_spotify_oauth")
    def test_authenticated_v1_list_playlists_envelope(self, mock_oauth):
        mock_oauth_inst = MagicMock()
        mock_oauth_inst.cache_handler.get_cached_token.return_value = {"access_token": "token123"}
        mock_oauth_inst.validate_token.return_value = {"access_token": "token123"}
        mock_oauth.return_value = mock_oauth_inst

        with patch("spotipy.Spotify") as mock_spotify_cls:
            mock_sp = MagicMock()
            mock_spotify_cls.return_value = mock_sp
            mock_sp.current_user_playlists.return_value = {
                "items": [
                    {"id": "pl1", "name": "Favorites", "tracks": {"total": 12}, "public": True}
                ],
                "total": 1
            }

            res = self.client.get("/api/v1/playlists")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn("items", data)
            self.assertEqual(len(data["items"]), 1)
            self.assertEqual(data["total"], 1)
            self.assertIn("has_more", data)

    @patch("backend.auth.decorators.get_spotify_oauth")
    def test_authenticated_v1_patch_playlist(self, mock_oauth):
        mock_oauth_inst = MagicMock()
        mock_oauth_inst.cache_handler.get_cached_token.return_value = {"access_token": "token123"}
        mock_oauth_inst.validate_token.return_value = {"access_token": "token123"}
        mock_oauth.return_value = mock_oauth_inst

        with patch("spotipy.Spotify") as mock_spotify_cls:
            mock_sp = MagicMock()
            mock_spotify_cls.return_value = mock_sp

            res = self.client.patch("/api/v1/playlists/pl_123", json={"name": "Renamed Playlist"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data["status"], "ok")
            mock_sp.playlist_change_details.assert_called_once_with("pl_123", name="Renamed Playlist")

    @patch("backend.auth.decorators.get_spotify_oauth")
    def test_authenticated_v1_add_and_remove_tracks(self, mock_oauth):
        mock_oauth_inst = MagicMock()
        mock_oauth_inst.cache_handler.get_cached_token.return_value = {"access_token": "token123"}
        mock_oauth_inst.validate_token.return_value = {"access_token": "token123"}
        mock_oauth.return_value = mock_oauth_inst

        with patch("spotipy.Spotify") as mock_spotify_cls:
            mock_sp = MagicMock()
            mock_spotify_cls.return_value = mock_sp
            mock_sp.playlist_items.return_value = {"items": [], "total": 0}

            # Add track
            res_add = self.client.post(
                "/api/v1/playlists/pl_123/tracks",
                json={"track_ids": ["4cOdK2wGLETKBW3PvgPWqT"]}
            )
            self.assertEqual(res_add.status_code, 200)
            mock_sp.playlist_add_items.assert_called_once()

            # Remove track
            res_del = self.client.delete(
                "/api/v1/playlists/pl_123/tracks",
                json={"track_ids": ["4cOdK2wGLETKBW3PvgPWqT"]}
            )
            self.assertEqual(res_del.status_code, 200)
            mock_sp.playlist_remove_all_occurrences_of_items.assert_called_once()


if __name__ == "__main__":
    unittest.main()
