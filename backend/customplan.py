import io
import base64
import sqlite3
import secrets
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import qrcode
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from buying import DB_PATH, SMDP_HOST, _gen_iccid, _gen_lpa, _qr_data_uri
from credits import credit_balance, _get_account

router = APIRouter(prefix="/api", tags=["customplan"])

class CustomPlanRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    email: str
    data_gb: int = Field(..., ge=1, le=100)
    days: int = Field(..., ge=1, le=90)

class CustomPlanResponse(BaseModel):
    order_id: str
    iccid: str
    lpa_string: str
    qr_data_uri: str
    expires_at: str
    amount: float
    new_balance: float

@router.post("/custom-buy", response_model=CustomPlanResponse)
def buy_custom(req: CustomPlanRequest):
    # 1. Calculate price ($3 per GB, $1 per day)
    price = (req.data_gb * 3.0) + (req.days * 1.0)
    
    # 2. Deduct credits (throws 402 error if insufficient)
    new_balance = credit_balance(req.account_id, -price, "buy:custom")

    # 3. Generate eSIM details
    order_id = "ord_" + secrets.token_hex(6)
    txn_id = "txn_" + secrets.token_hex(8)
    paid_at = datetime.utcnow()
    expires = paid_at + timedelta(days=req.days)
    iccid = _gen_iccid()
    activation_id = uuid.uuid4().hex
    lpa = _gen_lpa(activation_id)
    qr_uri = _qr_data_uri(lpa)
    data_mb = req.data_gb * 1024

    # 4. Save to Database
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO orders (order_id,account_id,email,plan_id,amount,transaction_id,paid_at) VALUES (?,?,?,?,?,?,?)",
            (order_id, req.account_id, req.email, "custom", price, txn_id, paid_at.isoformat()),
        )
        conn.execute(
            "INSERT INTO esims (iccid,order_id,account_id,plan_id,activation_id,smdp_address,lpa_string,status,issued_at,expires_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (iccid, order_id, req.account_id, f"custom-{data_mb}", activation_id, SMDP_HOST, lpa, "issued",
             paid_at.isoformat(), expires.isoformat()),
        )

    return CustomPlanResponse(
        order_id=order_id,
        iccid=iccid,
        lpa_string=lpa,
        qr_data_uri=qr_uri,
        expires_at=expires.isoformat(),
        amount=price,
        new_balance=new_balance,
    )