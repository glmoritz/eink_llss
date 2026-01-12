"""
Tests for instance routes
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_instance():
    """Test instance creation endpoint."""
    response = client.post(
        "/instances",
        json={
            "name": "Test Dashboard",
            "type": "homeassistant",
        },
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
    assert response.status_code == 403


def test_notify_instance_authorized():
    """Test notify endpoint with auth."""
    response = client.post(
        "/instances/test_instance/notify",
        headers={"Authorization": "Bearer test_token"},
    )
    assert response.status_code == 202
