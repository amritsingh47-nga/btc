from fastapi import APIRouter

from . import service

router = APIRouter(prefix="/api/modules/macro", tags=["macro"])


@router.get("/overview")
async def overview():
    return service.get_overview()


@router.get("/series/{series_id}")
async def series(series_id: str):
    return service.get_series(series_id)


@router.get("/calendar")
async def calendar(days: int = 14):
    return service.get_release_calendar(days_ahead=min(max(days, 1), 60))


@router.get("/warning")
async def warning():
    return {"warning": service.get_macro_warning()}
