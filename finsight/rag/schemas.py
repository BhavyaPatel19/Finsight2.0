from pydantic import BaseModel


class RAGQueryRequest(BaseModel):
    question: str
    symbol: str | None = None
    period: str | None = None
    top_k: int = 8


class RAGSource(BaseModel):
    symbol: str | None = None
    doc_type: str | None = None
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    document_id: int | None = None
    chunk_index: int | None = None
    snippet: str | None = None


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[RAGSource]
