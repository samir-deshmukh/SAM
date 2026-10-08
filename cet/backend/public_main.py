"""Candidate-facing FastAPI service.

This entrypoint deliberately exposes only the public API. Admin login,
imports, PDF processing, publishing, and resolver work remain in
backend.main so they cannot compete with student traffic on the public
service.

Required runtime configuration:
- DATABASE_URL
- CET_DATA_ALLOWED_ORIGINS (comma-separated frontend origins)

The health endpoint does not require a database connection.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as public_api_router

app = FastAPI(
    title="CETFind Public API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CET_DATA_ALLOWED_ORIGINS",
        "https://cetfind.onrender.com",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Cheap liveness endpoint for the hosting platform."""
    return {"ok": True}


app.include_router(public_api_router)
