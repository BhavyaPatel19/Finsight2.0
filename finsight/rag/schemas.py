from pydantic import BaseModel


class PrepareRequest(BaseModel):
    document_ids: list[int]


class RAGQueryRequest(BaseModel):
    question: str
    document_ids: list[int] | None = None  # filter to specific docs
    symbol: str | None = None
    period: str | None = None
    top_k: int = 8
    model: str | None = None  # "deepseek-r1:14b" or "llama3.1:8b"


class NavigationStep(BaseModel):
    section: str | None = None
    sub_section: str | None = None
    page_number: int = 0
    snippet: str = ""


class RAGSource(BaseModel):
    symbol: str | None = None
    doc_type: str | None = None
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    document_id: int | None = None
    chunk_index: int | None = None
    page_number: int | str | None = None
    section: str | None = None
    sub_section: str | None = None
    snippet: str | None = None


class RAGQueryResponse(BaseModel):
    answer: str
    thinking: str | None = None
    navigations: list[NavigationStep] = []
    sources: list[RAGSource] = []
    model_used: str = ""


class PrepareResponse(BaseModel):
    results: list[dict] = []


class AvailableDocument(BaseModel):
    id: int
    symbol: str
    doc_type: str
    company_name: str | None = None
    fiscal_quarter: str | None = None
    fiscal_year: str | None = None
    status: str = "pending"
    chunk_count: int = 0
    file_size: int | None = None


class EvaluateRequest(BaseModel):
    questions: list[str]
    document_ids: list[int] | None = None
    top_k: int = 8
    model: str | None = None


class EvaluateResponse(BaseModel):
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    per_question: list[dict] = []
    error: str | None = None
