"""
Tests for device routes
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _device_registration_payload(hardware_id: str) -> dict:
    return {
        "hardware_id": hardware_id,
        "firmware_version": "1.0.0",
        "display": {
            "width": 800,
            "height": 480,
            "bit_depth": 4,
            "partial_refresh": True,
        },
    }


def test_register_device():
    """Test device registration endpoint."""
    response = client.post(
        "/devices/register",
        json=_device_registration_payload("esp32_001"),
    )
    assert response.status_code == 201
    data = response.json()
    assert "device_id" in data
    assert "device_secret" in data
    assert "access_token" in data


def test_admin_can_delete_device_and_reregister_same_hardware_id():
    """Deleting a device from admin should allow a fresh registration."""
    hardware_id = "esp32_delete_and_reregister"
    register_response = client.post(
        "/api/auth/devices/register",
        json=_device_registration_payload(hardware_id),
    )
    assert register_response.status_code == 201
    device_id = register_response.json()["device_id"]

    delete_response = client.delete(f"/api/admin/devices/{device_id}")
    assert delete_response.status_code == 204

    reregister_response = client.post(
        "/api/auth/devices/register",
        json=_device_registration_payload(hardware_id),
    )
    assert reregister_response.status_code == 201
    assert reregister_response.json()["device_id"] != device_id


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
