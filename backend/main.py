from customplan import router as customplan_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from buying import router as buying_router
from plans import router as plans_router
from esims import router as esims_router
from topup import router as topup_router
from credits import router as credits_router
from accounts import router as accounts_router

app = FastAPI(title="Roamline API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customplan_router)
app.include_router(plans_router)
app.include_router(accounts_router)
app.include_router(credits_router)
app.include_router(buying_router)
app.include_router(esims_router)
app.include_router(topup_router)


@app.get("/")
def root():
    return {"ok": True, "service": "roamline", "docs": "/docs"}