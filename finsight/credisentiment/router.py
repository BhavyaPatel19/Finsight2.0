from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from finsight.credisentiment.schemas import (
    AnalyzeSentimentRequest,
    AnalyzeSentimentResponse,
    AvailableDocumentResponse,
    ClaimComparison,
    DivisionSentimentItem,
    ProcessResponse,
    WalkTheTalkRequest,
    WalkTheTalkResponse,
)
from finsight.credisentiment.service import (
    analyze_division_sentiment,
)
from finsight.database.session import get_session
from finsight.deps import get_current_user
from finsight.ingestion.access import get_accessible_document, visible_documents
from finsight.ingestion.uploads import save_upload
from finsight.models import Document, User

router = APIRouter()


# ── Document listing (same as RAG) ─────────────────────


@router.get("/available-documents", response_model=list[AvailableDocumentResponse])
def get_available_documents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Documents this user may analyse (own uploads + shared corpus)."""
    docs = visible_documents(session, current_user)
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
async def upload_document(
    file: UploadFile = File(...),
    symbol: str = Form(...),
    doc_type: str = Form("annual_report"),
    fiscal_quarter: str = Form(None),
    fiscal_year: str = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF/HTML/text filing for analysis."""
    dest = await save_upload(file, symbol=symbol, fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter)

    doc = Document(
        user_id=current_user.id,
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


# ── Processing pipeline ──────────────────────────────


@router.post("/process/{document_id}", response_model=ProcessResponse)
def process_for_credisentiment_endpoint(
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Index a document (one route for RAG, sentiment and Walk the Talk)."""
    doc = get_accessible_document(session, current_user, document_id)
    if not doc.pdf_path:
        raise HTTPException(status_code=400, detail="Document has no file")

    from finsight.retrieval import index_document

    result = index_document(session, document_id, force=True)
    session.refresh(doc)
    doc.cs_status = doc.status  # legacy flag the UI still reads
    session.add(doc)
    session.commit()

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Processing failed"))

    return result


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
        doc = get_accessible_document(session, current_user, doc_id)

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


@router.get("/wtt-documents", response_model=list[AvailableDocumentResponse])
def get_wtt_documents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Indexed documents this user may see, for the Walk-the-Talk picker."""
    docs = [d for d in visible_documents(session, current_user) if d.status == "indexed"]
    return [
        AvailableDocumentResponse(
            id=d.id,
            symbol=d.symbol,
            doc_type=d.doc_type,
            company_name=d.company_name,
            fiscal_quarter=d.fiscal_quarter,
            fiscal_year=d.fiscal_year,
            status=d.status or "pending",
            chunk_count=d.chunk_count or 0,
            file_size=d.file_size,
        )
        for d in docs
    ]


@router.post("/walk-the-talk", response_model=WalkTheTalkResponse)
async def walk_the_talk_endpoint(
    payload: WalkTheTalkRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Compare management claims from one document against actual results
    in another using DeepSeek R1 LLM (async two-stage pipeline).
    """
    import json

    from finsight.verification import verify

    for doc_id in (payload.claims_document_id, payload.actuals_document_id):
        doc = get_accessible_document(session, current_user, doc_id)
        if doc.status != "indexed":
            raise HTTPException(status_code=400, detail=f"Document {doc_id} is not indexed yet — process it first")
    result = await verify(session, payload.claims_document_id, payload.actuals_document_id)
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

    def _verdict_to_met(claim: dict) -> bool | None:
        """Convert LLM verdict string to boolean met field."""
        # Check explicit 'met' field first (legacy format)
        if "met" in claim and claim["met"] is not None:
            return bool(claim["met"])
        # Map verdict string from Stage 2 prompt
        verdict = str(claim.get("verdict", "")).upper().strip()
        if verdict == "MET":
            return True
        if verdict in ("MISSED", "NOT MET"):
            return False
        if verdict == "PARTIAL":
            return None  # Partial treated as unclear
        return None

    from finsight.config import WTT_MODEL

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
                met=_verdict_to_met(c),
                explanation=c.get("explanation"),
                verdict=(str(c["verdict"]).upper() if c.get("verdict") else None),
                quote=c.get("quote"),
                speaker=c.get("speaker"),
                page=c.get("page"),
                period=c.get("period"),
                metric=c.get("metric"),
                evidence_quote=c.get("evidence_quote"),
                evidence_doc_type=c.get("evidence_doc_type"),
                evidence_page=c.get("evidence_page"),
                confidence=c.get("confidence"),
                confidence_reasons=list(c.get("confidence_reasons") or []),
                method=c.get("method"),
            )
            for c in claims_data
        ],
        narrative_summary=result.narrative_summary or "",
        model_used=WTT_MODEL,
        computed_at=result.computed_at,
    )
