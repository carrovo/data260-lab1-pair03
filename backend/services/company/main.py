from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.company_applications import (
    router as company_applications_router,
)
from backend.app.routers.company_auth import router as company_auth_router
from backend.app.routers.company_events import router as company_events_router
from backend.app.routers.company_jobs import router as company_jobs_router
from backend.app.routers.company_profile import router as company_profile_router
from backend.app.routers.students_search import router as students_search_router


app = FastAPI(
    title="DATA 260 Lab 2 - Pair 03 Company Service",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(company_auth_router)
app.include_router(company_profile_router)
app.include_router(company_jobs_router)
app.include_router(company_applications_router)
app.include_router(company_events_router)
app.include_router(students_search_router)


@app.get("/")
def read_root():
    return {
        "message": "Pair 03 Company Service is running",
        "service": "company",
        "pair": "03",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "company",
        "pair": "03",
    }
