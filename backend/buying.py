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
from pydantic import BaseModel, EmailStr, Field

DB_PATH = Path(__file__).parent / "roamline.db"
SMDP_HOST = "rsp.demo-roamline.example"

PLANS = {
    "eu-1":   {"name": "Europe Lite",     "region": "Europe",        "data_mb": 1024,  "days": 7,  "price": 9.00},
    "eu-5":   {"name": "Europe Plus",     "region": "Europe",        "data_mb": 5120,  "days": 15, "price": 19.00},
    "eu-20":  {"name": "Europe Max",      "region": "Europe",        "data_mb": 20480, "days": 30, "price": 39.00},
    "as-3":   {"name": "Asia Pass",       "region": "Asia",          "data_mb": 3072,  "days": 14, "price": 17.00},
    "as-10":  {"name": "Asia Max",        "region": "Asia",          "data_mb": 10240, "days": 30, "price": 34.00},
    "gl-5":   {"name": "Global Starter",  "region": "Global",        "data_mb": 5120,  "days": 15, "price": 29.00},
    "gl-20":  {"name": "Global Pro",      "region": "Global",        "data_mb": 20480, "days": 30, "price": 59.00},
    "us-10":  {"name": "USA + Canada",    "region": "North America", "data_mb": 10240, "days": 30, "price": 36.00},
    "jp-5":   {"name": "Japan Pass",      "region": "Japan",         "data_mb": 5120,  "days": 14, "price": 22.00},
    "th-5":   {"name": "Thailand Pass",   "region": "Thailand",      "data_mb": 5120,  "days": 14, "price": 18.00},
    "au-10":  {"name": "Australia Pass",  "region": "Australia",     "data_mb": 10240, "days": 30, "price": 32.00},
    "me-10":  {"name": "Middle East",     "region": "Middle East",   "data_mb": 10240, "days": 30, "price": 41.00},
}


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id        TEXT PRIMARY KEY,
                account_id      TEXT,
                email           TEXT NOT NULL,
                plan_id         TEXT NOT NULL,
                amount          REAL NOT NULL,
                transaction_id  TEXT NOT NULL,
                paid_at         TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS esims (
                iccid           TEXT PRIMARY KEY,
                order_id        TEXT NOT NULL REFERENCES orders(order_id),
                account_id      TEXT,
                plan_id         TEXT NOT NULL,
                activation_id   TEXT NOT NULL,
                smdp_address    TEXT NOT NULL,
                lpa_string      TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'issued',
                issued_at       TEXT NOT NULL,
                expires_at      TEXT NOT NULL
            );
        """)


init_db()


class BuyRequest(BaseModel):
    plan_id: str = Field(..., min_length=1)
    email: EmailStr
    account_id: str | None = None
    pay_with_credits: bool = False
    custom_data_mb: int | None = None
    custom_days: int | None = None


class BuyResponse(BaseModel):
    order_id: str
    iccid: str
    lpa_string: str
    activation_id: str
    smdp_address: str
    qr_data_uri: str
    expires_at: str
    amount: float
    paid_with_credits: bool
    new_balance: float | None


def _gen_iccid() -> str:
    return "89" + "".join(str(random.randint(0, 9)) for _ in range(18))


def _gen_lpa(activation_id: str) -> str:
    return f"LPA:1${SMDP_HOST}${activation_id}"


def _qr_data_uri(payload: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


router = APIRouter(prefix="/api", tags=["buying"])


@router.post("/buy", response_model=BuyResponse)
def buy(req: BuyRequest) -> BuyResponse:
    if req.plan_id.startswith("custom-"):
        if not req.custom_data_mb or not req.custom_days:
            raise HTTPException(status_code=400, detail="Missing custom plan details")
        price = (req.custom_data_mb / 1024 * 3) + (req.custom_days * 1)
        plan = {
            "name": f"Custom {req.custom_data_mb/1024:g}GB / {req.custom_days} Days",
            "region": "Custom",
            "data_mb": req.custom_data_mb,
            "days": req.custom_days,
            "price": price
        }
    else:
        plan = PLANS.get(req.plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="plan not found")

    new_balance = None
    if req.pay_with_credits:
        if not req.account_id:
            raise HTTPException(status_code=400, detail="account_id required for credits")
        from credits import credit_balance
        new_balance = credit_balance(req.account_id, -plan["price"], f"buy:{req.plan_id}")

    order_id = "ord_" + secrets.token_hex(6)
    txn_id = "txn_" + secrets.token_hex(8)
    paid_at = datetime.utcnow()
    expires = paid_at + timedelta(days=plan["days"])
    iccid = _gen_iccid()
    activation_id = uuid.uuid4().hex
    lpa = _gen_lpa(activation_id)
    qr_uri = _qr_data_uri(lpa)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO orders (order_id,account_id,email,plan_id,amount,transaction_id,paid_at) VALUES (?,?,?,?,?,?,?)",
            (order_id, req.account_id, req.email, req.plan_id, plan["price"], txn_id, paid_at.isoformat()),
        )
        conn.execute(
            "INSERT INTO esims (iccid,order_id,account_id,plan_id,activation_id,smdp_address,lpa_string,status,issued_at,expires_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (iccid, order_id, req.account_id, req.plan_id, activation_id, SMDP_HOST, lpa, "issued",
             paid_at.isoformat(), expires.isoformat()),
        )

    return BuyResponse(
        order_id=order_id,
        iccid=iccid,
        lpa_string=lpa,
        activation_id=activation_id,
        smdp_address=SMDP_HOST,
        qr_data_uri=qr_uri,
        expires_at=expires.isoformat(),
        amount=plan["price"],
        paid_with_credits=req.pay_with_credits,
        new_balance=new_balance,
    )