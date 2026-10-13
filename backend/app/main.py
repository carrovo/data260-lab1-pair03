from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    company_auth,
    company_profile,
    jobs,
    applications,
    events,
    students_search,
    assistant,
)

app = FastAPI(
    title="Handshake — Pair 03 (Company side + AI assistant)",
    description=(
        "Company-side endpoints (auth, profile, jobs, applicants, events, "
        "student search) plus the hand-built AI assistant (Ollama agent "
        "loop + tools). Student-side endpoints are owned by Xuanhua and "
        "merge in separately — see README for integration notes."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9031", "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dev convenience only — in the real submission, prefer Alembic migrations
# over create_all() so schema changes from both halves of the team are
# tracked. Left here so this half of the app is runnable standalone.
Base.metadata.create_all(bind=engine)

app.include_router(company_auth.router)
app.include_router(company_profile.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(events.router)
app.include_router(students_search.router)
app.include_router(assistant.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "pair": "03"}
