"""
test_bookings.py – BookingService
Place at the ROOT of the booking-service repo.
Run with: pytest test_bookings.py -v
"""
import pytest


# ── /health ───────────────────────────────────────────────────────────────────

def test_health(client):
    c, _, __ = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── POST /api/book ────────────────────────────────────────────────────────────

def test_create_booking_success(client):
    c, _, test_event = client
    r = c.post("/api/book", json={"event_id": test_event.id})
    assert r.status_code == 201
    data = r.json()
    assert data["event_id"] == test_event.id
    assert "id" in data
    assert "booking_date" in data


def test_create_booking_duplicate(client):
    c, _, test_event = client
    c.post("/api/book", json={"event_id": test_event.id})
    r = c.post("/api/book", json={"event_id": test_event.id})
    assert r.status_code == 409


def test_create_booking_event_not_found(client_event_missing):
    r = client_event_missing.post("/api/book", json={"event_id": 99999})
    assert r.status_code == 404


# ── GET /api/booking/{id} ─────────────────────────────────────────────────────

def test_get_booking_success(client):
    c, _, test_event = client
    created = c.post("/api/book", json={"event_id": test_event.id})
    booking_id = created.json()["id"]
    r = c.get(f"/api/booking/{booking_id}")
    assert r.status_code == 200
    assert r.json()["id"] == booking_id


def test_get_booking_not_found(client):
    c, _, __ = client
    r = c.get("/api/booking/99999")
    assert r.status_code == 404


# ── DELETE /api/booking/{id} ──────────────────────────────────────────────────

def test_delete_booking_success(client):
    c, _, test_event = client
    created = c.post("/api/book", json={"event_id": test_event.id})
    booking_id = created.json()["id"]
    r = c.delete(f"/api/booking/{booking_id}")
    assert r.status_code == 204
    # Confirm it's gone
    r2 = c.get(f"/api/booking/{booking_id}")
    assert r2.status_code == 404


def test_delete_booking_not_found(client):
    c, _, __ = client
    r = c.delete("/api/booking/99999")
    assert r.status_code == 404


# ── PATCH /api/booking/{id} ───────────────────────────────────────────────────

def test_update_booking_success(client, db):
    c, _, test_event = client
    from datetime import datetime
    import models

    # Create a second event to update to
    event2 = models.Event(
        id=99, event_date=datetime(2025, 12, 1, 10, 0),
        place="Second Venue", description="Another event",
    )
    db.add(event2)
    db.commit()

    created = c.post("/api/book", json={"event_id": test_event.id})
    booking_id = created.json()["id"]
    r = c.patch(f"/api/booking/{booking_id}", json={"event_id": 99})
    assert r.status_code == 200
    assert r.json()["event_id"] == 99


def test_update_booking_not_found(client):
    c, _, __ = client
    r = c.patch("/api/booking/99999", json={"event_id": 1})
    assert r.status_code == 404


# ── GET /api/schedules ────────────────────────────────────────────────────────

def test_get_schedules_empty(client):
    c, _, __ = client
    r = c.get("/api/schedules")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_schedules_with_booking(client):
    c, _, test_event = client
    c.post("/api/book", json={"event_id": test_event.id})
    r = c.get("/api/schedules")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert "event_date" in items[0]
    assert "place" in items[0]
    assert "booking_id" in items[0]
