"""ClubHub Vancouver's own database, kept apart from Victoria's clubhub.db.

Same tables as models.py (Event, SourceSyncStatus, VenueSyncStatus), different file, so
nothing Vancouver scrapes can reach Victoria's snapshot export, alerts or audits.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VANCOUVER_DB_PATH = os.path.join(BASE_DIR, "clubhub_vancouver.db")

engine = create_engine(f"sqlite:///{VANCOUVER_DB_PATH}", echo=False)
VancouverSessionLocal = sessionmaker(bind=engine)


def init_vancouver_db():
    Base.metadata.create_all(engine)


class VancouverDBMixin:
    """Put before BaseScraper in a scraper's bases to save into clubhub_vancouver.db."""

    def open_db(self):
        return VancouverSessionLocal()


if __name__ == "__main__":
    init_vancouver_db()
    print(f"Vancouver database initialized at {VANCOUVER_DB_PATH}")
