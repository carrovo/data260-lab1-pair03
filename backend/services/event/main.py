from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.common.tracing import TraceMiddleware
from backend.app.routers.company_events import router as company_events_router
from backend.app.routers.events import router as events_router
from backend.app.routers.registration_routes import (
    router as registration_router,
)


app = FastAPI(
    title="DATA 260 Lab 2 - Pair 03 Event Service",
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

app.add_middleware(TraceMiddleware, service="event")

app.include_router(events_router)
app.include_router(registration_router)
app.include_router(company_events_router)


@app.get("/")
def read_root():
    return {
        "message": "Pair 03 Event Service is running",
        "service": "event",
        "pair": "03",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "event",
        "pair": "03",
    }
