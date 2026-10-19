from fastapi import APIRouter
from pydantic import BaseModel

from buying import PLANS

router = APIRouter(prefix="/api", tags=["plans"])


class Plan(BaseModel):
    id: str
    name: str
    region: str
    data_mb: int
    days: int
    price: float


@router.get("/plans", response_model=list[Plan])
def list_plans() -> list[Plan]:
    return [
        Plan(id=pid, name=p["name"], region=p["region"], data_mb=p["data_mb"], days=p["days"], price=p["price"])
        for pid, p in PLANS.items()
    ]