"""Market data provider layer. yfinance calls are stubbed; no network."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from finsight import config
from finsight.market.providers import MarketNotLinked, get_market_provider, market_status
from finsight.market.providers.yfinance_provider import YFinanceProvider, _from_yahoo, _to_yahoo
from finsight.market.providers.zerodha_provider import ZerodhaProvider
from finsight.models import User, ZerodhaSession

_BASES = {"INFY.NS": 100.0, "TCS.NS": 200.0}


def _ohlcv_frame(ticker: str, rows: int = 3) -> pd.DataFrame:
    """Frame shaped like yf.Ticker(t).history(): one row per session."""
    idx = pd.date_range("2026-09-15", periods=rows, freq="D", tz="Asia/Kolkata")
    base = _BASES.get(ticker, 300.0)
    data = {}
    for i, field in enumerate(["Open", "High", "Low", "Close", "Adj Close"]):
        data[field] = [base + r + i * 0.1 for r in range(rows)]
    data["Volume"] = [1000 + r for r in range(rows)]
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# Symbol mapping
# ---------------------------------------------------------------------------


def test_symbol_mapping():
    assert _to_yahoo("NSE:INFY") == "INFY.NS"
    assert _to_yahoo("infy") == "INFY.NS"
    assert _to_yahoo("INFY.BO") == "INFY.BO"
    assert _from_yahoo("INFY.NS") == "INFY"


# ---------------------------------------------------------------------------
# yfinance quotes
# ---------------------------------------------------------------------------


class TestYFinanceQuotes:
    def test_quote_shape_matches_kite_contract(self, monkeypatch):
        p = YFinanceProvider()
        monkeypatch.setattr(p, "_recent", _ohlcv_frame)
        q = p.get_quotes(["NSE:INFY", "NSE:TCS"])

        assert set(q) == {"NSE:INFY", "NSE:TCS"}
        infy = q["NSE:INFY"]
        assert set(infy) >= {"last_price", "volume", "ohlc", "timestamp"}
        assert set(infy["ohlc"]) == {"open", "high", "low", "close"}
        # last row: Open=102.0, High=102.1, Low=102.2, Close=102.3 ; previous Close=101.3
        assert infy["last_price"] == 102.3
        assert infy["ohlc"]["open"] == 102.0
        assert infy["ohlc"]["close"] == 101.3, "ohlc.close must be the previous session close"
        assert infy["volume"] == 1002
        assert q["NSE:TCS"]["last_price"] == 202.3

    def test_ltp_derived_from_quotes(self, monkeypatch):
        p = YFinanceProvider()
        monkeypatch.setattr(p, "_recent", _ohlcv_frame)
        assert p.get_ltp(["NSE:INFY"]) == {"INFY": 102.3}

    def test_quotes_cached_within_ttl(self, monkeypatch):
        p = YFinanceProvider()
        calls = {"n": 0}

        def recent(ticker):
            calls["n"] += 1
            return _ohlcv_frame(ticker)

        monkeypatch.setattr(p, "_recent", recent)
        p.get_quotes(["NSE:INFY"])
        p.get_quotes(["NSE:INFY"])
        assert calls["n"] == 1

    def test_fetch_failure_yields_empty(self, monkeypatch):
        p = YFinanceProvider()

        def boom(ticker):
            raise RuntimeError("rate limited")

        monkeypatch.setattr(p, "_recent", boom)
        assert p.get_quotes(["NSE:INFY"]) == {}

    def test_empty_symbols(self):
        assert YFinanceProvider().get_quotes([]) == {}


# ---------------------------------------------------------------------------
# yfinance history
# ---------------------------------------------------------------------------


class TestYFinanceHistory:
    def test_candles_shape_and_interval_mapping(self, monkeypatch):
        p = YFinanceProvider()
        seen = {}

        def hist(ticker, interval, start, end):
            seen.update(ticker=ticker, interval=interval, start=start, end=end)
            idx = pd.date_range("2026-09-01", periods=2, freq="D", tz="Asia/Kolkata")
            return pd.DataFrame(
                {"Open": [1.0, 2.0], "High": [1.5, 2.5], "Low": [0.5, 1.5], "Close": [1.2, 2.2], "Volume": [10, 20]},
                index=idx,
            )

        monkeypatch.setattr(p, "_history", hist)
        candles = p.get_history("INFY", interval="15minute", from_date="2026-09-01", to_date="2026-09-02")

        assert seen["ticker"] == "INFY.NS" and seen["interval"] == "15m"
        assert seen["end"] == datetime(2026, 9, 3)  # to_date is inclusive
        assert candles[0] == {
            "timestamp": "2026-09-01T00:00:00+05:30",
            "open": 1.0,
            "high": 1.5,
            "low": 0.5,
            "close": 1.2,
            "volume": 10,
        }

    def test_intraday_lookback_is_clamped(self, monkeypatch):
        p = YFinanceProvider()
        seen = {}

        def hist(ticker, interval, start, end):
            seen["start"] = start
            return pd.DataFrame()

        monkeypatch.setattr(p, "_history", hist)
        p.get_history("INFY", interval="minute", from_date="2020-01-01")
        # Yahoo only serves 1m candles for the last 7 days; we clamp rather than 4xx.
        assert seen["start"] > datetime.now() - timedelta(days=8)

    def test_unknown_interval_falls_back_to_daily(self, monkeypatch):
        p = YFinanceProvider()
        seen = {}
        monkeypatch.setattr(p, "_history", lambda t, i, s, e: seen.update(i=i) or pd.DataFrame())
        p.get_history("INFY", interval="bogus")
        assert seen["i"] == "1d"


# ---------------------------------------------------------------------------
# Instrument search (bundled NIFTY 500 → Yahoo search fallback)
# ---------------------------------------------------------------------------


class TestSearch:
    def test_bundled_list_exact_then_prefix_then_name(self, monkeypatch):
        p = YFinanceProvider()
        monkeypatch.setattr(p, "_yahoo_search", lambda q, n: [])
        res = p.search_instruments("INFY")
        assert res[0]["symbol"] == "INFY"
        assert res[0]["name"].upper().startswith("INFOSYS")
        assert res[0]["exchange"] == "NSE" and res[0]["instrument_type"] == "EQ"

        res = p.search_instruments("tata")
        assert len(res) >= 5 and all("TATA" in (r["symbol"] + r["name"]).upper() for r in res)

    def test_yahoo_fallback_for_unknown_names(self, monkeypatch):
        p = YFinanceProvider()
        monkeypatch.setattr(
            p,
            "_yahoo_search",
            lambda q, n: [
                {"symbol": "ZZZ.NS", "shortname": "Zzz Ltd", "quoteType": "EQUITY"},
                {"symbol": "ZZZ", "shortname": "Zzz ADR", "quoteType": "EQUITY", "exchange": "NYQ"},
                {"symbol": "ZZZ.BO", "shortname": "Zzz BSE", "quoteType": "EQUITY"},
            ],
        )
        res = p.search_instruments("zzz nonexistent")
        assert [r["symbol"] for r in res] == ["ZZZ"]
        assert res[0]["name"] == "Zzz Ltd"

    def test_empty_query(self):
        assert YFinanceProvider().search_instruments("   ") == []


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


@pytest.fixture()
def user(test_db_session):
    u = User(first_name="A", last_name="B", email="a@b.c", hashed_password="x")
    test_db_session.add(u)
    test_db_session.commit()
    test_db_session.refresh(u)
    return u


class TestSelection:
    def test_auto_without_zerodha_credentials_is_yfinance(self, test_db_session, user, monkeypatch):
        monkeypatch.setattr(config, "MARKET_DATA_PROVIDER", "auto")
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "")
        assert isinstance(get_market_provider(test_db_session, user.id), YFinanceProvider)

    def test_auto_with_credentials_but_no_link_is_yfinance(self, test_db_session, user, monkeypatch):
        monkeypatch.setattr(config, "MARKET_DATA_PROVIDER", "auto")
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "k")
        monkeypatch.setattr(config, "ZERODHA_API_SECRET", "s")
        assert isinstance(get_market_provider(test_db_session, user.id), YFinanceProvider)

    def test_auto_with_link_is_zerodha(self, test_db_session, user, monkeypatch):
        monkeypatch.setattr(config, "MARKET_DATA_PROVIDER", "auto")
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "k")
        monkeypatch.setattr(config, "ZERODHA_API_SECRET", "s")
        test_db_session.add(ZerodhaSession(user_id=user.id, access_token="tok"))
        test_db_session.commit()
        p = get_market_provider(test_db_session, user.id)
        assert isinstance(p, ZerodhaProvider) and p.access_token == "tok" and p.live

    def test_forced_zerodha_without_link_raises(self, test_db_session, user, monkeypatch):
        monkeypatch.setattr(config, "MARKET_DATA_PROVIDER", "zerodha")
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "k")
        monkeypatch.setattr(config, "ZERODHA_API_SECRET", "s")
        with pytest.raises(MarketNotLinked):
            get_market_provider(test_db_session, user.id)

    def test_status_reports_everything(self, test_db_session, user, monkeypatch):
        monkeypatch.setattr(config, "MARKET_DATA_PROVIDER", "auto")
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "")
        assert market_status(test_db_session, user.id) == {
            "provider": "yfinance",
            "live": False,
            "zerodha_configured": False,
            "zerodha_linked": False,
        }


# ---------------------------------------------------------------------------
# API: the whole point — market endpoints work with no broker at all
# ---------------------------------------------------------------------------


class TestMarketApiWithoutZerodha:
    def test_search_works_unlinked(self, api_client, auth_headers, monkeypatch):
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "")
        monkeypatch.setattr(YFinanceProvider, "_yahoo_search", lambda self, q, n: [])
        r = api_client.get("/market/instruments/search", params={"q": "RELI"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["results"][0]["symbol"] == "RELIANCE"

    def test_quotes_work_unlinked(self, api_client, auth_headers, monkeypatch):
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "")
        monkeypatch.setattr(YFinanceProvider, "_recent", lambda self, ticker: _ohlcv_frame(ticker))
        r = api_client.get("/market/quotes", params={"symbols": "INFY"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["provider"] == "yfinance"
        assert r.json()["quotes"]["NSE:INFY"]["last_price"] == 102.3

    def test_status_endpoint(self, api_client, auth_headers, monkeypatch):
        monkeypatch.setattr(config, "ZERODHA_API_KEY", "")
        r = api_client.get("/market/status", headers=auth_headers)
        assert r.status_code == 200 and r.json()["provider"] == "yfinance"
