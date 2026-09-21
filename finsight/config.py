import os
from pathlib import Path

from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Load .env from project root (where you run uvicorn from)
load_dotenv(PROJECT_ROOT / ".env")

# Evaluation corpora live side by side: FINSIGHT_CORPUS=pdf → finsight_pdf.db + chroma_db_pdf/
_CORPUS = os.getenv("FINSIGHT_CORPUS", "").strip()
_SUFFIX = f"_{_CORPUS}" if _CORPUS else ""

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / f'finsight{_SUFFIX}.db').as_posix()}")

# JWT — no fallback: a known default key makes every token forgeable.
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY.startswith("change-me"):
    raise RuntimeError("SECRET_KEY is not set. Generate one with `openssl rand -hex 32` and put it in .env")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# CORS — comma-separated list of allowed frontend origins. Default is the Vite dev server.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

# Market data — "auto" uses Zerodha for users who linked a Kite account, else yfinance.
MARKET_DATA_PROVIDER = os.getenv("MARKET_DATA_PROVIDER", "auto")

# Zerodha Kite Connect (optional; paid API subscription + per-user OAuth)
ZERODHA_API_KEY = os.getenv("ZERODHA_API_KEY", "")
ZERODHA_API_SECRET = os.getenv("ZERODHA_API_SECRET", "")
# Must match the Redirect URL you set in Zerodha app (e.g. https://yourdomain.com/zerodha/callback)
ZERODHA_REDIRECT_URI = os.getenv("ZERODHA_REDIRECT_URI", "")

# LLM provider — "auto" picks Groq when GROQ_API_KEY is set, else Ollama.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto")

# Groq — hosted inference (free tier at https://console.groq.com). New projects block every
# model until an admin enables it at https://console.groq.com/settings/project/limits.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Cerebras — same open models, OpenAI-compatible; free tier 1M tokens/day (https://cloud.cerebras.ai)
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")

# Ollama — local inference
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
# Ollama's default context window (2048–4096) silently truncates RAG prompts
# (~4k tokens for 8 chunks) from the front, dropping the instructions.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
# Local reasoning models (qwen3, deepseek-r1) can take minutes on a 4k-token RAG prompt.
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "300"))

# SEC EDGAR downloads (sample corpus). SEC requires an identifying User-Agent with a contact email.
EDGAR_USER_AGENT = os.getenv("EDGAR_USER_AGENT", "FinSight research (set EDGAR_USER_AGENT)")

# Embeddings and reranker (local, via sentence-transformers)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
# v2-m3 (568M) discriminates within a document far better than -base, which mostly matched the
# chunk header; measured in eval/results/HISTORY.md. ~1 s for 20 candidates on Apple silicon.
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
# Where the embedder and reranker run: "auto" (MPS/CUDA when present) or "cpu" — set cpu to keep a
# background eval off the GPU while the machine is in use.
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "auto")

# ChromaDB
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(PROJECT_ROOT / f"chroma_db{_SUFFIX}"))
DOCUMENTS_DIR = PROJECT_ROOT / "documents"  # raw PDFs and extracted text

# Ingestion — legacy (used by old chunk_text)
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64

# RAG — page-aware chunking
RAG_CHUNK_SIZE = 1500
RAG_CHUNK_OVERLAP = 200

# CrediSentiment — section-aware chunking (larger than RAG for claim context)
CREDISENTIMENT_CHUNK_SIZE = int(os.getenv("CREDISENTIMENT_CHUNK_SIZE", "3500"))
CREDISENTIMENT_CHUNK_OVERLAP = int(os.getenv("CREDISENTIMENT_CHUNK_OVERLAP", "500"))

# FinBERT batch inference
FINBERT_BATCH_SIZE = int(os.getenv("FINBERT_BATCH_SIZE", "32"))
FINBERT_MAX_SENTENCES = int(os.getenv("FINBERT_MAX_SENTENCES", "500"))

# Walking the Talk — optimized pipeline settings
# WTT_MODEL overrides the provider default for claim extraction / verification only.
WTT_MODEL = os.getenv("WTT_MODEL", "")
WTT_MAX_CLAIMS_CHUNKS = int(os.getenv("WTT_MAX_CLAIMS_CHUNKS", "40"))
WTT_BATCH_SIZE = int(os.getenv("WTT_BATCH_SIZE", "5"))
WTT_PARALLEL = int(os.getenv("WTT_PARALLEL", "4"))
WTT_ACTUALS_TOP_K = int(os.getenv("WTT_ACTUALS_TOP_K", "3"))
# Stage 2 verifies at most this many extracted claims (processing-time cap; raise on hosted providers).
WTT_MAX_CLAIMS = int(os.getenv("WTT_MAX_CLAIMS", "35"))
