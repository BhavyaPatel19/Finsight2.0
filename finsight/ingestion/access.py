"""
Document visibility.

A document is visible to a user when they uploaded it (`user_id` matches)
or when it is part of the shared corpus (`user_id` is NULL — e.g. the
seeded sample filings). Every router that touches a document goes through
these two helpers, so the rule cannot drift between endpoints.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, or_, select

from finsight.models import Document, User


def visible_documents(session: Session, user: User, **filters) -> list[Document]:
    stmt = select(Document).where(or_(Document.user_id == user.id, Document.user_id.is_(None)))
    for field, value in filters.items():
        if value:
            stmt = stmt.where(getattr(Document, field) == value)
    stmt = stmt.order_by(Document.ingested_at.desc())
    return list(session.exec(stmt).all())


def get_accessible_document(session: Session, user: User, document_id: int) -> Document:
    """The document, or 404 — the same response whether it is missing or someone else's."""
    doc = session.get(Document, document_id)
    if not doc or (doc.user_id is not None and doc.user_id != user.id):
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def can_access(user: User, doc: Document) -> bool:
    return doc.user_id is None or doc.user_id == user.id
