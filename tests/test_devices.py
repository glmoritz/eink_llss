"""
Tests for device routes
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register_device():
    """Test device registration endpoint."""
    response = client.post(
        "/devices/register",
        json={
            "hardware_id": "esp32_001",
            "firmware_version": "1.0.0",
            "display": {
                "width": 800,
                "height": 480,
                "bit_depth": 4,
                "partial_refresh": True,
            },
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "device_id" in data
    assert "device_secret" in data
    assert "access_token" in data


def test_get_device_state_unauthorized():
    """Test that device state endpoint requires authentication."""
    response = client.get("/devices/test_device/state")
    assert response.status_code == 403


def test_get_device_state_authorized():
    """Test device state endpoint with auth."""
    response = client.get(
        "/devices/test_device/state",
        headers={"Authorization": "Bearer test_token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "action" in data
    assert data["action"] in ["NOOP", "FETCH_FRAME", "SLEEP"]
