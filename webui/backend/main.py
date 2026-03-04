from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webui.backend.api.configs import router as configs_router
from webui.backend.api.datasets import router as datasets_router
from webui.backend.api.jobs import router as jobs_router
from webui.backend.api.references import router as references_router
from webui.backend.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SEED4D Web UI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(configs_router)
app.include_router(references_router)
app.include_router(jobs_router)
app.include_router(datasets_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
