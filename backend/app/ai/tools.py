"""
The 5 required tools: JSON schemas + implementations.

Every tool function ALWAYS returns a string and NEVER raises — database or
lookup errors are caught and turned into a plain error string, per the lab
spec ("must return a string in all cases and never raise an exception").

Ownership note (for the report / AI_USE.md):
  - search_events, save_job_or_event: implemented here in full (Trapti).
  - search_jobs, get_job_details: implemented here against the Job model
    this half of the app owns, so the loop is testable standalone.
  - get_student_preferences: STUBBED. There is no dedicated preferences
    table yet — this reads city/major/skills off the Student stub as a
    placeholder. Replace with Xuanhua's real preferences implementation
    on merge; the signature and return contract below must not change.
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import Job, Event, Student, SavedItem

# ---------------------------------------------------------------------------
# JSON schemas (passed to the model as `tools`)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_student_preferences",
            "description": (
                "Return the current student's saved job and event preferences "
                "(e.g. preferred city, categories, skills). Call this FIRST "
                "whenever a request depends on 'my' preferences, such as "
                "finding something 'in my city'. Clearly states when no "
                "preferences are saved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {
                        "type": "integer",
                        "description": "ID of the student the assistant is acting for.",
                    }
                },
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_jobs",
            "description": (
                "Filter job postings by title, company, category, city, salary, "
                "skills, and/or deadline. Returns id, title, company, location, "
                "category, salary, and deadline for each match, or a plain "
                "no-match message if nothing fits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Partial or full job title to match."},
                    "category": {
                        "type": "string",
                        "enum": ["full_time", "part_time", "on_campus", "internship"],
                        "description": "Job category filter.",
                    },
                    "city": {"type": "string", "description": "City to filter by."},
                    "remote": {"type": "boolean", "description": "True to match remote-friendly postings only."},
                    "skills": {"type": "string", "description": "Comma-separated skills the job should mention."},
                    "min_salary": {"type": "number", "description": "Minimum salary filter."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_details",
            "description": (
                "Return full details for one job: description, company info, "
                "deadline, location, salary, and recent posting information. "
                "Returns an error string if the job id does not exist."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "integer", "description": "ID of the job to look up."},
                },
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": (
                "Find upcoming events by name, city, date range, major, or "
                "eligibility. Returns a short formatted list, or a plain "
                "no-match message if nothing fits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Partial or full event name to match."},
                    "city": {"type": "string", "description": "City to filter by."},
                    "within_days": {
                        "type": "integer",
                        "description": "Only include events within this many days from today.",
                    },
                    "eligibility": {"type": "string", "description": "Eligibility text to match, e.g. 'CS majors'."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_job_or_event",
            "description": (
                "Save a job or event for the current student (bookmarking it). "
                "This changes state and is gated by a confirmation step "
                "before it runs. Returns a confirmation string, or a clear "
                "error if the id doesn't exist or the save fails."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "integer", "description": "ID of the student saving the item."},
                    "item_type": {"type": "string", "enum": ["job", "event"], "description": "What's being saved."},
                    "item_id": {"type": "integer", "description": "ID of the job or event to save."},
                },
                "required": ["student_id", "item_type", "item_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Implementations — each takes (db, **kwargs) and returns a string
# ---------------------------------------------------------------------------

def get_student_preferences(db: Session, student_id: int = None, **_) -> str:
    try:
        if student_id is None:
            return "No student_id was provided, so preferences cannot be looked up."
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return f"No student found with id {student_id}."

        parts = []
        if student.city:
            parts.append(f"preferred city: {student.city}")
        if student.major:
            parts.append(f"major: {student.major}")
        if student.skills:
            parts.append(f"skills: {student.skills}")

        if not parts:
            return "This student has no saved preferences yet."
        return "Saved preferences — " + "; ".join(parts) + "."
    except Exception as exc:  # tool must never raise
        return f"Error looking up student preferences: {exc}"


def search_jobs(
    db: Session,
    title: str = None,
    category: str = None,
    city: str = None,
    remote: bool = None,
    skills: str = None,
    min_salary: float = None,
    **_,
) -> str:
    try:
        query = db.query(Job)
        if title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        if category:
            query = query.filter(Job.category == category)
        if city:
            if remote:
                query = query.filter((Job.city.ilike(f"%{city}%")) | (Job.location.ilike("%remote%")))
            else:
                query = query.filter(Job.city.ilike(f"%{city}%"))
        elif remote:
            query = query.filter(Job.location.ilike("%remote%"))
        if skills:
            for skill in [s.strip() for s in skills.split(",") if s.strip()]:
                query = query.filter(Job.skills.ilike(f"%{skill}%"))
        if min_salary is not None:
            query = query.filter(Job.salary >= min_salary)

        jobs = query.order_by(Job.posting_date.desc()).limit(10).all()
        if not jobs:
            return "No jobs matched those filters."

        lines = []
        for j in jobs:
            deadline = j.deadline.strftime("%Y-%m-%d") if j.deadline else "no deadline listed"
            salary = f"${j.salary:.0f}" if j.salary else "salary not listed"
            lines.append(
                f"- id={j.id} | {j.title} at company #{j.company_id} | "
                f"{j.location or j.city} | {j.category.value} | {salary} | deadline {deadline}"
            )
        return "Matching jobs:\n" + "\n".join(lines)
    except Exception as exc:
        return f"Error searching jobs: {exc}"


def get_job_details(db: Session, job_id: int = None, **_) -> str:
    try:
        if job_id is None:
            return "No job_id was provided."
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return f"No job found with id {job_id}."

        deadline = job.deadline.strftime("%Y-%m-%d") if job.deadline else "no deadline listed"
        salary = f"${job.salary:.0f}" if job.salary else "salary not listed"
        return (
            f"Job #{job.id}: {job.title}\n"
            f"Company id: {job.company_id}\n"
            f"Category: {job.category.value}\n"
            f"Location: {job.location or job.city}\n"
            f"Salary: {salary}\n"
            f"Deadline: {deadline}\n"
            f"Posted: {job.posting_date.strftime('%Y-%m-%d')}\n"
            f"Description: {job.description or 'No description provided.'}"
        )
    except Exception as exc:
        return f"Error fetching job details: {exc}"


def search_events(
    db: Session,
    name: str = None,
    city: str = None,
    within_days: int = None,
    eligibility: str = None,
    **_,
) -> str:
    try:
        query = db.query(Event).filter(Event.date >= datetime.utcnow())
        if name:
            query = query.filter(Event.name.ilike(f"%{name}%"))
        if city:
            query = query.filter(Event.city.ilike(f"%{city}%"))
        if eligibility:
            query = query.filter(Event.eligibility.ilike(f"%{eligibility}%"))
        if within_days is not None:
            cutoff = datetime.utcnow() + timedelta(days=within_days)
            query = query.filter(Event.date <= cutoff)

        events = query.order_by(Event.date.asc()).limit(10).all()
        if not events:
            return "No upcoming events matched those filters."

        lines = []
        for e in events:
            lines.append(
                f"- id={e.id} | {e.name} | {e.date.strftime('%Y-%m-%d')} "
                f"{e.time or ''} | {e.location or e.city} | eligibility: {e.eligibility or 'open to all'}"
            )
        return "Matching events:\n" + "\n".join(lines)
    except Exception as exc:
        return f"Error searching events: {exc}"


def save_job_or_event(
    db: Session,
    student_id: int = None,
    item_type: str = None,
    item_id: int = None,
    **_,
) -> str:
    try:
        if student_id is None or item_type is None or item_id is None:
            return "Missing required fields: student_id, item_type, and item_id are all required."
        if item_type not in ("job", "event"):
            return f"Invalid item_type '{item_type}' — must be 'job' or 'event'."

        if item_type == "job":
            exists = db.query(Job).filter(Job.id == item_id).first()
        else:
            exists = db.query(Event).filter(Event.id == item_id).first()
        if not exists:
            return f"No {item_type} found with id {item_id} — nothing was saved."

        saved = SavedItem(student_id=student_id, item_type=item_type, item_id=item_id)
        db.add(saved)
        db.commit()
        return f"Saved {item_type} #{item_id} for student #{student_id}."
    except Exception as exc:
        db.rollback()
        return f"Error saving {item_type or 'item'}: {exc}"


TOOL_IMPLEMENTATIONS = {
    "get_student_preferences": get_student_preferences,
    "search_jobs": search_jobs,
    "get_job_details": get_job_details,
    "search_events": search_events,
    "save_job_or_event": save_job_or_event,
}
