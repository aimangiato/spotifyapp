# Piano 05: Quality Assurance & Test dei Service Layer Critici

## 🎯 Obiettivo
Implementare una suite di test mirata e leggera con `pytest` per verificare e blindare i due service layer critici identificati:
1. **`AuthService`**: Gestione anti-CSRF dello state, refresh dei token e isolamento sessioni.
2. **`TrackService` & Chunking**: Estrazione null-safe dei metadati brani (copertine assenti, tracce nulle) e suddivisione dei batch $\le 100$.

> [!NOTE]
> In linea con quanto concordato nel `/grill-me`, la strategia di test si concentra sui componenti ad alto rischio di crash e di sicurezza (Unit Test dei Service Layer), evitando test di integrazione HTTP complessi o fragili.

---

## 📦 Dipendenze di Progetto (`requirements.txt`)

Il file `requirements.txt` target deve essere formalizzato come segue:

```text
Flask>=3.0.0
flask-cors>=4.0.0
spotipy>=2.23.0
python-dotenv>=1.0.0
marshmallow>=3.20.0
webargs>=8.3.0

# Testing & Dev dependencies
pytest>=7.4.0
pytest-mock>=3.11.0
```

---

## 🧪 Struttura della Cartella `tests/`

```
tests/
├── conftest.py               # Fixture condivise e mock del client Spotify
├── test_auth_service.py      # Test unitari per logica OAuth e State CSRF
└── test_track_service.py     # Test unitari per estrazione metadati e chunking
```

---

## 🛠️ Implementazione dei Test

### 1. Fixture Condivise (`tests/conftest.py`)

Crea un mock riutilizzabile del client `spotipy.Spotify` per evitare qualsiasi chiamata di rete reale:

```python
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
```

---

### 2. Test Unitari `TrackService` (`tests/test_track_service.py`)

Verifica che le anomalie dei dati non causino mai crash del backend e che l'algoritmo di chunking rispetti rigorosamente i limiti di Spotify:

```python
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
```

---

### 3. Test Unitari `AuthService` (`tests/test_auth_service.py`)

Verifica la protezione anti-CSRF dello state e la validazione dei token:

```python
import pytest
from backend.services.auth_service import AuthService

def test_generate_oauth_state():
    auth_service = AuthService()
    state1 = auth_service.generate_state()
    state2 = auth_service.generate_state()

    assert state1 != state2
    assert len(state1) >= 32

def test_verify_oauth_state_success():
    auth_service = AuthService()
    state = "valid_secure_state_string_12345"
    assert auth_service.validate_state(state, expected_state=state) is True

def test_verify_oauth_state_mismatch():
    auth_service = AuthService()
    assert auth_service.validate_state("tampered_state", expected_state="original_state") is False

def test_verify_oauth_state_missing():
    auth_service = AuthService()
    assert auth_service.validate_state(None, expected_state="original_state") is False
    assert auth_service.validate_state("state", expected_state=None) is False
```

---

## 🏃 Come Eseguire la Suite di Test

```bash
# Attivazione virtualenv
source venv/bin/activate

# Installazione dipendenze di test
pip install -r requirements.txt

# Esecuzione rapida di tutti i test unitari
pytest -v
```

### Criteri di Accettazione QA (Definition of Done)
1. **100% dei test passati** con zero warning di deprecazione critici.
2. Tempo totale di esecuzione dei test unitari $< 2\text{ secondi}$.
3. Nessuna richiesta verso l'esterno: `pytest` deve essere eseguibile anche in totale assenza di connessione Internet grazie ai mock.
