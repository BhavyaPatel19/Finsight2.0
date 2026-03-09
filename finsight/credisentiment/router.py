import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select

from finsight.config import DOCUMENTS_DIR
from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.models import User, Document
from finsight.credisentiment.schemas import (
    AnalyzeSentimentRequest,
    AnalyzeSentimentResponse,
    DivisionSentimentItem,
    WalkTheTalkRequest,
    WalkTheTalkResponse,
    ClaimComparison,
    AvailableDocumentResponse,
)
from finsight.credisentiment.service import (
    analyze_division_sentiment,
    walk_the_talk,
)

router = APIRouter()


# ── Document listing (same as RAG) ─────────────────────

@router.get("/available-documents", response_model=list[AvailableDocumentResponse])
def get_available_documents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return all documents for the document picker."""
    stmt = select(Document).order_by(Document.ingested_at.desc())
    docs = list(session.exec(stmt).all())
    return [
        AvailableDocumentResponse(
            id=d.id,
            symbol=d.symbol,
            doc_type=d.doc_type,
            company_name=d.company_name,
            fiscal_quarter=d.fiscal_quarter,
            fiscal_year=d.fiscal_year,
            status=d.status,
            chunk_count=d.chunk_count or 0,
            file_size=d.file_size,
        )
        for d in docs
    ]


# ── Upload ─────────────────────────────────────────────

@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    symbol: str = Form(...),
    doc_type: str = Form("annual_report"),
    fiscal_quarter: str = Form(None),
    fiscal_year: str = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF document for analysis."""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = DOCUMENTS_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = Document(
        symbol=symbol.upper(),
        doc_type=doc_type,
        fiscal_quarter=fiscal_quarter,
        fiscal_year=fiscal_year,
        pdf_path=str(dest),
        status="pending",
        file_size=dest.stat().st_size,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    return {"id": doc.id, "status": "uploaded", "symbol": doc.symbol}


# ── Feature 1: Division-level FinBERT ──────────────────

@router.post("/analyze-sentiment", response_model=list[AnalyzeSentimentResponse])
def analyze_sentiment(
    payload: AnalyzeSentimentRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Run division-level FinBERT sentiment analysis on selected documents.
    Auto-indexes documents for RAG if not already done.
    """
    results = []
    for doc_id in payload.document_ids:
        doc = session.get(Document, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        divisions = analyze_division_sentiment(session, doc_id)
        if not divisions:
            results.append(
                AnalyzeSentimentResponse(
                    document_id=doc_id,
                    symbol=doc.symbol,
                    divisions=[],
                    computed_at=doc.ingested_at,
                )
            )
            continue

        results.append(
            AnalyzeSentimentResponse(
                document_id=doc_id,
                symbol=doc.symbol,
                divisions=[
                    DivisionSentimentItem(
                        division_name=d.division_name,
                        positive_score=d.positive_score,
                        negative_score=d.negative_score,
                        neutral_score=d.neutral_score,
                        overall_score=d.overall_score,
                        sentence_count=d.sentence_count,
                    )
                    for d in divisions
                ],
                computed_at=divisions[0].computed_at if divisions else doc.ingested_at,
            )
        )

    return results


# ── Feature 2: Walking the Talk ────────────────────────

@router.post("/walk-the-talk", response_model=WalkTheTalkResponse)
def walk_the_talk_endpoint(
    payload: WalkTheTalkRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Compare management claims from one document against actual results
    in another using DeepSeek R1 LLM.
    """
    import json

    result = walk_the_talk(
        session,
        payload.claims_document_id,
        payload.actuals_document_id,
    )
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not analyze documents. Ensure both exist and have text content.",
        )

    # Parse claims JSON
    try:
        claims_data = json.loads(result.claims_json) if result.claims_json else []
    except json.JSONDecodeError:
        claims_data = []

    return WalkTheTalkResponse(
        claims_document_id=result.claims_document_id,
        actuals_document_id=result.actuals_document_id,
        symbol=result.symbol,
        overall_score=result.overall_score,
        claims=[
            ClaimComparison(
                claim=c.get("claim", ""),
                category=c.get("category", "other"),
                claimed_value=c.get("claimed_value"),
                actual_value=c.get("actual_value"),
                met=c.get("met"),
                explanation=c.get("explanation"),
            )
            for c in claims_data
        ],
        narrative_summary=result.narrative_summary or "",
        computed_at=result.computed_at,
    )
