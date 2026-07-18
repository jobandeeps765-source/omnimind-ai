from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.utils import get_current_user
from app.memory import service

router = APIRouter(prefix="/memory", tags=["memory"])


class FactIn(BaseModel):
    text: str


@router.get("")
async def list_memory(user: dict = Depends(get_current_user)):
    return await service.list_facts(str(user["_id"]))


@router.post("")
async def create_memory(body: FactIn, user: dict = Depends(get_current_user)):
    fact_id = await service.add_fact(str(user["_id"]), body.text, source="manual")
    return {"id": fact_id}


@router.put("/{fact_id}")
async def edit_memory(fact_id: str, body: FactIn, user: dict = Depends(get_current_user)):
    ok = await service.update_fact(str(user["_id"]), fact_id, body.text)
    if not ok:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"ok": True}


@router.delete("/{fact_id}")
async def remove_memory(fact_id: str, user: dict = Depends(get_current_user)):
    ok = await service.delete_fact(str(user["_id"]), fact_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"ok": True}
