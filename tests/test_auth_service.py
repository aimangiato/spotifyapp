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
