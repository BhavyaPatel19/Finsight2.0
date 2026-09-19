from datetime import datetime

from pydantic import BaseModel

# ── Feature 1: Division-level FinBERT ──────────────────


class AnalyzeSentimentRequest(BaseModel):
    document_ids: list[int]


class DivisionSentimentItem(BaseModel):
    division_name: str
    positive_score: float
    negative_score: float
    neutral_score: float
    overall_score: float
    sentence_count: int


class AnalyzeSentimentResponse(BaseModel):
    document_id: int
    symbol: str
    divisions: list[DivisionSentimentItem]
    computed_at: datetime

    class Config:
        from_attributes = True


# ── Feature 2: Walking the Talk ────────────────────────


class WalkTheTalkRequest(BaseModel):
    claims_document_id: int
    actuals_document_id: int


class ClaimComparison(BaseModel):
    claim: str
    category: str
    claimed_value: str | None = None
    actual_value: str | None = None
    met: bool | None = None  # True = met, False = missed, None = unclear
    explanation: str | None = None


class WalkTheTalkResponse(BaseModel):
    claims_document_id: int
    actuals_document_id: int
    symbol: str
    overall_score: float  # 0-100
    claims: list[ClaimComparison]
    narrative_summary: str
    model_used: str = ""
    computed_at: datetime

    class Config:
        from_attributes = True


# ── Document listing (shared with RAG) ─────────────────


class AvailableDocumentResponse(BaseModel):
    id: int
    symbol: str
    doc_type: str
    company_name: str | None = None
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    status: str
    chunk_count: int = 0
    file_size: int | None = None

    class Config:
        from_attributes = True


# ── Processing pipeline response ─────────────────────


class ProcessResponse(BaseModel):
    status: str  # "indexed" | "already_indexed" | "error"
    document_id: int
    chunks: int = 0
    message: str | None = None
