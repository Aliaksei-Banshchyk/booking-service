"""
Tests for BookingService – bookings.py
Business logic covered:
  - create booking: success, duplicate → 409, event not found → 404
  - get booking: found, not found, belongs to current user only
  - delete booking: success, not found, other user can't delete
  - update booking: change event_id, event not found → 404, booking not found → 404
  - schedules: empty list, with bookings, ordering by event_date
  - booking_date is automatically set on creation
"""
import models
from datetime import datetime


# ── create_booking ────────────────────────────────────────────────────────────

def test_create_booking_success(client):
    c, user, event = client
    resp = c.post("/api/book", json={"event_id": event.id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == user.id
    assert data["event_id"] == event.id
    assert "id" in data
    assert "booking_date" in data          # auto-set


def test_create_booking_date_is_set_automatically(client):
    c, _, event = client
    resp = c.post("/api/book", json={"event_id": event.id})
    booking_date = resp.json()["booking_date"]
    assert booking_date is not None
    assert len(booking_date) > 10          # is a real datetime string


def test_create_booking_duplicate_rejected(client):
    c, _, event = client
    c.post("/api/book", json={"event_id": event.id})
    resp = c.post("/api/book", json={"event_id": event.id})
    assert resp.status_code == 409


def test_create_booking_event_not_found(client_event_missing):
    resp = client_event_missing.post("/api/book", json={"event_id": 99999})
    assert resp.status_code == 404


# ── get_booking ───────────────────────────────────────────────────────────────

def test_get_booking_found(client):
    c, _, event = client
    booking_id = c.post("/api/book", json={"event_id": event.id}).json()["id"]
    resp = c.get(f"/api/booking/{booking_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == booking_id


def test_get_booking_not_found(client):
    c, _, _ = client
    resp = c.get("/api/booking/99999")
    assert resp.status_code == 404


def test_get_booking_belongs_to_current_user(client, db):
    """A booking created by user A is invisible to user B."""
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db
    from auth import get_current_user

    c, _, event = client
    booking_id = c.post("/api/book", json={"event_id": event.id}).json()["id"]

    user_b = models.User(login="userb", password="pw", name="User B")
    db.add(user_b)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user_b
    with patch("booking_message_broker.publish", return_value=None):
        with TestClient(app) as c_b:
            resp = c_b.get(f"/api/booking/{booking_id}")
    app.dependency_overrides.clear()

    assert resp.status_code == 404


# ── delete_booking ────────────────────────────────────────────────────────────

def test_delete_booking_success(client):
    c, _, event = client
    booking_id = c.post("/api/book", json={"event_id": event.id}).json()["id"]
    assert c.delete(f"/api/booking/{booking_id}").status_code == 204
    assert c.get(f"/api/booking/{booking_id}").status_code == 404


def test_delete_booking_not_found(client):
    c, _, _ = client
    assert c.delete("/api/booking/99999").status_code == 404


def test_delete_booking_removes_from_schedules(client):
    c, _, event = client
    booking_id = c.post("/api/book", json={"event_id": event.id}).json()["id"]
    c.delete(f"/api/booking/{booking_id}")
    ids = [s["booking_id"] for s in c.get("/api/schedules").json()]
    assert booking_id not in ids


# ── update_booking ────────────────────────────────────────────────────────────

def test_update_booking_event(client, db):
    c, _, event = client
    event2 = models.Event(event_date=datetime(2025, 10, 1, 12, 0), place="Venue 2", description=None)
    db.add(event2)
    db.commit()

    booking_id = c.post("/api/book", json={"event_id": event.id}).json()["id"]
    resp = c.patch(f"/api/booking/{booking_id}", json={"event_id": event2.id})
    assert resp.status_code == 200
    assert resp.json()["event_id"] == event2.id


def test_update_booking_not_found(client):
    c, _, _ = client
    resp = c.patch("/api/booking/99999", json={"event_id": 1})
    assert resp.status_code == 404


def test_update_booking_event_not_found(client_event_missing, db):
    """Updating to a non-existent event_id → 404."""
    resp = client_event_missing.patch("/api/booking/1", json={"event_id": 99999})
    assert resp.status_code == 404


# ── schedules ─────────────────────────────────────────────────────────────────

def test_schedules_empty(client):
    c, _, _ = client
    resp = c.get("/api/schedules")
    assert resp.status_code == 200
    assert resp.json() == []


def test_schedules_contains_booking_details(client):
    c, _, event = client
    c.post("/api/book", json={"event_id": event.id})
    items = c.get("/api/schedules").json()
    assert len(items) == 1
    assert items[0]["event_id"] == event.id
    assert items[0]["place"] == event.place
    assert "event_date" in items[0]
    assert "booking_date" in items[0]


def test_schedules_ordered_by_event_date(client, db):
    c, user, _ = client

    early = models.Event(event_date=datetime(2025, 3, 1, 10, 0), place="Early")
    late  = models.Event(event_date=datetime(2025, 11, 1, 10, 0), place="Late")
    db.add_all([early, late])
    db.commit()
    c.post("/api/book", json={"event_id": late.id})
    c.post("/api/book", json={"event_id": early.id})

    dates = [s["event_date"] for s in c.get("/api/schedules").json()]
    assert dates == sorted(dates)


# ── health ────────────────────────────────────────────────────────────────────

def test_health(client):
    c, _, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "BookingService"
