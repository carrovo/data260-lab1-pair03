from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .application_status import ApplicationStatus
from .database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    college_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    major: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="student"
    )
    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="student"
    )
    preferences: Mapped["StudentPreferences | None"] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    saved_items: Mapped[list["SavedItem"]] = relationship(
        back_populates="student"
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    profile_picture_storage_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")
    events: Mapped[list["Event"]] = relationship(back_populates="company")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_remote: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    salary: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    company: Mapped["Company"] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="job"
    )
    saved_items: Mapped[list["SavedItem"]] = relationship(
        back_populates="job"
    )


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "job_id",
            name="uq_application_student_job",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str] = mapped_column(
        String(50),
        default=ApplicationStatus.PENDING.value,
        server_default=ApplicationStatus.PENDING.value,
    )
    # These columns remain nullable so databases with pre-upload application
    # rows can be migrated without deleting or fabricating resume data.
    resume_storage_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    resume_original_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    resume_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    student: Mapped["Student"] = relationship(
        back_populates="applications"
    )
    job: Mapped["Job"] = relationship(
        back_populates="applications"
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    major: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eligibility: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    company: Mapped["Company | None"] = relationship(
        back_populates="events"
    )
    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="event"
    )
    saved_items: Mapped[list["SavedItem"]] = relationship(
        back_populates="event"
    )


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "event_id",
            name="uq_registration_student_event",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    student: Mapped["Student"] = relationship(
        back_populates="registrations"
    )
    event: Mapped["Event"] = relationship(
        back_populates="registrations"
    )


class StudentPreferences(Base):
    __tablename__ = "student_preferences"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        primary_key=True,
    )
    job_preferences: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    event_preferences: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    student: Mapped["Student"] = relationship(
        back_populates="preferences"
    )


class SavedItem(Base):
    __tablename__ = "saved_items"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('job', 'event')",
            name="ck_saved_item_type",
        ),
        CheckConstraint(
            "(item_type = 'job' AND job_id IS NOT NULL "
            "AND event_id IS NULL) OR "
            "(item_type = 'event' AND event_id IS NOT NULL "
            "AND job_id IS NULL)",
            name="ck_saved_item_target_matches_type",
        ),
        UniqueConstraint(
            "student_id",
            "job_id",
            name="uq_saved_item_student_job",
        ),
        UniqueConstraint(
            "student_id",
            "event_id",
            name="uq_saved_item_student_event",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id"),
        nullable=True,
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id"),
        nullable=True,
    )
    item_type: Mapped[str] = mapped_column(String(20))
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    student: Mapped["Student"] = relationship(back_populates="saved_items")
    job: Mapped["Job | None"] = relationship(back_populates="saved_items")
    event: Mapped["Event | None"] = relationship(
        back_populates="saved_items"
    )
