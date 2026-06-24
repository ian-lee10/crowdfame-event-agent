import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./events.db")
API_KEY = os.environ.get("API_KEY", "")

engine = create_engine(DATABASE_URL)
bearer_scheme = HTTPBearer()

app = FastAPI(title="Events API")


class Event(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str
    date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    poster_image_url: Optional[str] = None
    creator_name: Optional[str] = None
    instagram_handle: Optional[str] = None
    country: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class EventIn(BaseModel):
    title: str
    date: str
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None
    sourceUrl: Optional[str] = None
    posterImageUrl: Optional[str] = None
    creatorName: Optional[str] = None
    instagramHandle: Optional[str] = None
    country: Optional[str] = None


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


def require_api_key(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)):
    if not API_KEY or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


@app.post("/events", status_code=201)
def create_events(events: list[EventIn], _: str = Depends(require_api_key)):
    created = []
    skipped = 0
    with Session(engine) as session:
        for e in events:
            if e.sourceUrl:
                existing = session.exec(
                    select(Event).where(Event.source_url == e.sourceUrl)
                ).first()
                if existing:
                    skipped += 1
                    continue
            row = Event(
                title=e.title,
                date=e.date,
                start_time=e.startTime,
                end_time=e.endTime,
                timezone=e.timezone,
                location=e.location,
                city=e.city,
                state=e.state,
                description=e.description,
                source_url=e.sourceUrl,
                poster_image_url=e.posterImageUrl,
                creator_name=e.creatorName,
                instagram_handle=e.instagramHandle,
                country=e.country,
            )
            session.add(row)
            created.append(row.id)
        session.commit()
    return {"created": len(created), "skipped": skipped, "ids": created}


@app.get("/events")
def list_events(limit: int = 50, offset: int = 0, _: str = Depends(require_api_key)):
    with Session(engine) as session:
        rows = session.exec(select(Event).offset(offset).limit(limit)).all()
    return rows


@app.get("/health")
def health():
    return {"status": "ok"}
