import io
import base64
import sqlite3
from datetime import datetime
import qrcode
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from buying import DB_PATH, PLANS

router = APIRouter(prefix="/api", tags=["esims"])

class EsimView(BaseModel):
    iccid: str
    order_id: str
    account_id: str | None
    plan_id: str
    plan_name: str
    region: str
    total_mb: int
    used_mb: int
    left_mb: int
    lpa_string: str
    qr_data_uri: str
    status: str
    issued_at: str
    expires_at: str
    expired: bool

class EsimSummary(BaseModel):
    iccid: str
    plan_id: str
    plan_name: str
    region: str
    status: str
    total_mb: int
    used_mb: int
    left_mb: int
    expires_at: str

class UsageRequest(BaseModel):
    mb: int = Field(..., gt=0, le=10240)

class UsageResponse(BaseModel):
    iccid: str
    used_mb: int
    left_mb: int
    status: str

def _qr_data_uri(payload: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

def _ensure_usage_column() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(esims)").fetchall()}
        if "used_mb" not in cols:
            conn.execute("ALTER TABLE esims ADD COLUMN used_mb INTEGER NOT NULL DEFAULT 0")
        if "account_id" not in cols:
            conn.execute("ALTER TABLE esims ADD COLUMN account_id TEXT")

_ensure_usage_column()

def _fetch(iccid):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM esims WHERE iccid = ?", (iccid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="esim not found")
    return row

def _effective_total(iccid, plan_id):
    from topup import _topup_total_mb
    if plan_id.startswith("custom-"):
        base = int(plan_id.split("-")[1])
    else:
        plan = PLANS.get(plan_id)
        base = plan["data_mb"] if plan else 0
    return base + _topup_total_mb(iccid)

def _status_for(row, total, used):
    left = max(0, total - used)
    expired = datetime.utcnow().isoformat() > row["expires_at"]
    if expired: return "expired"
    if left == 0: return "depleted"
    return row["status"]

@router.get("/esims/{iccid}", response_model=EsimView)
def get_esim(iccid: str) -> EsimView:
    row = _fetch(iccid)
    if row["plan_id"].startswith("custom-"):
        data_mb = int(row["plan_id"].split("-")[1])
        plan = {"name": f"Custom {data_mb/1024:g}GB", "region": "Custom"}
    else:
        plan = PLANS.get(row["plan_id"], {"name": "Unknown", "region": "—"})
    total = _effective_total(iccid, row["plan_id"])
    used = row["used_mb"] or 0
    left = max(0, total - used)
    expired = datetime.utcnow().isoformat() > row["expires_at"]
    return EsimView(
        iccid=row["iccid"],
        order_id=row["order_id"],
        account_id=row["account_id"] if "account_id" in row.keys() else None,
        plan_id=row["plan_id"],
        plan_name=plan["name"],
        region=plan["region"],
        total_mb=total,
        used_mb=used,
        left_mb=left,
        lpa_string=row["lpa_string"],
        qr_data_uri=_qr_data_uri(row["lpa_string"]),
        status=_status_for(row, total, used),
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        expired=expired,
    )

@router.get("/accounts/{account_id}/esims", response_model=list[EsimSummary])
def list_account_esims(account_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM esims WHERE account_id = ? ORDER BY issued_at DESC", (account_id,)
        ).fetchall()
    out = []
    for row in rows:
        if row["plan_id"].startswith("custom-"):
            data_mb = int(row["plan_id"].split("-")[1])
            plan = {"name": f"Custom {data_mb/1024:g}GB", "region": "Custom"}
        else:
            plan = PLANS.get(row["plan_id"], {"name": "Unknown", "region": "—"})
        total = _effective_total(row["iccid"], row["plan_id"])
        used = row["used_mb"] or 0
        out.append(EsimSummary(
            iccid=row["iccid"],
            plan_id=row["plan_id"],
            plan_name=plan["name"],
            region=plan["region"],
            status=_status_for(row, total, used),
            total_mb=total,
            used_mb=used,
            left_mb=max(0, total - used),
            expires_at=row["expires_at"],
        ))
    return out

@router.post("/esims/{iccid}/usage", response_model=UsageResponse)
def burn_usage(iccid: str, req: UsageRequest) -> UsageResponse:
    row = _fetch(iccid)
    total = _effective_total(iccid, row["plan_id"])
    used = row["used_mb"] or 0
    left = max(0, total - used)
    if left == 0:
        raise HTTPException(status_code=409, detail="data exhausted")
    if datetime.utcnow().isoformat() > row["expires_at"]:
        raise HTTPException(status_code=409, detail="esim expired")
    spend = min(req.mb, left)
    new_used = used + spend
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE esims SET used_mb = ? WHERE iccid = ?", (new_used, iccid))
    return UsageResponse(iccid=iccid, used_mb=new_used, left_mb=total - new_used,
                        status="depleted" if total - new_used == 0 else "active")