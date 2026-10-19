import sqlite3
import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from buying import DB_PATH

router = APIRouter(prefix="/api", tags=["accounts"])


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr


class Account(BaseModel):
    account_id: str
    name: str
    email: str
    balance: float
    created_at: str


def _row_to_account(row):
    return Account(
        account_id=row["account_id"],
        name=row["name"],
        email=row["email"],
        balance=row["balance"],
        created_at=row["created_at"],
    )


@router.post("/accounts/signup", response_model=Account)
def signup(req: SignupRequest):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute("SELECT * FROM accounts WHERE email = ?", (req.email,)).fetchone()
        if existing:
            return _row_to_account(existing)

        account_id = "acc_" + secrets.token_hex(8)
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO accounts (account_id,email,name,balance,created_at) VALUES (?,?,?,?,?)",
            (account_id, req.email, req.name, 25.0, now),
        )
        row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    return _row_to_account(row)


@router.get("/accounts/{account_id}", response_model=Account)
def get_account(account_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="account not found")
    return _row_to_account(row)