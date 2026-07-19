from typing import Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/api/modules/portfolio", tags=["portfolio"])


class PositionIn(BaseModel):
    symbol: str
    direction: str          # long | short
    size: float
    entry_price: float
    asset_type: str = 'stock'   # stock | futures | crypto | fx
    notes: str = ''


class PositionPatch(BaseModel):
    symbol: Optional[str] = None
    direction: Optional[str] = None
    size: Optional[float] = None
    entry_price: Optional[float] = None
    asset_type: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def portfolio():
    return service.get_portfolio_with_pnl()


@router.post("")
async def add(position: PositionIn):
    try:
        return service.add_position(**position.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/{pos_id}")
async def patch(pos_id: str, changes: PositionPatch):
    updated = service.update_position(pos_id, **changes.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="position not found")
    return updated


@router.delete("/{pos_id}")
async def delete(pos_id: str):
    if not service.delete_position(pos_id):
        raise HTTPException(status_code=404, detail="position not found")
    return {"deleted": pos_id}
