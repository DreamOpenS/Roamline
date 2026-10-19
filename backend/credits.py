import sqlite3
import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from buying import DB_PATH

router = APIRouter(prefix="/api", tags=["credits"])

CREDIT_PACKS = {
    "cr-10": {"label": "$10", "amount": 10.0},
    "cr-25": {"label": "$25", "amount": 25.0},
    "cr-50": {"label": "$50", "amount": 50.0},
    "cr-100": {"label": "$100", "amount": 100.0},
}


class CreditPack(BaseModel):
    id: str
    label: str
    amount: float


class CreditBalance(BaseModel):
    account_id: str
    balance: float


class AddCreditsRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    pack_id: str = Field(..., min_length=1)


class CreditTransaction(BaseModel):
    txn_id: str
    account_id: str
    amount: float
    kind: str
    at: str


def init_credits():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                email      TEXT NOT NULL,
                name       TEXT NOT NULL,
                balance    REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS credit_txns (
                txn_id     TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                amount     REAL NOT NULL,
                kind       TEXT NOT NULL,
                at         TEXT NOT NULL
            );
        """)


init_credits()


def _get_account(account_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="account not found")
    return row


def credit_balance(account_id, amount, kind):
    acct = _get_account(account_id)
    new_balance = acct["balance"] + amount
    if new_balance < 0:
        raise HTTPException(status_code=402, detail="insufficient credits")
    txn_id = "ctx_" + secrets.token_hex(6)
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE accounts SET balance = ? WHERE account_id = ?", (new_balance, account_id))
        conn.execute(
            "INSERT INTO credit_txns (txn_id,account_id,amount,kind,at) VALUES (?,?,?,?,?)",
            (txn_id, account_id, amount, kind, now),
        )
    return new_balance


@router.get("/credits/packs", response_model=list[CreditPack])
def list_credit_packs():
    return [CreditPack(id=k, **v) for k, v in CREDIT_PACKS.items()]


@router.get("/credits/{account_id}", response_model=CreditBalance)
def get_balance(account_id: str):
    acct = _get_account(account_id)
    return CreditBalance(account_id=account_id, balance=acct["balance"])


@router.post("/credits/{account_id}/add", response_model=CreditBalance)
def add_credits(account_id: str, req: AddCreditsRequest):
    pack = CREDIT_PACKS.get(req.pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="credit pack not found")
    new_balance = credit_balance(account_id, pack["amount"], f"topup:{req.pack_id}")
    return CreditBalance(account_id=account_id, balance=new_balance)


@router.get("/credits/{account_id}/history", response_model=list[CreditTransaction])
def history(account_id: str):
    _get_account(account_id)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM credit_txns WHERE account_id = ? ORDER BY at DESC", (account_id,)
        ).fetchall()
    return [CreditTransaction(**dict(r)) for r in rows]