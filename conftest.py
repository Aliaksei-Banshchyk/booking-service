"""
conftest.py – BookingService
Place at the ROOT of the booking-service repo alongside bookings.py.

Extra: mocks utility.get so HTTP calls to EventService are never made.
Also mocks the message broker publish so Azure Service Bus is not needed.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

SQLITE_URL = "sqlite:///./test.db"

with patch.dict(os.environ, {
    "DB_USERNAME": "test", "DB_PASSWORD": "test",
    "DB_SERVER": "localhost", "DB_DATABASE": "test",
}):
    import database
    import models

database.engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
database.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=database.engine
)

for table in models.Base.metadata.tables.values():
    table.schema = None

import auth
from main import app
from database import get_db
from auth import get_current_user


# ── Mock HTTP response that looks like EventService returning 200 ─────────────
def _mock_event_found(*args, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _mock_event_not_found(*args, **kwargs):
    resp = MagicMock()
    resp.status_code = 404
    return resp


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    models.Base.metadata.create_all(bind=database.engine)
    yield
    models.Base.metadata.drop_all(bind=database.engine)
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture()
def db():
    connection = database.engine.connect()
    transaction = connection.begin()
    session = database.SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    # Seed test user and event so FK constraints pass
    test_user = models.User(
        id=1, login="testuser",
        password=auth.hash_password("password123"),
        name="Test User",
    )
    from datetime import datetime
    test_event = models.Event(
        id=1,
        event_date=datetime(2025, 9, 1, 10, 0),
        place="Test Venue",
        description="Test event",
    )
    db.add(test_user)
    db.add(test_event)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with patch("utility.get", side_effect=_mock_event_found), \
         patch("booking_message_broker.publish", return_value=None):
        with TestClient(app) as c:
            yield c, test_user, test_event

    app.dependency_overrides.clear()


@pytest.fixture()
def client_event_missing(db):
    """Client where EventService returns 404 for any event lookup."""
    from fastapi.testclient import TestClient

    test_user = models.User(
        id=2, login="testuser2",
        password=auth.hash_password("password123"),
        name="Test User 2",
    )
    db.add(test_user)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with patch("utility.get", side_effect=_mock_event_not_found), \
         patch("booking_message_broker.publish", return_value=None):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()
