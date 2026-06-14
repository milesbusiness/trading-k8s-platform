"""
Order Service — manages order lifecycle with pre-trade risk checks via gRPC to risk-service.
"""
import uuid
import logging
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, make_asgi_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ORDERS_SUBMITTED = Counter("orders_submitted_total", "Total orders submitted", ["status"])
ORDER_LATENCY = Histogram("order_processing_seconds", "Order processing latency", buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5])

RISK_SERVICE_URL = "http://risk-service:8082"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    trader_id: str


class Order(BaseModel):
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    limit_price: float | None
    trader_id: str
    status: str
    created_at: str
    risk_approved: bool = False


orders_db: dict[str, Order] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Order Service", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.post("/api/orders", response_model=Order)
async def create_order(request: OrderRequest):
    with ORDER_LATENCY.time():
        # Pre-trade risk check
        try:
            async with httpx.AsyncClient(timeout=0.1) as client:
                risk_resp = await client.post(
                    f"{RISK_SERVICE_URL}/api/risk/check",
                    json={
                        "symbol": request.symbol,
                        "side": request.side,
                        "quantity": request.quantity,
                        "trader_id": request.trader_id
                    }
                )
                risk_result = risk_resp.json()
                risk_approved = risk_result.get("approved", False)
                if not risk_approved:
                    ORDERS_SUBMITTED.labels(status="rejected").inc()
                    raise HTTPException(400, f"Risk check failed: {risk_result.get('reason', 'Unknown')}")
        except httpx.TimeoutException:
            # Risk service circuit breaker — reject on timeout to protect capital
            ORDERS_SUBMITTED.labels(status="risk_timeout").inc()
            raise HTTPException(503, "Risk service unavailable — order rejected for capital protection")

        order = Order(
            order_id=str(uuid.uuid4()),
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
            trader_id=request.trader_id,
            status="ACCEPTED",
            created_at=datetime.utcnow().isoformat(),
            risk_approved=True
        )

        orders_db[order.order_id] = order
        ORDERS_SUBMITTED.labels(status="accepted").inc()
        logger.info(f"Order {order.order_id} accepted: {order.side} {order.quantity} {order.symbol}")
        return order


@app.get("/api/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    if order_id not in orders_db:
        raise HTTPException(404, "Order not found")
    return orders_db[order_id]


@app.get("/api/orders")
async def list_orders(trader_id: str | None = None):
    orders = list(orders_db.values())
    if trader_id:
        orders = [o for o in orders if o.trader_id == trader_id]
    return {"orders": orders, "total": len(orders)}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "order-service", "orders": len(orders_db)}
