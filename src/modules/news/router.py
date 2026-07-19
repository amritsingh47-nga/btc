from typing import Optional

from fastapi import APIRouter

from . import service

router = APIRouter(prefix="/api/modules/news", tags=["news"])


@router.get("/feed")
async def feed(limit: int = 100, instrument: Optional[str] = None,
               political: bool = False):
    return service.get_news(limit=min(max(limit, 1), 300),
                            instrument=instrument, political_only=political)


@router.post("/refresh")
async def refresh():
    return service.refresh(force=True)


@router.get("/sentiment/{symbol}")
async def sentiment(symbol: str):
    return service.get_instrument_sentiment(symbol)
