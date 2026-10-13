"""
SQLAlchemy models.

IMPORTANT — reconcile with Xuanhua before merging:
The `Student` model below is a MINIMAL STUB just big enough for the
company-side code (job applicants, event registrants, student search) to
run and be testable on its own. Xuanhua owns the real student-side schema
(signup fields, education, experience, preferences, etc.) per the task
split. When merging repos, replace this stub with her actual model and
re-point the foreign keys / re-run migrations — do not keep both.

Everything else here (Company, Job, Event, EventRegistration, Application)
is the company-side schema and is the "source of truth" for those tables.
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey, Enum, Boolean
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class JobCategory(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    on_campus = "on_campus"
    internship = "internship"


class ApplicationStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    declined = "declined"


# ---------------------------------------------------------------------------
# STUB — replace with Xuanhua's real Student model on merge
# ---------------------------------------------------------------------------
class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    college_name = Column(String(255))
    major = Column(String(120))
    city = Column(String(120))
    state = Column(String(120))
    skills = Column(Text)  # comma-separated for the stub; real model may normalize this
    resume_path = Column(String(500))  # path to uploaded PDF resume
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("Application", back_populates="student")
    registrations = relationship("EventRegistration", back_populates="student")


# ---------------------------------------------------------------------------
# Company-side schema (owned here)
# ---------------------------------------------------------------------------
class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    location = Column(String(255))
    description = Column(Text)
    contact_info = Column(String(255))
    profile_picture = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="company", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="company", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    category = Column(Enum(JobCategory), nullable=False, index=True)
    city = Column(String(120), index=True)
    location = Column(String(255))
    salary = Column(Float)
    skills = Column(Text)  # comma-separated skill tags
    posting_date = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime)

    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    resume_path = Column(String(500))  # snapshot of resume used for this application
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.pending, index=True)
    applied_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="applications")
    student = relationship("Student", back_populates="applications")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    date = Column(DateTime, nullable=False, index=True)
    time = Column(String(50))
    location = Column(String(255))
    city = Column(String(120), index=True)
    eligibility = Column(String(255))  # e.g. "CS majors", "all majors"

    company = relationship("Company", back_populates="events")
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")


class EventRegistration(Base):
    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="registrations")
    student = relationship("Student", back_populates="registrations")


class SavedItem(Base):
    """Backs the save_job_or_event AI tool (a student 'saving' a job or event)."""
    __tablename__ = "saved_items"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    item_type = Column(String(20), nullable=False)  # "job" or "event"
    item_id = Column(Integer, nullable=False)
    saved_at = Column(DateTime, default=datetime.utcnow)
