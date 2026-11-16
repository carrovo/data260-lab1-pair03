from fastapi import FastAPI

from backend.common.runtime import configure_threadpool
from fastapi.middleware.cors import CORSMiddleware

from backend.common.tracing import TraceMiddleware
from backend.app.routers.company_jobs import router as company_jobs_router
from backend.app.routers.jobs import router as jobs_router


app = FastAPI(
    title="DATA 260 Lab 2 - Pair 03 Job Service",
    version="0.2.0",
)

configure_threadpool(app)
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

app.add_middleware(TraceMiddleware, service="job")

app.include_router(jobs_router)
app.include_router(company_jobs_router)


@app.get("/")
def read_root():
    return {
        "message": "Pair 03 Job Service is running",
        "service": "job",
        "pair": "03",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "job",
        "pair": "03",
    }
