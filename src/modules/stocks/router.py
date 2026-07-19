from typing import List

from fastapi import APIRouter, Body

from . import service

router = APIRouter(prefix="/api/modules/stocks", tags=["stocks"])


@router.get("/watchlist")
async def watchlist():
    return {"watchlist": service.get_watchlist()}


@router.post("/watchlist")
async def update_watchlist(tickers: List[str] = Body(..., embed=True)):
    return {"watchlist": service.set_watchlist(tickers)}


@router.get("/quotes")
async def quotes():
    return service.get_quotes()


@router.get("/candles/{ticker}")
async def candles(ticker: str, interval: str = "1d", limit: int = 180):
    return service.get_candles(ticker, interval=interval, limit=min(max(limit, 10), 500))


@router.get("/earnings")
async def earnings(days: int = 14):
    return service.get_earnings_calendar(days_ahead=min(max(days, 1), 60))


@router.get("/news/{ticker}")
async def ticker_news(ticker: str):
    return service.get_ticker_news(ticker)
