import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models
import schemas
import booking_message_broker as message_broker
import utility

router = APIRouter(prefix="/api", tags=["BookingService"])


@router.post("/book", response_model=schemas.BookingResponse, status_code=201)
def create_booking(payload: schemas.BookingCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Check event exists via EventService HTTP call
    resp = utility.get(f"{utility.EVENT_SERVICE_URL}/api/event/{payload.event_id}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Event not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="EventService unavailable")

    existing = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.event_id == payload.event_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already booked this event")

    booking = models.Booking(user_id=current_user.id, event_id=payload.event_id)
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Trigger: send message to Service Bus
    message_broker.publish(
        user_id=current_user.id,
        booking_id=booking.id,
        message=f"Booking created for event {payload.event_id}",
    )
    return booking


@router.get("/booking/{booking_id}", response_model=schemas.BookingResponse)
def get_booking(booking_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    booking = db.query(models.Booking).filter(
        models.Booking.id == booking_id,
        models.Booking.user_id == current_user.id,
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.delete("/booking/{booking_id}", status_code=204)
def delete_booking(booking_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    booking = db.query(models.Booking).filter(
        models.Booking.id == booking_id,
        models.Booking.user_id == current_user.id,
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    db.delete(booking)
    db.commit()


@router.patch("/booking/{booking_id}", response_model=schemas.BookingResponse)
def update_booking(booking_id: int, payload: schemas.BookingUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    booking = db.query(models.Booking).filter(
        models.Booking.id == booking_id,
        models.Booking.user_id == current_user.id,
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if payload.event_id is not None:
        resp = utility.get(f"{utility.EVENT_SERVICE_URL}/api/event/{payload.event_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Event not found")
        booking.event_id = payload.event_id
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/schedules", response_model=List[schemas.ScheduleItem])
def get_schedules(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.Booking, models.Event)
        .join(models.Event, models.Booking.event_id == models.Event.id)
        .filter(models.Booking.user_id == current_user.id)
        .order_by(models.Event.event_date)
        .all()
    )
    return [
        schemas.ScheduleItem(
            booking_id=b.id, event_id=e.id, event_date=e.event_date,
            place=e.place, description=e.description, booking_date=b.booking_date,
        )
        for b, e in rows
    ]
