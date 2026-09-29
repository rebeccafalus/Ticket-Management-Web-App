from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import make_pipeline

TicketCategory = Literal["Account access", "Hardware", "Software", "Network", "Other"]
CATEGORIES = ["Account access", "Hardware", "Software", "Network", "Other"]

TRAINING_EXAMPLES = [
    ("Account access", "I forgot my password and cannot sign in to my account."),
    ("Account access", "Please unlock my account after too many login attempts."),
    ("Account access", "I need permission to access the finance shared drive."),
    ("Account access", "My multi-factor authentication code is not working."),
    ("Account access", "A new employee needs an email and network account."),
    ("Account access", "Please add me to the payroll application user group."),
    ("Account access", "I am locked out of my work account."),
    ("Account access", "Request access to the project folder and files."),
    ("Hardware", "My laptop will not power on even when plugged in."),
    ("Hardware", "The monitor has a cracked screen and needs replacement."),
    ("Hardware", "Several keys on my keyboard stopped working."),
    ("Hardware", "My docking station does not recognize the external display."),
    ("Hardware", "The printer is jammed and shows a paper feed error."),
    ("Hardware", "The laptop fan is loud and the computer is overheating."),
    ("Hardware", "I need a replacement mouse for my workstation."),
    ("Hardware", "The headset microphone has stopped working."),
    ("Software", "The spreadsheet application crashes when I open a file."),
    ("Software", "Please install the approved design software on my computer."),
    ("Software", "I need a license for the PDF editing application."),
    ("Software", "The latest application update fails to install."),
    ("Software", "My browser extension is causing an error on every page."),
    ("Software", "The desktop client freezes during startup."),
    ("Software", "Please update the video conferencing software."),
    ("Software", "A program reports a missing library after installation."),
    ("Network", "The VPN disconnects every few minutes while I am on calls."),
    ("Network", "I cannot connect to the office wireless network."),
    ("Network", "Websites are not loading on the wired office connection."),
    ("Network", "The internal DNS name does not resolve from my laptop."),
    ("Network", "Our team has lost access to the shared network drive."),
    ("Network", "The connection is very slow in the conference room."),
    ("Network", "Please check the firewall blocking our service connection."),
    ("Network", "Remote access fails even though my password is correct."),
    ("Other", "Where can I find the current IT support hours?"),
    ("Other", "I have a general question about the equipment return process."),
    ("Other", "Please advise who should approve this request."),
    ("Other", "I would like information about available support services."),
    ("Other", "Can someone explain the technology onboarding process?"),
    ("Other", "This request does not fit any of the listed service categories."),
    ("Other", "I need help identifying the right team for my question."),
    ("Other", "Please provide an update on the office technology policy."),
]

EVALUATION_EXAMPLES = [
    ("Account access", "My account is locked and the password reset link does not work."),
    ("Account access", "Please grant me read access to the shared team folder."),
    ("Hardware", "The keyboard and mouse connected to my workstation are broken."),
    ("Hardware", "My laptop screen flickers and goes black."),
    ("Software", "The accounting application closes as soon as it starts."),
    ("Software", "I need the approved photo editing program installed."),
    ("Network", "Office WiFi drops whenever I join a video meeting."),
    ("Network", "I cannot establish a remote VPN connection from home."),
    ("Other", "Could you tell me the process for returning old equipment?"),
    ("Other", "Who can answer a general question about support services?"),
]

texts = [text for _, text in TRAINING_EXAMPLES]
labels = [label for label, _ in TRAINING_EXAMPLES]
classifier = make_pipeline(
    TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True),
    LogisticRegression(max_iter=1000, random_state=42),
)
classifier.fit(texts, labels)

app = FastAPI(title="Ticket Management ML Service")


class PredictionRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=3000)


class LabeledExample(PredictionRequest):
    category: TicketCategory


class EvaluationRequest(BaseModel):
    examples: list[LabeledExample] = Field(min_length=1, max_length=1000)


def evaluate(examples: list[tuple[str, str]]) -> dict[str, object]:
    expected = [category for category, _ in examples]
    predicted = classifier.predict([text for _, text in examples]).tolist()
    precision, recall, f1, support = precision_recall_fscore_support(
        expected, predicted, labels=CATEGORIES, zero_division=0
    )
    return {
        "accuracy": round(float(accuracy_score(expected, predicted)), 4),
        "examples": len(examples),
        "perCategory": {
            category: {
                "precision": round(float(precision[index]), 4),
                "recall": round(float(recall[index]), 4),
                "f1": round(float(f1[index]), 4),
                "support": int(support[index]),
            }
            for index, category in enumerate(CATEGORIES)
        },
        "confusionMatrix": confusion_matrix(expected, predicted, labels=CATEGORIES).tolist(),
        "categoryOrder": CATEGORIES,
    }


@app.post("/predict")
def predict(payload: PredictionRequest) -> dict[str, str | float]:
    text = f"{payload.subject.strip()}\n{payload.description.strip()}"
    probabilities = classifier.predict_proba([text])[0]
    best_index = int(probabilities.argmax())
    return {
        "category": str(classifier.classes_[best_index]),
        "confidence": round(float(probabilities[best_index]), 4),
    }


@app.get("/analysis")
def analysis() -> dict[str, object]:
    return {
        "model": "tfidf-logistic-regression-v1",
        "trainingExamples": len(TRAINING_EXAMPLES),
        "trainingExamplesByCategory": {
            category: sum(label == category for label, _ in TRAINING_EXAMPLES)
            for category in CATEGORIES
        },
        "holdout": evaluate(EVALUATION_EXAMPLES),
    }


@app.post("/evaluate")
def evaluate_labeled(payload: EvaluationRequest) -> dict[str, object]:
    examples = [
        (item.category, f"{item.subject.strip()}\n{item.description.strip()}")
        for item in payload.examples
    ]
    return evaluate(examples)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}