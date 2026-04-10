import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'clubhub.db')}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String, unique=True, nullable=False)  # e.g. "saanich_156870"
    title = Column(String, nullable=False)
    sport_type = Column(String, nullable=False)  # normalized: hockey, pickleball, basketball, etc.
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
    last_fetched = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "title": self.title,
            "sport_type": self.sport_type,
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
            "last_fetched": self.last_fetched.isoformat() if self.last_fetched else None,
        }


def init_db():
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
