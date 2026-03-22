"""
Google News RSS integration for stock news headlines.
In-memory cache with 1-hour TTL.
"""

import logging
import time
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

_news_cache: dict[str, tuple[list[dict], float]] = {}
_NEWS_TTL = 3600  # 1 hour

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def fetch_news(symbol: str, max_items: int = 5) -> list[dict]:
    sym = symbol.upper()

    if sym in _news_cache:
        articles, expires = _news_cache[sym]
        if time.time() < expires:
            return articles

    query = f"{sym} NSE stock"
    try:
        resp = httpx.get(
            GOOGLE_NEWS_RSS,
            params={"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            timeout=10.0,
            headers={"User-Agent": "FinSight/1.0"},
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        articles = []
        for item in items[:max_items]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source = item.findtext("source", "")
            articles.append({
                "title": title,
                "url": link,
                "published": pub_date,
                "source": source,
            })

        _news_cache[sym] = (articles, time.time() + _NEWS_TTL)
        return articles
    except Exception as e:
        logger.warning("News fetch failed for %s: %s", sym, e)
        return []
