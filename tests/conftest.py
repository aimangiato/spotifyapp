import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_spotify():
    """Mock completo del client spotipy.Spotify."""
    mock = MagicMock()
    mock.current_user.return_value = {
        "id": "test_user_123",
        "display_name": "Test User",
        "email": "test@example.com"
    }
    return mock


@pytest.fixture
def sample_track_full():
    return {
        "track": {
            "id": "4cOdK2wGLETKBW3PvgPWqT",
            "name": "Never Gonna Give You Up",
            "artists": [{"name": "Rick Astley"}],
            "album": {
                "name": "Whenever You Need Somebody",
                "images": [{"url": "https://i.scdn.co/image/test_cover.jpg", "height": 300, "width": 300}]
            },
            "duration_ms": 213573,
            "uri": "spotify:track:4cOdK2wGLETKBW3PvgPWqT"
        }
    }


@pytest.fixture
def sample_track_no_images():
    """Traccia senza immagini copertina (potenziale causa di IndexError)."""
    return {
        "track": {
            "id": "1111111111111111111111",
            "name": "Local Audio File",
            "artists": [{"name": "Local Artist"}],
            "album": {
                "name": "Local Album",
                "images": []  # Lista vuota!
            },
            "duration_ms": 120000,
            "uri": "spotify:track:1111111111111111111111"
        }
    }


@pytest.fixture
def sample_track_none():
    """Elemento con track nullo (es. episodio podcast o brano rimosso)."""
    return {
        "track": None
    }
