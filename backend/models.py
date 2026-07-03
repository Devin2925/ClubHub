import os
from datetime import UTC, datetime
from sqlalchemy import Boolean, create_engine, Column, Integer, String, DateTime, Float, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'clubhub.db')}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String, unique=True, nullable=False)  # e.g. "saanich_156870"
    title = Column(String, nullable=False)
    sport_type = Column(String, nullable=False)  # normalized: hockey, pickleball, basketball, etc.
    offering_type = Column(String, nullable=False, default="drop-in")  # pickup, drop-in, class
    venue_name = Column(String, nullable=False)  # e.g. "G.R. Pearkes Recreation Centre"
    facility_name = Column(String)  # e.g. "GRP Fieldhouse - Court #4b"
    center_id = Column(Integer)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    price = Column(String)  # e.g. "$44.76"
    description = Column(Text)
    booking_url = Column(String)
    source = Column(String, default="saanich")  # system source, e.g., 'saanich', 'perfectmind'
    municipality = Column(String, nullable=False, default="Saanich") # e.g., 'Saanich', 'Victoria', 'Oak Bay'
    registration_required = Column(Boolean)
    age_group = Column(String, nullable=False, default="")
    skill_level = Column(String, nullable=False, default="")
    last_fetched = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "title": self.title,
            "sport_type": self.sport_type,
            "offering_type": self.offering_type,
            "venue_name": self.venue_name,
            "facility_name": self.facility_name,
            "center_id": self.center_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "price": self.price,
            "description": self.description,
            "booking_url": self.booking_url,
            "source": self.source,
            "municipality": self.municipality,
            "registration_required": self.registration_required,
            "age_group": self.age_group,
            "skill_level": self.skill_level,
            "last_fetched": self.last_fetched.isoformat() if self.last_fetched else None,
        }


class SourceSyncStatus(Base):
    __tablename__ = "source_sync_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_key = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    municipality = Column(String, nullable=False)
    status = Column(String, nullable=False, default="never_run")
    last_started_at = Column(DateTime)
    last_succeeded_at = Column(DateTime)
    last_failed_at = Column(DateTime)
    last_completed_at = Column(DateTime)
    last_error = Column(Text)
    last_event_count = Column(Integer, nullable=False, default=0)
    previous_event_count = Column(Integer, nullable=False, default=0)
    last_event_delta = Column(Integer, nullable=False, default=0)
    last_duration_ms = Column(Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "source_key": self.source_key,
            "display_name": self.display_name,
            "municipality": self.municipality,
            "status": self.status,
            "last_started_at": self.last_started_at.isoformat() if self.last_started_at else None,
            "last_succeeded_at": self.last_succeeded_at.isoformat() if self.last_succeeded_at else None,
            "last_failed_at": self.last_failed_at.isoformat() if self.last_failed_at else None,
            "last_completed_at": self.last_completed_at.isoformat() if self.last_completed_at else None,
            "last_error": self.last_error,
            "last_event_count": self.last_event_count,
            "previous_event_count": self.previous_event_count,
            "last_event_delta": self.last_event_delta,
            "last_duration_ms": self.last_duration_ms,
        }


class VenueSyncStatus(Base):
    __tablename__ = "venue_sync_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venue_key = Column(String, unique=True, nullable=False)
    municipality = Column(String, nullable=False)
    venue_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="never_run")
    last_succeeded_at = Column(DateTime)
    previous_event_count = Column(Integer, nullable=False, default=0)
    last_event_count = Column(Integer, nullable=False, default=0)
    last_event_delta = Column(Integer, nullable=False, default=0)
    last_error = Column(Text)

    def to_dict(self):
        return {
            "venue_key": self.venue_key,
            "municipality": self.municipality,
            "venue_name": self.venue_name,
            "status": self.status,
            "last_succeeded_at": self.last_succeeded_at.isoformat() if self.last_succeeded_at else None,
            "previous_event_count": self.previous_event_count,
            "last_event_count": self.last_event_count,
            "last_event_delta": self.last_event_delta,
            "last_error": self.last_error,
        }


def init_db():
    Base.metadata.create_all(engine)
    ensure_columns()


def ensure_columns():
    with engine.begin() as conn:
        event_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(events)"))
        }
        if "offering_type" not in event_columns:
            conn.execute(
                text(
                    "ALTER TABLE events "
                    "ADD COLUMN offering_type VARCHAR NOT NULL DEFAULT 'drop-in'"
                )
            )
        if "registration_required" not in event_columns:
            conn.execute(
                text(
                    "ALTER TABLE events "
                    "ADD COLUMN registration_required BOOLEAN"
                )
            )
        if "age_group" not in event_columns:
            conn.execute(
                text(
                    "ALTER TABLE events "
                    "ADD COLUMN age_group VARCHAR NOT NULL DEFAULT ''"
                )
            )
        if "skill_level" not in event_columns:
            conn.execute(
                text(
                    "ALTER TABLE events "
                    "ADD COLUMN skill_level VARCHAR NOT NULL DEFAULT ''"
                )
            )

        source_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(source_sync_status)"))
        }
        if "previous_event_count" not in source_columns:
            conn.execute(
                text(
                    "ALTER TABLE source_sync_status "
                    "ADD COLUMN previous_event_count INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "last_event_delta" not in source_columns:
            conn.execute(
                text(
                    "ALTER TABLE source_sync_status "
                    "ADD COLUMN last_event_delta INTEGER NOT NULL DEFAULT 0"
                )
            )

        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        if "venue_sync_status" not in tables:
            VenueSyncStatus.__table__.create(bind=conn)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
