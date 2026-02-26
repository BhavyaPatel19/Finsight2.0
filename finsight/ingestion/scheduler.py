from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Lazy singleton
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def scheduled_fetch_documents() -> None:
    """Placeholder: in production, fetch new PDFs from BSE/NSE/company IR and call ingestion."""
    pass


def scheduled_portfolio_snapshot() -> None:
    """Placeholder: for each user with Zerodha linked, save daily holdings snapshot."""
    pass


def start_scheduler() -> None:
    s = get_scheduler()
    s.add_job(scheduled_fetch_documents, IntervalTrigger(days=1), id="fetch_docs")
    s.add_job(scheduled_portfolio_snapshot, IntervalTrigger(days=1), id="portfolio_snapshot")
    if not s.running:
        s.start()
