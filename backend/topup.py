import sqlite3
import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from buying import DB_PATH, PLANS

router = APIRouter(prefix="/api", tags=["topup"])

# ---------------------------------------------------------------------------
# top-up catalog — sold as data blocks, priced per GB, region-agnostic.
# keeps it simple: user pays for raw data, no new plan, no new validity window.
# ---------------------------------------------------------------------------
TOPUP_PACKS = {
    "tb-1":  {"label": "1 GB",  "data_mb": 1024,  "price": 6.00},
    "tb-3":  {"label": "3 GB",  "data_mb": 3072,  "price": 15.00},
    "tb-5":  {"label": "5 GB",  "data_mb": 5120,  "price": 22.00},
    "tb-10": {"label": "10 GB", "data_mb": 10240, "price": 38.00},
}


# ---------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------
class TopupPack(BaseModel):
    id: str
    label: str
    data_mb: int
    price: float


class TopupRequest(BaseModel):
    pack_id: str = Field(..., min_length=1)


class TopupResponse(BaseModel):
    iccid: str
    pack_id: str
    added_mb: int
    total_mb: int      # plan data + all topups
    used_mb: int
    left_mb: int
    amount: float
    transaction_id: str
    status: str


class TopupRecord(BaseModel):
    topup_id: str
    iccid: str
    pack_id: str
    added_mb: int
    amount: float
    transaction_id: str
    paid_at: str


# ---------------------------------------------------------------------------
# db bootstrap — topups table, idempotent
# ---------------------------------------------------------------------------
def _init_topup_table() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topups (
                topup_id       TEXT PRIMARY KEY,
                iccid          TEXT NOT NULL REFERENCES esims(iccid),
                pack_id        TEXT NOT NULL,
                added_mb       INTEGER NOT NULL,
                amount         REAL NOT NULL,
                transaction_id TEXT NOT NULL,
                paid_at        TEXT NOT NULL
            )
        """)


_init_topup_table()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _fetch_esim(iccid: str) -> sqlite3.Row:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM esims WHERE iccid = ?", (iccid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="esim not found")
    return row


def _topup_total_mb(iccid: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(added_mb), 0) FROM topups WHERE iccid = ?", (iccid,)
        ).fetchone()
    return int(row[0])


def _effective_total(iccid: str, plan_id: str) -> int:
    plan = PLANS.get(plan_id)
    base = plan["data_mb"] if plan else 0
    return base + _topup_total_mb(iccid)


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@router.get("/topup/packs", response_model=list[TopupPack])
def list_packs() -> list[TopupPack]:
    return [TopupPack(id=k, **v) for k, v in TOPUP_PACKS.items()]


@router.post("/esims/{iccid}/topup", response_model=TopupResponse)
def topup(iccid: str, req: TopupRequest) -> TopupResponse:
    pack = TOPUP_PACKS.get(req.pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="top-up pack not found")

    esim = _fetch_esim(iccid)

    # reject on expired esim — you can't refill something that's dead.
    if datetime.utcnow().isoformat() > esim["expires_at"]:
        raise HTTPException(status_code=409, detail="esim expired — buy a new plan")

    topup_id = "top_" + secrets.token_hex(6)
    txn_id   = "txn_" + secrets.token_hex(8)
    paid_at  = datetime.utcnow()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO topups (topup_id,iccid,pack_id,added_mb,amount,transaction_id,paid_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (topup_id, iccid, req.pack_id, pack["data_mb"], pack["price"], txn_id, paid_at.isoformat()),
        )

    used_mb  = esim["used_mb"] or 0
    total_mb = _effective_total(iccid, esim["plan_id"])
    left_mb  = max(0, total_mb - used_mb)
    status   = "active" if left_mb > 0 else "depleted"

    return TopupResponse(
        iccid=iccid,
        pack_id=req.pack_id,
        added_mb=pack["data_mb"],
        total_mb=total_mb,
        used_mb=used_mb,
        left_mb=left_mb,
        amount=pack["price"],
        transaction_id=txn_id,
        status=status,
    )


@router.get("/esims/{iccid}/topups", response_model=list[TopupRecord])
def topup_history(iccid: str) -> list[TopupRecord]:
    _fetch_esim(iccid)  # 404 if the esim doesn't exist
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM topups WHERE iccid = ? ORDER BY paid_at ASC", (iccid,)
        ).fetchall()
    return [TopupRecord(**dict(r)) for r in rows]