import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app import main as api_main
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


def test_prediction_persists_and_technician_correction_is_evaluated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        api_main,
        "predict_category",
        lambda subject, description: {"category": "Network", "confidence": 0.91},
    )
    created = client.post(
        "/tickets",
        json={
            "name": "Taylor Kim",
            "email": "taylor@example.com",
            "subject": "VPN drops",
            "description": "I lose my network connection during calls.",
        },
    )

    assert created.status_code == 201
    ticket = created.json()
    assert ticket["category"] == "Network"
    assert ticket["predictedCategory"] == "Network"
    assert ticket["predictionConfidence"] == 0.91
    assert ticket["categoryCorrectedAt"] is None

    corrected = client.patch("/tickets/TK-1001", json={"category": "Hardware"})
    assert corrected.status_code == 200
    assert corrected.json()["category"] == "Hardware"
    assert corrected.json()["predictedCategory"] == "Network"
    assert corrected.json()["categoryCorrectedAt"]

    analytics = client.get("/analytics").json()
    assert analytics["categoryCorrections"] == 1
    assert analytics["reviewedPredictions"] == 1
    assert analytics["predictionAccuracy"] == 0
    assert analytics["categoryCounts"]["Hardware"] == 1

    monkeypatch.setattr(
        api_main,
        "predict_category",
        lambda subject, description: {"category": "Software", "confidence": 0.82},
    )
    second = client.post(
        "/tickets",
        json={
            "name": "Taylor Kim",
            "email": "taylor@example.com",
            "subject": "App crash",
            "description": "The desktop software closes at startup.",
        },
    ).json()
    confirmed = client.patch(f"/tickets/{second['id']}", json={"category": "Software"})
    assert confirmed.json()["categoryReviewedAt"]
    assert confirmed.json()["categoryCorrectedAt"] is None
    updated_analytics = client.get("/analytics").json()
    assert updated_analytics["categoryCorrections"] == 1
    assert updated_analytics["reviewedPredictions"] == 2
    assert updated_analytics["predictionAccuracy"] == 0.5


def test_ticket_creation_falls_back_when_prediction_is_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_main, "predict_category", lambda subject, description: None)
    created = client.post(
        "/tickets",
        json={
            "name": "Taylor Kim",
            "email": "taylor@example.com",
            "subject": "Uncategorized request",
            "description": "The classifier service is unavailable.",
        },
    )

    assert created.status_code == 201
    assert created.json()["category"] == "Other"
    assert created.json()["predictedCategory"] is None
    assert created.json()["predictionConfidence"] is None