"""Estado do sistema — ferramentas externas, GPU, modelos instalados."""
from __future__ import annotations

from fastapi import APIRouter

from app.core import config

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/capabilities")
def capabilities():
    return config.capabilities()
