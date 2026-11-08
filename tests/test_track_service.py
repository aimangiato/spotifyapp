import pytest
from backend.services.track_service import TrackService
from backend.services.playlist_service import chunk_list


def test_extract_track_data_standard(mock_spotify, sample_track_full):
    service = TrackService(mock_spotify)
    result = service.extract_track_data(sample_track_full)

    assert result is not None
    assert result["id"] == "4cOdK2wGLETKBW3PvgPWqT"
    assert result["name"] == "Never Gonna Give You Up"
    assert result["artist"] == "Rick Astley"
    assert result["coverart"] == "https://i.scdn.co/image/test_cover.jpg"


def test_extract_track_data_no_images_does_not_crash(mock_spotify, sample_track_no_images):
    """Verifica che un album senza copertine non generi IndexError e restituisca None."""
    service = TrackService(mock_spotify)
    result = service.extract_track_data(sample_track_no_images)

    assert result is not None
    assert result["id"] == "1111111111111111111111"
    assert result["coverart"] is None


def test_extract_track_data_none_does_not_crash(mock_spotify, sample_track_none):
    """Verifica che un track nullo non generi TypeError e venga scartato in sicurezza."""
    service = TrackService(mock_spotify)
    result = service.extract_track_data(sample_track_none)

    assert result is None


def test_extract_multiple_artists(mock_spotify):
    service = TrackService(mock_spotify)
    item = {
        "track": {
            "id": "2222222222222222222222",
            "name": "Collab Song",
            "artists": [{"name": "Artist 1"}, {"name": "Artist 2"}],
            "album": {"images": []}
        }
    }
    result = service.extract_track_data(item)
    assert result["artist"] == "Artist 1, Artist 2"


@pytest.mark.parametrize("total_items,chunk_size,expected_batches", [
    (0, 100, 0),
    (50, 100, 1),
    (100, 100, 1),
    (101, 100, 2),
    (245, 100, 3)
])
def test_chunk_list(total_items, chunk_size, expected_batches):
    items = [f"id_{i}" for i in range(total_items)]
    batches = list(chunk_list(items, chunk_size=chunk_size))

    assert len(batches) == expected_batches
    if total_items > 0:
        assert sum(len(b) for b in batches) == total_items
        assert all(len(b) <= chunk_size for b in batches)
