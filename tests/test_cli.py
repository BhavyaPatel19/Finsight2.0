"""CLI wiring (no models, no LLM): parser, docs listing, ingest error path."""

import io
from contextlib import redirect_stdout

import pytest

from finsight import cli


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("docs", "ingest", "ask", "verify", "sentiment", "seed", "eval"):
        assert cmd in out


def test_docs_on_empty_db(monkeypatch, tmp_path):
    from sqlalchemy.pool import StaticPool
    from sqlmodel import create_engine

    import finsight.database.session as db

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(db, "engine", engine)
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert cli.main(["docs"]) == 0
    assert "no documents" in buf.getvalue()


def test_ingest_missing_file(tmp_path):
    assert cli.main(["ingest", str(tmp_path / "nope.pdf"), "--symbol", "INFY"]) == 2
