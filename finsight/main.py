import logging
import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finsight.config import ALLOWED_ORIGINS
from finsight.database.session import init_db
from finsight.auth.router import router as auth_router
from finsight.zerodha.router import router as zerodha_router
from finsight.portfolio.router import router as portfolio_router
from finsight.ingestion.router import router as ingestion_router
from finsight.rag.router import router as rag_router
from finsight.sentiment.router import router as sentiment_router
from finsight.credibility.router import router as credibility_router
from finsight.market.router import router as market_router
from finsight.scraper.router import router as scraper_router
from finsight.credisentiment.router import router as credisentiment_router
from finsight.watchlist.router import router as watchlist_router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_migrations():
    """Apply any missing columns to the SQLite DB at startup (idempotent)."""
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./finsight.db")
    # Strip the sqlite:/// prefix to get the filesystem path
    db_path = db_path.replace("sqlite:///", "")
    migrations = [
        "ALTER TABLE documents ADD COLUMN cs_status TEXT DEFAULT 'pending'",
        "ALTER TABLE documents ADD COLUMN cs_chunk_count INTEGER DEFAULT 0",
        "ALTER TABLE documents ADD COLUMN cs_error_message TEXT",
        "ALTER TABLE user ADD COLUMN first_name TEXT DEFAULT ''",
        "ALTER TABLE user ADD COLUMN last_name TEXT DEFAULT ''",
    ]
    try:
        conn = sqlite3.connect(db_path)
        for sql in migrations:
            try:
                conn.execute(sql)
                conn.commit()
                logger.info("migration applied: %s", sql)
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    pass  # column already exists, skip
                else:
                    raise
        conn.close()
    except Exception:
        logger.exception("migration failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    init_db()
    yield


app = FastAPI(title="FinSight", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(zerodha_router, prefix="/zerodha", tags=["zerodha"])
app.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
app.include_router(ingestion_router, prefix="/ingestion", tags=["ingestion"])
app.include_router(rag_router, prefix="/rag", tags=["rag"])
app.include_router(sentiment_router, prefix="/sentiment", tags=["sentiment"])
app.include_router(credibility_router, prefix="/credibility", tags=["credibility"])
app.include_router(market_router, prefix="/market", tags=["market"])
app.include_router(scraper_router, prefix="/scraper", tags=["scraper"])
app.include_router(credisentiment_router, prefix="/credisentiment", tags=["credisentiment"])
app.include_router(watchlist_router, prefix="/watchlist", tags=["watchlist"])
