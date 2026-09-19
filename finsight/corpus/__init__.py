"""
Ingestion v2: filings → typed elements → lossless, structure-aware chunks.

    from finsight.corpus import parse_document, chunk_elements
    parsed = parse_document(path)          # ParsedDocument(elements, total_pages)
    chunks = chunk_elements(parsed.elements, header="Infosys Ltd (INFY) · earnings call transcript · Q4 FY25")
"""

from finsight.corpus.chunker import Chunk, chunk_elements
from finsight.corpus.elements import Element, ParsedDocument
from finsight.corpus.parse import parse_document

__all__ = ["Chunk", "Element", "ParsedDocument", "chunk_elements", "parse_document"]
