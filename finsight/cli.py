"""
finsight — command line for the pipeline and the evaluation harness.

    finsight docs                                   list documents and index status
    finsight ingest FILE --symbol INFY --type concall --fy FY25 --quarter Q4
    finsight ask "What FY26 guidance was given in April 2025?" [--docs 1,2] [--top-k 8]
    finsight verify --claims 1 --actuals 5           Walk the Talk between two documents
    finsight sentiment DOC_ID                        FinBERT sentiment by division
    finsight seed [--format pdf] [--engine v2]       download + index the sample corpus
    finsight render-pdfs                             render the sample HTML filings to PDF
    finsight eval retrieval|generation|wtt [...]     evaluation harnesses (args passed through)

Documents created here belong to the shared corpus (visible to every user).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


def _session():
    from sqlmodel import Session

    from finsight.database.session import engine, init_db

    init_db()
    return Session(engine)


def cmd_docs(args) -> int:
    from sqlmodel import select

    from finsight.models import Document

    with _session() as s:
        docs = s.exec(select(Document).order_by(Document.id)).all()
        if not docs:
            print("no documents — try `finsight seed`")
            return 0
        print(f"{'id':>4}  {'symbol':8} {'type':14} {'period':9} {'status':10} {'chunks':>6}  file")
        for d in docs:
            period = " ".join(x for x in (d.fiscal_quarter, d.fiscal_year) if x)
            print(
                f"{d.id:>4}  {d.symbol:8} {d.doc_type:14} {period:9} {d.status:10} {d.chunk_count or 0:>6}  {Path(d.pdf_path or '').name}"
            )
            for w in json.loads(d.parse_health)["warnings"] if d.parse_health else []:
                print(f"      ! {w}")
    return 0


def cmd_ingest(args) -> int:
    from finsight.ingestion.service import register_document
    from finsight.retrieval import index_document

    path = Path(args.file).resolve()
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 2
    doc_type, fy, quarter = args.type, args.fy, args.quarter
    if not (doc_type and fy and quarter) and path.suffix.lower() == ".pdf":
        from finsight.corpus.detect import detect_metadata

        d = detect_metadata(path)
        doc_type = doc_type or d["doc_type"] or "quarterly"
        fy = fy or d["fiscal_year"]
        quarter = quarter or d["fiscal_quarter"]
        print(f"detected: {d['doc_type']} {d['fiscal_quarter']} {d['fiscal_year']} ({d['evidence']})", file=sys.stderr)
    with _session() as s:
        doc = register_document(
            s,
            symbol=args.symbol.upper(),
            doc_type=doc_type or "quarterly",
            fiscal_year=fy,
            fiscal_quarter=quarter,
            pdf_path=str(path),
        )
        result = index_document(s, doc.id, force=True)
    print(json.dumps(result, indent=1))
    return 0 if result.get("status") == "indexed" else 1


def cmd_detect(args) -> int:
    from finsight.corpus.detect import detect_metadata

    for f in args.files:
        d = detect_metadata(f)
        print(
            f"{Path(f).name:40s} {str(d['doc_type']):14s} {str(d['fiscal_quarter']):3s} {str(d['fiscal_year']):5s} {d['company_name'] or ''}"
        )
    return 0


def cmd_ask(args) -> int:
    from finsight.llm import LLMError
    from finsight.rag.service import answer_question

    doc_ids = [int(x) for x in args.docs.split(",")] if args.docs else None
    with _session() as s:
        try:
            r = answer_question(
                s, args.question, document_ids=doc_ids, top_k=args.top_k, model=args.model, retrieval_mode=args.mode
            )
        except LLMError as e:
            print(f"LLM unavailable: {e}", file=sys.stderr)
            return 1
    print(r["answer"])
    print(
        f"\n— {r['model_used']} · retrieval {r['usage']['retrieval_ms']} ms · generation {r['usage']['latency_ms']} ms"
    )
    for i, src in enumerate(r["sources"], 1):
        who = f" · {src.get('speaker')}" if src.get("speaker") else ""
        print(
            f"  [{i}] {src['doc_type']} {src.get('fiscal_quarter') or ''} {src.get('fiscal_year') or ''} p{src['page_number']}{who}: {src['snippet'][:90]!r}"
        )
    return 0


def cmd_verify(args) -> int:
    from finsight.verification import verify

    with _session() as s:
        result = asyncio.run(verify(s, args.claims, args.actuals, model=args.model))
        if result is None:
            print("nothing to verify — are both documents indexed?", file=sys.stderr)
            return 1
        rows = json.loads(result.claims_json or "[]")
        print(
            f"credibility score: {result.overall_score}/100 over {sum(1 for r in rows if r['verdict'] != 'UNVERIFIABLE')} verifiable claims "
            f"({sum(1 for r in rows if r['verdict'] == 'UNVERIFIABLE')} unverifiable)\n"
        )
        for r in rows:
            print(f"[{r['verdict']:12}] {r['claim']}")
            if r.get("actual_value"):
                print(
                    f"               actual: {r['actual_value']}  — {r.get('evidence_doc_type')} p{r.get('evidence_page')}: {(r.get('evidence_quote') or '')[:100]!r}"
                )
            elif r.get("explanation"):
                print(f"               {r['explanation'][:120]}")
        print(f"\n{result.narrative_summary}")
    return 0


def cmd_sentiment(args) -> int:
    from finsight.credisentiment.service import analyze_division_sentiment

    with _session() as s:
        rows = analyze_division_sentiment(s, args.doc_id)
        if not rows:
            print("no result — is the document indexed?", file=sys.stderr)
            return 1
        print(f"{'division':40} {'n':>5} {'pos':>6} {'neg':>6} {'net':>7}")
        for r in sorted(rows, key=lambda r: -r.sentence_count):
            print(
                f"{r.division_name[:40]:40} {r.sentence_count:>5} {r.positive_score:6.3f} {r.negative_score:6.3f} {r.overall_score:+7.3f}"
            )
    return 0


def cmd_seed(args) -> int:
    sys.argv = ["seed_demo"] + args.rest
    from scripts.seed_demo import main

    main()
    return 0


def cmd_render(args) -> int:
    from scripts.render_pdfs import main

    main()
    return 0


def cmd_eval(args) -> int:
    import runpy

    module = {"retrieval": "eval.retrieval", "generation": "eval.generation", "wtt": "eval.wtt"}[args.suite]
    sys.argv = [module] + args.rest
    runpy.run_module(module, run_name="__main__")
    return 0


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY") or "cli-local")
    ap = argparse.ArgumentParser(
        prog="finsight", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("docs", help="list documents").set_defaults(fn=cmd_docs)

    p = sub.add_parser("ingest", help="register and index a filing")
    p.add_argument("file")
    p.add_argument("--symbol", required=True)
    p.add_argument(
        "--type", default=None, help="concall | press_release | fact_sheet | annual_report (detected if omitted)"
    )
    p.add_argument("--fy", default=None, help="e.g. FY26 (detected if omitted)")
    p.add_argument("--quarter", default=None, help="e.g. Q4 (detected if omitted)")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("detect", help="guess document type, period and company from the first pages")
    p.add_argument("files", nargs="+")
    p.set_defaults(fn=cmd_detect)

    p = sub.add_parser("ask", help="answer a question with citations")
    p.add_argument("question")
    p.add_argument("--docs", default="", help="comma-separated document ids (default: all)")
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--model", default=None)
    p.add_argument("--mode", default="v2", help="retrieval mode (v2, hybrid_rerank, …)")
    p.set_defaults(fn=cmd_ask)

    p = sub.add_parser("verify", help="Walk the Talk: claims document vs actuals document")
    p.add_argument("--claims", type=int, required=True)
    p.add_argument("--actuals", type=int, required=True)
    p.add_argument("--model", default=None)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("sentiment", help="FinBERT sentiment by division")
    p.add_argument("doc_id", type=int)
    p.set_defaults(fn=cmd_sentiment)

    p = sub.add_parser("seed", help="download + index the sample corpus (args passed to scripts.seed_demo)")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_seed)

    sub.add_parser("render-pdfs", help="render the sample HTML filings to PDF").set_defaults(fn=cmd_render)

    p = sub.add_parser("eval", help="run an evaluation harness")
    p.add_argument("suite", choices=["retrieval", "generation", "wtt"])
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_eval)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
