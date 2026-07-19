from fastapi import APIRouter

from . import service

router = APIRouter(prefix="/api/modules/fx", tags=["fx"])


@router.get("/rates")
async def rates():
    return service.get_rates()


@router.get("/trend")
async def trend(days: int = 30):
    return service.get_usd_trend(days=min(max(days, 7), 365))
