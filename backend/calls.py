import sqlite3
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from buying import DB_PATH
from credits import credit_balance, _get_account

router = APIRouter(prefix="/api", tags=["calls"])

CALL_RATE_PER_MIN = 0.10

def _init_calls_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                call_id        TEXT PRIMARY KEY,
                account_id     TEXT NOT NULL,
                number         TEXT NOT NULL,
                duration_sec   INTEGER NOT NULL,
                cost           REAL NOT NULL,
                called_at      TEXT NOT NULL
            )
        """)
_init_calls_table()

class CallRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    number: str = Field(..., min_length=1)
    duration_sec: int = Field(..., ge=0)

class CallResponse(BaseModel):
    call_id: str
    cost: float
    new_balance: float

class CallRecord(BaseModel):
    call_id: str
    number: str
    duration_sec: int
    cost: float
    called_at: str

@router.post("/calls", response_model=CallResponse)
def log_call(req: CallRequest):
    cost = (req.duration_sec / 60.0) * CALL_RATE_PER_MIN
    if cost > 0:
        new_balance = credit_balance(req.account_id, -cost, "call")
    else:
        new_balance = _get_account(req.account_id)["balance"]

    call_id = "call_" + secrets.token_hex(6)
    now = datetime.utcnow().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO calls (call_id,account_id,number,duration_sec,cost,called_at) VALUES (?,?,?,?,?,?)",
            (call_id, req.account_id, req.number, req.duration_sec, cost, now),
        )

    return CallResponse(call_id=call_id, cost=round(cost, 2), new_balance=new_balance)

@router.get("/accounts/{account_id}/calls", response_model=list[CallRecord])
def get_calls(account_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM calls WHERE account_id = ? ORDER BY called_at DESC", (account_id,)
        ).fetchall()
    return [CallRecord(**dict(r)) for r in rows]