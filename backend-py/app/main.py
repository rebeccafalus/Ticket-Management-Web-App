import re
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Ticket
from app.schemas import TicketCreate, TicketRead, TicketStatus, TicketUpdate

app = FastAPI(title="Ticket Management API")
TICKET_ID_PATTERN = re.compile(r"^TK-(\d+)$")
TICKET_CATEGORIES = {"Account access", "Hardware", "Software", "Network", "Other"}


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
    ticket = Ticket(**payload.model_dump() | {"category": payload.category or "Other"})
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
    category_counts = dict(
        session.execute(select(Ticket.category, func.count()).group_by(Ticket.category)).all()
    )
    return {"categoryCounts": category_counts}


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
    if "status" in updates:
        ticket.resolved_at = (
            ticket.resolved_at or datetime.now(timezone.utc)
            if ticket.status == "Resolved"
            else None
        )
    session.commit()
    session.refresh(ticket)
    return ticket