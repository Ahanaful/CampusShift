"""Persistence and overlap rules independent of HTTP routing."""

from fastapi import HTTPException
from sqlalchemy import select, text

from app.models import Availability, ClassSchedule


def list_windows(db, model, student_id):
    return list(db.scalars(select(model).where(model.student_id == student_id)
                           .order_by(model.day_of_week, model.start_time, model.id)))


def owned_window(db, model, student_id, window_id):
    entry = db.scalar(select(model).where(model.id == window_id, model.student_id == student_id))
    if not entry:
        raise HTTPException(404, "Entry not found.")
    return entry


def save_window(db, model, student_id, data, window_id=None):
    # Reserve SQLite's write lock before the overlap read so simultaneous saves
    # cannot both pass validation and insert conflicting windows.
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    entry = owned_window(db, model, student_id, window_id) if window_id else None
    query = select(model.id).where(model.student_id == student_id,
        model.day_of_week == data.day_of_week, model.start_time < data.end_time,
        model.end_time > data.start_time)
    if entry:
        query = query.where(model.id != entry.id)
    if db.scalar(query) is not None:
        raise HTTPException(409, "This time overlaps an existing entry on the same day.")
    if entry is None:
        entry = model(student_id=student_id)
        db.add(entry)
    for key, value in data.model_dump().items():
        setattr(entry, key, value)
    db.commit()
    return entry


def delete_window(db, model, student_id, window_id):
    db.delete(owned_window(db, model, student_id, window_id))
    db.commit()


def conflicts(db, student_id):
    classes = list_windows(db, ClassSchedule, student_id)
    availability = list_windows(db, Availability, student_id)
    return [{"class_id": c.id, "availability_id": a.id, "course_name": c.course_name,
             "day_of_week": c.day_of_week, "start_time": max(c.start_time, a.start_time),
             "end_time": min(c.end_time, a.end_time)}
            for c in classes for a in availability
            if c.day_of_week == a.day_of_week and c.start_time < a.end_time and a.start_time < c.end_time]
