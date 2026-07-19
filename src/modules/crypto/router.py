from fastapi import APIRouter

from . import service

router = APIRouter(prefix="/api/modules/crypto", tags=["crypto"])


@router.get("/markets")
async def markets(limit: int = 25):
    return service.get_markets(limit=min(max(limit, 1), 100))


@router.get("/trending")
async def trending():
    return service.get_trending()


@router.get("/chart/{coin_id}")
async def chart(coin_id: str, days: int = 30):
    return service.get_coin_chart(coin_id, days=min(max(days, 1), 365))


@router.get("/fear-greed")
async def fear_greed(limit: int = 30):
    return service.get_fear_greed(limit=min(max(limit, 1), 90))
