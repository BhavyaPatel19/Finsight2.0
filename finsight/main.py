from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finsight.database.session import init_db
from finsight.ingestion.scheduler import start_scheduler
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    from finsight.ingestion.scheduler import get_scheduler
    s = get_scheduler()
    if s.running:
        s.shutdown(wait=False)


app = FastAPI(title="FinSight", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
