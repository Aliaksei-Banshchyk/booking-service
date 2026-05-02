"""
Tests for BookingService – bookings.py
Covers: create_booking, get_booking, delete_booking, update_booking, get_schedules
"""


def test_create_booking_success(client):
    c, user, event = client
    resp = c.post("/api/book", json={"event_id": event.id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == user.id
    assert data["event_id"] == event.id
    assert "id" in data
    assert "booking_date" in data


def test_create_booking_duplicate(client):
    c, _, event = client
    c.post("/api/book", json={"event_id": event.id})
    resp = c.post("/api/book", json={"event_id": event.id})
    assert resp.status_code == 409


def test_create_booking_event_not_found(client_event_missing):
    resp = client_event_missing.post("/api/book", json={"event_id": 999})
    assert resp.status_code == 404


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


def test_delete_booking(client):
    c, _, event = client
    booking_id = c.post("/api/book", json={"event_id": event.id}).json()["id"]
    resp = c.delete(f"/api/booking/{booking_id}")
    assert resp.status_code == 204
    assert c.get(f"/api/booking/{booking_id}").status_code == 404


def test_delete_booking_not_found(client):
    c, _, _ = client
    resp = c.delete("/api/booking/99999")
    assert resp.status_code == 404


def test_update_booking_success(client, db):
    import models
    from datetime import datetime

    c, user, event = client

    # Create a second event directly in DB (utility.get is already mocked to 200)
    event2 = models.Event(id=2, event_date=datetime(2025, 10, 1, 12, 0), place="Venue 2", description=None)
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


def test_get_schedules_empty(client):
    c, _, _ = client
    resp = c.get("/api/schedules")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_schedules_with_booking(client):
    c, _, event = client
    c.post("/api/book", json={"event_id": event.id})
    resp = c.get("/api/schedules")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["event_id"] == event.id
    assert "event_date" in items[0]
    assert "place" in items[0]


def test_health(client):
    c, _, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "BookingService"
