"""
Tests for instance routes
"""

import pytest
from fastapi.testclient import TestClient

from app.auth import HLSS_SHARED_KEY, create_access_token
from app.main import app

client = TestClient(app)


def _admin_headers() -> dict:
    token = create_access_token(
        "llss_orchestrator",
        token_type="llss_admin",
        secret_key=HLSS_SHARED_KEY,
    )
    return {"Authorization": f"Bearer {token}"}


def test_create_instance():
    """Test instance creation endpoint."""
    response = client.post(
        "/instances",
        json={
            "name": "Test Dashboard",
            "type": "homeassistant",
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 201
    data = response.json()
    assert "instance_id" in data
    assert data["name"] == "Test Dashboard"
    assert data["type"] == "homeassistant"
    assert "created_at" in data


def test_notify_instance_unauthorized():
    """Test that notify endpoint requires authentication."""
    response = client.post("/instances/test_instance/notify")
    assert response.status_code == 401


def test_notify_instance_authorized():
    """Test notify endpoint with auth."""
    create_response = client.post(
        "/instances",
        json={
            "name": "Notify Dashboard",
            "type": "homeassistant",
        },
        headers=_admin_headers(),
    )
    assert create_response.status_code == 201
    instance_data = create_response.json()
    instance_id = instance_data["instance_id"]
    access_token = instance_data["access_token"]

    response = client.post(
        f"/instances/{instance_id}/notify",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 202
