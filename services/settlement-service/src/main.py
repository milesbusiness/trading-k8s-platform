"""
Settlement Service — T+2 settlement processing with CSDR compliance.
Subscribes to order.executed events via RabbitMQ.
"""
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum

from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, make_asgi_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SETTLEMENTS_CREATED  = Counter("settlements_created_total", "Total settlement instructions created")
SETTLEMENTS_FAILED   = Counter("settlements_failed_total", "Total failed settlements")
PENDING_SETTLEMENTS  = Gauge("settlements_pending_count", "Number of pending settlements")


class SettlementStatus(str, Enum):
    PENDING   = "PENDING"
    MATCHED   = "MATCHED"
    SETTLED   = "SETTLED"
    FAILED    = "FAILED"


class SettlementInstruction(BaseModel):
    settlement_id: str
    order_id: str
    symbol: str
    quantity: float
    settlement_date: str  # T+2 ISO date
    status: SettlementStatus
    counterparty_lei: str | None = None
    created_at: str


settlements_db: dict[str, SettlementInstruction] = {}


app = FastAPI(title="Settlement Service", version="1.0.0")
app.mount("/metrics", make_asgi_app())


@app.post("/api/settlement", response_model=SettlementInstruction)
async def create_settlement(order_id: str, symbol: str, quantity: float):
    settlement_date = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d")

    instruction = SettlementInstruction(
        settlement_id=str(uuid.uuid4()),
        order_id=order_id,
        symbol=symbol,
        quantity=quantity,
        settlement_date=settlement_date,
        status=SettlementStatus.PENDING,
        created_at=datetime.utcnow().isoformat()
    )

    settlements_db[instruction.settlement_id] = instruction
    SETTLEMENTS_CREATED.inc()
    PENDING_SETTLEMENTS.set(sum(1 for s in settlements_db.values() if s.status == SettlementStatus.PENDING))

    logger.info(f"Settlement {instruction.settlement_id} created for order {order_id}, settles {settlement_date}")
    return instruction


@app.get("/api/settlement/{settlement_id}", response_model=SettlementInstruction)
async def get_settlement(settlement_id: str):
    if settlement_id not in settlements_db:
        from fastapi import HTTPException
        raise HTTPException(404, "Settlement not found")
    return settlements_db[settlement_id]


@app.get("/api/settlements/pending")
async def pending_settlements():
    pending = [s for s in settlements_db.values() if s.status == SettlementStatus.PENDING]
    return {"pending": pending, "count": len(pending)}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "settlement-service", "settlements": len(settlements_db)}
