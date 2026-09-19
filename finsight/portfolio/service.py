from sqlmodel import Session

from finsight.zerodha.service import get_holdings


def get_holdings_with_metrics(session: Session, user_id: int) -> list[dict]:
    """Holdings with market data from Zerodha (day change, P&L, close price)."""
    holdings_list = get_holdings(session, user_id)
    out = []
    for h in holdings_list:
        out.append(
            {
                "symbol": h.symbol,
                "exchange": h.exchange,
                "quantity": h.quantity,
                "avg_price": h.avg_price,
                "current_price": h.current_price,
                "close_price": h.close_price,
                "pnl": h.pnl,
                "day_change": h.day_change,
                "day_change_pct": h.day_change_pct,
            }
        )
    return out


def get_portfolio_insights(session: Session, user_id: int) -> dict:
    """Compute portfolio credibility from live financial fundamentals (P/E, ROCE, D/E, etc.)."""
    import logging
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from finsight.credibility.fundamentals import fetch_and_score

    logger = logging.getLogger(__name__)

    holdings_list = get_holdings(session, user_id)
    if not holdings_list:
        return {
            "portfolio_credibility_score": None,
            "low_credibility_exposure_pct": None,
            "sentiment_weighted_exposure": None,
            "summary": "No holdings.",
        }

    total_value = sum((h.current_price or h.avg_price) * h.quantity for h in holdings_list)
    if total_value == 0:
        total_value = 1

    # Fetch scores in parallel with a short timeout per symbol
    results = {}

    def _fetch(symbol):
        try:
            return symbol, fetch_and_score(symbol)
        except Exception as e:
            logger.warning("Could not score %s: %s", symbol, e)
            return symbol, {"symbol": symbol, "score": None}

    symbols = [h.symbol for h in holdings_list]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_fetch, s): s for s in symbols}
        for future in as_completed(futures, timeout=20):
            try:
                sym, res = future.result()
                results[sym] = res
            except Exception:
                pass

    weighted_cred = 0.0
    low_cred_value = 0.0
    scored_count = 0

    for h in holdings_list:
        w = (h.current_price or h.avg_price) * h.quantity / total_value
        result = results.get(h.symbol, {})
        score = result.get("score")
        if score is not None:
            weighted_cred += w * score
            scored_count += 1
            if score < 50:
                low_cred_value += (h.current_price or h.avg_price) * h.quantity

    return {
        "portfolio_credibility_score": round(weighted_cred, 1) if scored_count > 0 else None,
        "low_credibility_exposure_pct": round((low_cred_value / total_value) * 100, 1) if total_value else None,
        "sentiment_weighted_exposure": None,
        "summary": f"Scored {scored_count}/{len(holdings_list)} holdings from live fundamentals.",
    }
