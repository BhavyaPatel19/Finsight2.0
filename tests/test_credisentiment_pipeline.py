"""Tests for CrediSentiment processing pipeline (vectorstore + chunking + orchestrator)."""

import pytest
from unittest.mock import patch, MagicMock

from finsight.models import Document, ComparisonChunk


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------

class TestChunkForCredisentiment:
    """Tests for chunk_for_credisentiment()."""

    def test_chunk_size_and_overlap(self):
        """A 7000-char input produces 2+ chunks, each <= 4000 chars."""
        from finsight.credisentiment.pipeline import chunk_for_credisentiment

        text = "A" * 7000
        pages = [{"page": 1, "text": text, "section": "Overview", "sub_section": None}]
        chunks = chunk_for_credisentiment(pages)

        assert len(chunks) >= 2, f"Expected 2+ chunks, got {len(chunks)}"
        for c in chunks:
            assert len(c["text"]) <= 4000, (
                f"Chunk {c['chunk_index']} is {len(c['text'])} chars (max 4000)"
            )

    def test_section_boundary_chunking(self):
        """Section change with buffer > 30% of chunk_size triggers flush."""
        from finsight.credisentiment.pipeline import chunk_for_credisentiment

        pages = [
            {"page": 1, "text": "X" * 1200, "section": "Section A", "sub_section": None},
            {"page": 2, "text": "Y" * 1200, "section": "Section B", "sub_section": None},
        ]
        chunks = chunk_for_credisentiment(pages)

        assert len(chunks) >= 2, "Section boundary should cause flush"
        # First chunk should be from Section A
        assert chunks[0]["section"] == "Section A"
        # Second chunk should be from Section B
        assert chunks[1]["section"] == "Section B"

    def test_no_toc_fallback(self):
        """When all pages have section=None, size-based flushing still works."""
        from finsight.credisentiment.pipeline import chunk_for_credisentiment

        text = "B" * 8000
        pages = [{"page": 1, "text": text, "section": None, "sub_section": None}]
        chunks = chunk_for_credisentiment(pages)

        assert len(chunks) >= 2, "Size-based flush should still produce multiple chunks"
        for c in chunks:
            assert len(c["text"]) <= 4000

    def test_overlap_present(self):
        """End of chunk N overlaps with start of chunk N+1 by ~500 chars."""
        from finsight.credisentiment.pipeline import chunk_for_credisentiment

        # Use distinct chars so we can verify overlap content
        text = "".join(chr(65 + (i % 26)) for i in range(8000))
        pages = [{"page": 1, "text": text, "section": None, "sub_section": None}]
        chunks = chunk_for_credisentiment(pages)

        assert len(chunks) >= 2, "Need 2+ chunks to test overlap"
        # The tail of chunk 0 should appear at the start of chunk 1
        tail_of_first = chunks[0]["text"][-400:]  # last 400 chars
        head_of_second = chunks[1]["text"][:600]  # first 600 chars
        assert tail_of_first in head_of_second, (
            "Overlap not found between consecutive chunks"
        )


# ---------------------------------------------------------------------------
# Vectorstore tests
# ---------------------------------------------------------------------------

class TestCredisentimentVectorstore:
    """Tests for credisentiment vectorstore module."""

    def test_separate_collection(self, tmp_chroma_dir):
        """get_collection() returns a collection named 'credisentiment_docs'."""
        from finsight.credisentiment.vectorstore import get_collection

        coll = get_collection()
        assert coll.name == "credisentiment_docs"


# ---------------------------------------------------------------------------
# Pipeline orchestrator tests
# ---------------------------------------------------------------------------

def _fake_structured_doc():
    """Return a fake extract_structured_document result with 2 pages."""
    return {
        "toc": [],
        "pages": [
            {
                "page": 1,
                "text": "Management discussed revenue growth of 15% " + ("detail " * 300),
                "section": "MD&A",
                "sub_section": None,
            },
            {
                "page": 2,
                "text": "Operating margins improved to 22% " + ("context " * 300),
                "section": "Financial Highlights",
                "sub_section": None,
            },
        ],
        "sections": [],
        "total_pages": 2,
    }


def _fake_embeddings(texts):
    """Return zero-vectors of dimension 768."""
    return [[0.0] * 768 for _ in texts]


class TestProcessForCredisentiment:
    """Tests for process_for_credisentiment() orchestrator."""

    @patch("finsight.credisentiment.pipeline.embed_documents", side_effect=_fake_embeddings)
    @patch("finsight.credisentiment.pipeline.extract_structured_document", return_value=_fake_structured_doc())
    def test_pipeline_independence(
        self, mock_extract, mock_embed, test_db_session, sample_document, tmp_chroma_dir
    ):
        """process_for_credisentiment sets cs_status='indexed' without touching status (RAG)."""
        from finsight.credisentiment.pipeline import process_for_credisentiment

        result = process_for_credisentiment(test_db_session, sample_document.id)

        assert result["status"] == "indexed"
        # Refresh doc from DB
        test_db_session.refresh(sample_document)
        assert sample_document.cs_status == "indexed"
        assert sample_document.status == "pending", "RAG status must not change"
        assert sample_document.cs_chunk_count > 0

    @patch("finsight.credisentiment.pipeline.embed_documents", side_effect=_fake_embeddings)
    @patch("finsight.credisentiment.pipeline.extract_structured_document", return_value=_fake_structured_doc())
    def test_process_guard(
        self, mock_extract, mock_embed, test_db_session, sample_document, tmp_chroma_dir
    ):
        """If cs_status is already 'indexed', return early with 'already_indexed'."""
        from finsight.credisentiment.pipeline import process_for_credisentiment

        sample_document.cs_status = "indexed"
        test_db_session.add(sample_document)
        test_db_session.commit()

        result = process_for_credisentiment(test_db_session, sample_document.id)
        assert result["status"] == "already_indexed"
        mock_extract.assert_not_called()

    def test_process_no_pdf(self, test_db_session, tmp_chroma_dir):
        """If doc.pdf_path is None, return error status."""
        from finsight.credisentiment.pipeline import process_for_credisentiment

        doc = Document(
            symbol="NOPDF", doc_type="annual_report",
            status="pending", cs_status="pending", pdf_path=None,
        )
        test_db_session.add(doc)
        test_db_session.commit()
        test_db_session.refresh(doc)

        result = process_for_credisentiment(test_db_session, doc.id)
        assert result["status"] == "error"
