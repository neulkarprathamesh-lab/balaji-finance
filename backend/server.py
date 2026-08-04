"""Balaji Convent Fee Software — FastAPI bootstrap.
Routers are split by domain under /app/backend/routers/. Shared infra lives in /app/backend/core.py.
Every endpoint stays under `/api` — clients don't need any change.
"""
import os
import logging
import sys
from pathlib import Path
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

# Ensure this directory is on sys.path so `from core import ...` works when
# uvicorn imports server:app from /app/backend.
sys.path.insert(0, str(Path(__file__).parent))

from core import client, seed_data  # noqa: E402
from routers import auth as auth_router  # noqa: E402
from routers import catalog as catalog_router  # noqa: E402
from routers import students as students_router  # noqa: E402
from routers import receipts as receipts_router  # noqa: E402
from routers import reports as reports_router  # noqa: E402
from routers import config_io as config_io_router  # noqa: E402

app = FastAPI(title="Balaji Convent Fee Software")

app.include_router(auth_router.router)
app.include_router(catalog_router.router)
app.include_router(students_router.router)
app.include_router(receipts_router.router)
app.include_router(reports_router.router)
app.include_router(config_io_router.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    await seed_data()

@app.on_event("shutdown")
async def on_shutdown():
    client.close()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
