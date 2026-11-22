import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.content.bank import bank, forms, mocks
from app.routers import forms as forms_router
from app.routers import drafts, mock, practice, progress, ratings, settings, speaking, speech

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bank()  # fail fast on invalid content YAML
    forms()
    mocks()
    yield


app = FastAPI(title="iBT Practice API", version="0.7.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin, "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(settings.router)
app.include_router(speech.router)
app.include_router(practice.router)
app.include_router(speaking.router)
app.include_router(forms_router.router)
app.include_router(drafts.router)
app.include_router(mock.router)
app.include_router(progress.router)
app.include_router(ratings.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": app.version}
