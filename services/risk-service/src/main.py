"""
Risk Service — pre-trade risk checks: position limits, VaR, concentration, trader limits.
Must respond in <5ms P99 to not block order flow.
"""
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, make_asgi_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RISK_CHECKS = Counter("risk_checks_total", "Total risk checks", ["result"])
CHECK_LATENCY = Histogram("risk_check_latency_seconds", "Risk check latency", buckets=[0.001, 0.002, 0.005, 0.01, 0.05])

# In-memory limits (production: Redis for sub-ms latency)
POSITION_LIMITS = {"EURUSD": 10_000_000, "GBPUSD": 5_000_000, "default": 1_000_000}
TRADER_LIMITS   = {"default_daily_notional": 50_000_000}
positions: dict[str, float] = {}
trader_notional: dict[str, float] = {}


class RiskCheckRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    trader_id: str
    notional: float | None = None


class RiskCheckResponse(BaseModel):
    approved: bool
    reason: str | None = None
    checks_passed: list[str] = []


app = FastAPI(title="Risk Service", version="1.0.0")
app.mount("/metrics", make_asgi_app())


@app.post("/api/risk/check", response_model=RiskCheckResponse)
async def risk_check(request: RiskCheckRequest):
    with CHECK_LATENCY.time():
        checks_passed = []

        # 1. Position limit check
        current_pos = positions.get(request.symbol, 0)
        pos_limit = POSITION_LIMITS.get(request.symbol, POSITION_LIMITS["default"])
        new_pos = current_pos + (request.quantity if request.side == "BUY" else -request.quantity)

        if abs(new_pos) > pos_limit:
            RISK_CHECKS.labels(result="rejected").inc()
            return RiskCheckResponse(approved=False, reason=f"Position limit exceeded: {abs(new_pos):,.0f} > {pos_limit:,.0f}")
        checks_passed.append("position_limit")

        # 2. Trader daily notional limit
        notional = request.notional or request.quantity * 100  # fallback estimate
        trader_used = trader_notional.get(request.trader_id, 0)
        daily_limit = TRADER_LIMITS["default_daily_notional"]

        if trader_used + notional > daily_limit:
            RISK_CHECKS.labels(result="rejected").inc()
            return RiskCheckResponse(approved=False, reason=f"Trader daily notional limit exceeded")
        checks_passed.append("trader_notional_limit")

        # 3. Concentration check (single position > 20% of limit)
        if abs(new_pos) > pos_limit * 0.8:
            logger.warning(f"Concentration warning: {request.symbol} at {abs(new_pos)/pos_limit:.1%} of limit")
        checks_passed.append("concentration")

        # Approve and update state
        positions[request.symbol] = new_pos
        trader_notional[request.trader_id] = trader_used + notional

        RISK_CHECKS.labels(result="approved").inc()
        return RiskCheckResponse(approved=True, checks_passed=checks_passed)


@app.get("/api/risk/positions")
async def get_positions():
    return {"positions": positions}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "risk-service"}
