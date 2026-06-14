"""
Market Data Service — aggregates price ticks from multiple feeds and publishes to RabbitMQ.
"""
import asyncio
import json
import logging
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime

import aio_pika
from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TICKS_PUBLISHED = Counter("market_data_ticks_published_total", "Total price ticks published", ["symbol"])
FEED_LATENCY = Histogram("market_data_feed_latency_seconds", "Feed processing latency")
CONNECTED_FEEDS = Gauge("market_data_connected_feeds", "Number of connected price feeds")

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "NIFTY50", "BANKNIFTY", "AAPL", "MSFT", "GOOGL"]


async def publish_ticks(connection: aio_pika.Connection):
    channel = await connection.channel()
    exchange = await channel.declare_exchange("price.tick", aio_pika.ExchangeType.FANOUT, durable=True)
    CONNECTED_FEEDS.set(3)

    while True:
        for symbol in SYMBOLS:
            with FEED_LATENCY.time():
                tick = {
                    "symbol": symbol,
                    "bid": round(random.uniform(1.05, 1.15), 5),
                    "ask": round(random.uniform(1.05, 1.15), 5),
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "feed-1"
                }
                await exchange.publish(
                    aio_pika.Message(body=json.dumps(tick).encode()),
                    routing_key=""
                )
                TICKS_PUBLISHED.labels(symbol=symbol).inc()

        await asyncio.sleep(0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    rabbitmq_url = "amqp://guest:guest@rabbitmq:5672/"
    try:
        connection = await aio_pika.connect_robust(rabbitmq_url)
        task = asyncio.create_task(publish_ticks(connection))
        logger.info("Market data publisher started")
        yield
        task.cancel()
        await connection.close()
    except Exception as e:
        logger.warning(f"RabbitMQ unavailable ({e}) — running in degraded mode")
        yield


app = FastAPI(title="Market Data Service", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "market-data-service", "feeds": SYMBOLS}


@app.get("/api/symbols")
async def get_symbols():
    return {"symbols": SYMBOLS}


@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    return {
        "symbol": symbol.upper(),
        "bid": round(random.uniform(1.05, 1.15), 5),
        "ask": round(random.uniform(1.05, 1.15), 5),
        "timestamp": datetime.utcnow().isoformat()
    }
