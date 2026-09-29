import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app import models  # noqa: F401


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session():
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_create_list_read_and_update_ticket(client: TestClient) -> None:
    created = client.post(
        "/tickets",
        json={
            "name": "Taylor Kim",
            "email": "taylor@example.com",
            "subject": "VPN is disconnected",
            "category": "Network",
            "priority": "High",
            "description": "The VPN disconnects during calls.",
        },
    )

    assert created.status_code == 201
    ticket = created.json()
    assert ticket["id"] == "TK-1001"
    assert ticket["status"] == "Open"
    assert ticket["assignee"] is None
    assert ticket["createdAt"]

    filtered = client.get("/tickets", params={"status": "Open", "assignee": "unassigned", "search": "VPN"})
    assert [item["id"] for item in filtered.json()] == ["TK-1001"]
    assert client.get("/tickets/TK-1001").json()["subject"] == "VPN is disconnected"

    updated = client.patch(
        "/tickets/TK-1001",
        json={"status": "Resolved", "assignee": "Riley Morgan"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "Resolved"
    assert updated.json()["assignee"] == "Riley Morgan"
    assert updated.json()["resolvedAt"]

    reopened = client.patch("/tickets/TK-1001", json={"status": "In progress"})
    assert reopened.json()["resolvedAt"] is None


def test_rejects_invalid_ticket_fields_and_empty_updates(client: TestClient) -> None:
    invalid_ticket = client.post(
        "/tickets",
        json={
            "name": "Taylor Kim",
            "email": "taylor@example.com",
            "subject": "Bad priority",
            "category": "Network",
            "priority": "Urgent",
            "description": "Invalid priority should fail validation.",
        },
    )
    assert invalid_ticket.status_code == 422
    assert client.patch("/tickets/TK-1001", json={}).status_code == 422
    assert client.patch("/tickets/TK-1001", json={"status": None}).status_code == 422
    assert client.get("/tickets/not-a-ticket").status_code == 404