import json
import os
import re
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Ticket
from app.schemas import TicketCreate, TicketRead, TicketStatus, TicketUpdate

app = FastAPI(title="Ticket Management API")
TICKET_ID_PATTERN = re.compile(r"^TK-(\d+)$")
TICKET_CATEGORIES = {"Account access", "Hardware", "Software", "Network", "Other"}
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml:8001").rstrip("/")


def predict_category(subject: str, description: str) -> dict[str, str | float] | None:
    request = Request(
        f"{ML_SERVICE_URL}/predict",
        data=json.dumps({"subject": subject, "description": description}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read())
        category = result.get("category")
        confidence = float(result.get("confidence"))
        if category not in TICKET_CATEGORIES or not 0 <= confidence <= 1:
            return None
        return {"category": category, "confidence": confidence}
    except (OSError, TimeoutError, URLError, ValueError, TypeError):
        return None


def find_ticket(session: Session, ticket_id: str) -> Ticket:
    match = TICKET_ID_PATTERN.fullmatch(ticket_id)
    if not match:
        raise HTTPException(status_code=404, detail="Ticket not found")
    database_id = int(match.group(1)) - 1000
    ticket = session.get(Ticket, database_id) if database_id > 0 else None
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tickets", response_model=TicketRead, status_code=201)
def create_ticket(payload: TicketCreate, session: Session = Depends(get_session)) -> Ticket:
    prediction = predict_category(payload.subject, payload.description)
    values = payload.model_dump(exclude={"category"})
    ticket = Ticket(
        **values,
        category=prediction["category"] if prediction else payload.category or "Other",
        predicted_category=prediction["category"] if prediction else None,
        prediction_confidence=prediction["confidence"] if prediction else None,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@app.get("/tickets", response_model=list[TicketRead])
def list_tickets(
    status: TicketStatus | None = None,
    assignee: str | None = None,
    search: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[Ticket]:
    statement = select(Ticket)
    if status is not None:
        statement = statement.where(Ticket.status == status)
    if assignee is not None:
        statement = statement.where(
            Ticket.assignee.is_(None) if assignee == "unassigned" else Ticket.assignee == assignee
        )
    if search:
        search_term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Ticket.subject.ilike(search_term),
                Ticket.name.ilike(search_term),
                Ticket.email.ilike(search_term),
                Ticket.category.ilike(search_term),
            )
        )
    statement = statement.order_by(Ticket.created_at.desc(), Ticket.id.desc())
    statement = statement.offset(offset).limit(limit)
    return list(session.scalars(statement).all())


@app.get("/analytics")
def ticket_analytics(session: Session = Depends(get_session)) -> dict[str, object]:
    total = session.scalar(select(func.count()).select_from(Ticket)) or 0
    predicted = session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.predicted_category.is_not(None))
    ) or 0
    correction_rows = session.execute(
        select(Ticket.predicted_category, Ticket.category).where(
            Ticket.category_reviewed_at.is_not(None), Ticket.predicted_category.is_not(None)
        )
    ).all()
    correction_count = session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.category_corrected_at.is_not(None))
    ) or 0
    category_counts = dict(
        session.execute(select(Ticket.category, func.count()).group_by(Ticket.category)).all()
    )
    correct = sum(predicted_category == category for predicted_category, category in correction_rows)
    return {
        "totalTickets": total,
        "predictedTickets": predicted,
        "categoryCorrections": correction_count,
        "reviewedPredictions": len(correction_rows),
        "predictionAccuracy": round(correct / len(correction_rows), 4) if correction_rows else None,
        "categoryCounts": category_counts,
    }


@app.get("/tickets/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: str, session: Session = Depends(get_session)) -> Ticket:
    return find_ticket(session, ticket_id)


@app.patch("/tickets/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    session: Session = Depends(get_session),
) -> Ticket:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="At least one field must be updated")

    ticket = find_ticket(session, ticket_id)
    for field, value in updates.items():
        setattr(ticket, field, value)
    if "category" in updates:
        now = datetime.now(timezone.utc)
        ticket.category_reviewed_at = now
        ticket.category_corrected_at = (
            now
            if ticket.predicted_category is not None and ticket.category != ticket.predicted_category
            else None
        )
    if "status" in updates:
        ticket.resolved_at = (
            ticket.resolved_at or datetime.now(timezone.utc)
            if ticket.status == "Resolved"
            else None
        )
    session.commit()
    session.refresh(ticket)
    return ticket