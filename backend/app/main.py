from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .config import CORS_ORIGINS, ENABLE_SCHEDULER
from .routers import reconcile, exceptions, metrics, settings

app = FastAPI(
    title="AI Finance Controller",
    description="Multi-level payment reconciliation with an agentic exception investigator.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reconcile.router)
app.include_router(exceptions.router)
app.include_router(metrics.router)
app.include_router(settings.router)


@app.on_event("startup")
def on_startup():
    init_db()
    if ENABLE_SCHEDULER:
        from .scheduler import start_scheduler
        start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    if ENABLE_SCHEDULER:
        from .scheduler import stop_scheduler
        stop_scheduler()


@app.get("/")
def root():
    return {
        "service": "ai-finance-controller",
        "status": "ok",
        "endpoints": [
            "POST /reconcile/seed", "POST /reconcile/run", "GET /reconcile/runs",
            "GET /reconcile/runs/{id}/report.csv",
            "POST /reconcile/import/preview", "POST /reconcile/import",
            "GET /reconcile/import/template/{settlement|bank}",
            "GET /reconcile/import/example/{settlement|bank}",
            "GET /exceptions", "GET /exceptions/{id}", "GET /exceptions/{id}/audit",
            "POST /exceptions/{id}/resolve", "POST /exceptions/bulk-resolve",
            "GET /metrics", "GET /metrics/trend",
            "GET /settings", "POST /settings", "GET /settings/simulate",
        ],
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
