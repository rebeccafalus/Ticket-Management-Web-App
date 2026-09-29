from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_predicts_ticket_category_with_confidence() -> None:
    response = client.post(
        "/predict",
        json={
            "subject": "VPN keeps disconnecting",
            "description": "I cannot stay connected to the office network from home.",
        },
    )

    assert response.status_code == 200
    assert response.json()["category"] == "Network"
    assert 0 <= response.json()["confidence"] <= 1


def test_analysis_reports_holdout_metrics_and_support() -> None:
    response = client.get("/analysis")

    assert response.status_code == 200
    analysis = response.json()
    assert analysis["trainingExamples"] == 40
    assert analysis["holdout"]["examples"] == 10
    assert len(analysis["holdout"]["confusionMatrix"]) == 5
    assert set(analysis["holdout"]["perCategory"]) == {
        "Account access", "Hardware", "Software", "Network", "Other"
    }


def test_evaluate_accepts_labeled_examples() -> None:
    response = client.post(
        "/evaluate",
        json={
            "examples": [
                {
                    "subject": "Password reset",
                    "description": "I am locked out of my user account.",
                    "category": "Account access",
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["examples"] == 1
    assert response.json()["accuracy"] == 1