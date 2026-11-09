from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import OperationalError

from workboard.database import get_session
from workboard.main import app


def test_crud_filter_and_timestamps(client):
    created = client.post("/api/v1/tasks", json={"title": " 学習 ", "description": "Compose"})
    assert created.status_code == 201
    task = created.json()
    UUID(task["id"])
    assert task["title"] == "学習"
    assert task["status"] == "TODO"
    assert datetime.fromisoformat(task["created_at"].replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    path = f"/api/v1/tasks/{task['id']}"
    assert client.get(path).json() == task
    updated = client.patch(path, json={"title": "更新", "status": "DONE", "description": None})
    assert updated.status_code == 200
    assert updated.json()["description"] is None
    assert updated.json()["created_at"] == task["created_at"]
    assert updated.json()["updated_at"] >= task["updated_at"]
    assert len(client.get("/api/v1/tasks?status=DONE").json()) == 1
    assert client.get("/api/v1/tasks?status=TODO").json() == []
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/tasks").json() == []


def test_partial_update_preserves_omitted_values(client):
    task = client.post("/api/v1/tasks", json={"title": "保持", "description": "説明"}).json()
    result = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "IN_PROGRESS"})
    assert result.status_code == 200
    assert result.json()["title"] == "保持"
    assert result.json()["description"] == "説明"


@pytest.mark.parametrize("body", [
    {}, {"title": ""}, {"title": "   "}, {"title": "a" * 121},
    {"title": "test", "description": "a" * 2001},
    {"title": "test", "status": "UNKNOWN"}, {"title": "test", "extra": True},
])
def test_invalid_creation(client, body):
    assert client.post("/api/v1/tasks", json=body).status_code == 422


@pytest.mark.parametrize("body", [{"title": None}, {"status": None}, {"title": ""}, {"status": "UNKNOWN"}])
def test_invalid_update(client, body):
    task = client.post("/api/v1/tasks", json={"title": "test"}).json()
    assert client.patch(f"/api/v1/tasks/{task['id']}", json=body).status_code == 422


def test_boundaries_and_missing_tasks(client):
    assert client.post("/api/v1/tasks", json={"title": "a" * 120, "description": "a" * 2000}).status_code == 201
    assert client.get("/api/v1/tasks?status=UNKNOWN").status_code == 422
    assert client.get("/api/v1/tasks/not-a-uuid").status_code == 422
    missing = f"/api/v1/tasks/{uuid4()}"
    assert client.get(missing).status_code == 404
    assert client.patch(missing, json={"title": "test"}).status_code == 404
    assert client.delete(missing).status_code == 404


def test_health_dependency_boundary(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200

    class UnavailableSession:
        def execute(self, statement):
            raise OperationalError("SELECT 1", {}, Exception("unavailable"))

    app.dependency_overrides[get_session] = lambda: UnavailableSession()
    assert client.get("/health/ready").status_code == 503
    assert client.get("/health/live").status_code == 200
