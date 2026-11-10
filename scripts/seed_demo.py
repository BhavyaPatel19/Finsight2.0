"""
Seed the sample corpus: download the public filings listed in
eval/gold/documents.json, register them, and index them for RAG.

    python -m scripts.seed_demo            # download + register + index
    python -m scripts.seed_demo --no-index # download + register only
    python -m scripts.seed_demo --wtt      # also build Walk-the-Talk chunks

Idempotent: existing files are kept when their SHA-256 matches, and
documents are matched on source_url.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from pathlib import Path

import httpx
from sqlmodel import Session, select

from finsight import config
from finsight.models import Document

logger = logging.getLogger("seed")

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "eval" / "gold" / "documents.json"
# SEC's fair-access policy requires a User-Agent with an app name and a
# contact email, and ≤10 requests/second. Set EDGAR_USER_AGENT in .env, e.g.
#   EDGAR_USER_AGENT="FinSight research you@example.com"
EDGAR_HEADERS = {"User-Agent": config.EDGAR_USER_AGENT}


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    return json.loads(path.read_text())["documents"]


def _is_edgar(url: str) -> bool:
    return "sec.gov" in url


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def local_file(entry: dict, dest_dir: Path, fmt: str) -> Path:
    """HTML as downloaded, or the locally rendered PDF (scripts/render_pdfs.py); a manifest entry
    that is itself a PDF (a company's own IR download) is used as is."""
    if fmt == "pdf" and not entry["file"].lower().endswith(".pdf"):
        return dest_dir / "pdf" / (Path(entry["file"]).stem + ".pdf")
    return dest_dir / entry["file"]


def download(entry: dict, dest_dir: Path, client: httpx.Client) -> Path:
    dest = dest_dir / entry["file"]
    if dest.exists() and entry.get("sha256") and sha256(dest) == entry["sha256"]:
        logger.info("cached   %s", dest.name)
        return dest
    if _is_edgar(entry["url"]):
        if "@" not in config.EDGAR_USER_AGENT:
            raise SystemExit(
                "EDGAR_USER_AGENT must include a contact email (SEC fair-access policy). "
                'Add e.g. EDGAR_USER_AGENT="FinSight research you@example.com" to .env'
            )
        headers = EDGAR_HEADERS
    else:
        headers = {"User-Agent": "Mozilla/5.0 (FinSight research; public investor-relations documents)"}
    r = client.get(entry["url"], headers=headers, timeout=120.0, follow_redirects=True)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    digest = sha256(dest)
    if entry.get("sha256") and digest != entry["sha256"]:
        logger.warning("sha256 mismatch for %s (manifest %s, got %s)", dest.name, entry["sha256"][:12], digest[:12])
    logger.info("fetched  %s (%d KB, sha256 %s)", dest.name, len(r.content) // 1024, digest[:12])
    time.sleep(0.25)
    return dest


def register(session: Session, entry: dict, path: Path) -> Document:
    doc = session.exec(select(Document).where(Document.source_url == entry["url"])).first()
    if doc is None:  # ingested by hand (`finsight ingest`) before the manifest existed
        doc = session.exec(select(Document).where(Document.pdf_path == str(path))).first()
    if doc:
        if doc.pdf_path != str(path) or doc.source_url != entry["url"]:
            doc.pdf_path = str(path)
            doc.source_url = entry["url"]
            session.add(doc)
            session.commit()
        return doc
    doc = Document(
        symbol=entry["symbol"],
        company_name=entry.get("company_name"),
        doc_type=entry["doc_type"],
        fiscal_year=entry.get("fiscal_year"),
        fiscal_quarter=entry.get("fiscal_quarter"),
        source_url=entry["url"],
        pdf_path=str(path),
        file_size=path.stat().st_size,
        status="pending",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def seed(
    session: Session,
    *,
    index: bool = True,
    wtt: bool = False,
    reindex: bool = False,
    dest_dir: Path | None = None,
    fmt: str = "html",
    engine: str = "v1",
    manifest: Path = MANIFEST,
) -> dict[str, Document]:
    """Download + register (+ index) every manifest entry. Returns {key: Document}."""
    dest_dir = dest_dir or Path(config.DOCUMENTS_DIR)
    entries = load_manifest(manifest)
    docs: dict[str, Document] = {}
    with httpx.Client() as client:
        for entry in entries:
            download(entry, dest_dir, client)
            path = local_file(entry, dest_dir, fmt)
            if not path.exists():
                raise SystemExit(f"{path} missing — run `python -m scripts.render_pdfs` first")
            docs[entry["key"]] = register(session, entry, path)

    if index:
        from finsight.rag.service import _process_for_rag_v1 as process_for_rag
        from finsight.retrieval import index_document

        for key, doc in docs.items():
            if doc.status == "indexed" and not reindex:
                logger.info("indexed  %s (already)", key)
                continue
            if reindex:
                doc.status = "pending"
                session.add(doc)
                session.commit()
            t0 = time.time()
            result = index_document(session, doc.id, force=True) if engine == "v2" else process_for_rag(session, doc.id)
            logger.info(
                "indexed  %s -> %s in %.1fs",
                key,
                {k: v for k, v in result.items() if k != "document_id"},
                time.time() - t0,
            )
    if wtt:
        from finsight.credisentiment.pipeline import process_for_credisentiment

        for key, doc in docs.items():
            session.refresh(doc)
            if doc.cs_status == "indexed":
                continue
            process_for_credisentiment(session, doc.id)
            logger.info("wtt      %s", key)
    return docs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-index", action="store_true", help="download and register only")
    ap.add_argument("--wtt", action="store_true", help="also build Walk-the-Talk chunks")
    ap.add_argument("--reindex", action="store_true", help="re-chunk and re-embed documents that are already indexed")
    ap.add_argument(
        "--format",
        choices=["html", "pdf"],
        default="html",
        help="register the HTML exhibits or the locally rendered PDFs",
    )
    ap.add_argument(
        "--engine",
        choices=["v1", "v2"],
        default="v1",
        help="indexing pipeline (v2 = finsight.corpus + finsight.retrieval)",
    )
    ap.add_argument("--write-hashes", action="store_true", help="record SHA-256 of downloaded files into the manifest")
    ap.add_argument(
        "--manifest", type=Path, default=MANIFEST, help="document manifest (default: the Infosys EDGAR sample corpus)"
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from finsight.database.session import engine, init_db

    init_db()
    with Session(engine) as session:
        docs = seed(
            session,
            index=not args.no_index,
            wtt=args.wtt,
            reindex=args.reindex,
            fmt=args.format,
            engine=args.engine,
            manifest=args.manifest,
        )
        paths = {key: Path(doc.pdf_path) for key, doc in docs.items()}

    if args.write_hashes:
        manifest = json.loads(args.manifest.read_text())
        by_key = {d["key"]: d for d in manifest["documents"]}
        for key, path in paths.items():
            by_key[key]["sha256"] = sha256(path)
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
        logger.info("wrote hashes to %s", args.manifest.resolve().relative_to(ROOT))


if __name__ == "__main__":
    main()
