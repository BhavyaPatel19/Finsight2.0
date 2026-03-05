import os
from pathlib import Path

from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Load .env from project root (where you run uvicorn from)
load_dotenv(PROJECT_ROOT / ".env")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / 'finsight.db').as_posix()}")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-use-openssl-rand-hex-32")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Zerodha (set in env in production)
ZERODHA_API_KEY = os.getenv("ZERODHA_API_KEY", "")
ZERODHA_API_SECRET = os.getenv("ZERODHA_API_SECRET", "")
# Must match the Redirect URL you set in Zerodha app (e.g. https://yourdomain.com/zerodha/callback)
ZERODHA_REDIRECT_URI = os.getenv("ZERODHA_REDIRECT_URI", "")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_MODEL_PRIMARY = os.getenv("OLLAMA_MODEL_PRIMARY", "deepseek-r1:14b")
OLLAMA_MODEL_FAST = os.getenv("OLLAMA_MODEL_FAST", "llama3.1:8b-instruct-q8_0")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

# ChromaDB
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(PROJECT_ROOT / "chroma_db"))
DOCUMENTS_DIR = PROJECT_ROOT / "documents"  # raw PDFs and extracted text

# Ingestion — legacy (used by old chunk_text)
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64

# RAG — page-aware chunking
RAG_CHUNK_SIZE = 1500
RAG_CHUNK_OVERLAP = 200
