"""BandScore AI — API local (FastAPI).

Arranque: uvicorn app.main:app --port 8765
Todo o processamento corre localmente; não há chamadas a serviços externos.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import export, imports, library, projects, recognition, score, system
from app.core import config
from app.core.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="BandScore AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # aplicação local — o Electron serve o frontend
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    """Erros inesperados devolvem JSON legível com CORS — sem isto o browser
    esconde a causa real atrás de um «Failed to fetch»."""
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


for module in (projects, imports, recognition, score, export, library, system):
    app.include_router(module.router)

# páginas, imagens processadas e exportações servidas como estáticos
app.mount("/files", StaticFiles(directory=str(config.data_dir())), name="files")
