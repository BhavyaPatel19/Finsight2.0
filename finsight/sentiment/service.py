import re

import torch
from sqlmodel import Session, select

from finsight.ml.finbert import get_finbert
from finsight.models import Document, SentimentScore


def compute_sentiment_for_document(session: Session, document_id: int) -> SentimentScore | None:
    """Run FinBERT on document text, aggregate scores, save SentimentScore."""
    doc = session.get(Document, document_id)
    if not doc or not doc.text_path:
        return None
    with open(doc.text_path, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        return None

    try:
        tokenizer, model, device = get_finbert()
    except Exception:
        tokenizer, model, device = None, None, None
    if tokenizer is None or model is None:
        # Fallback: store a placeholder score
        score_row = SentimentScore(
            document_id=document_id,
            symbol=doc.symbol,
            fiscal_quarter=doc.fiscal_quarter,
            fiscal_year=doc.fiscal_year,
            overall_score=0.0,
        )
        session.add(score_row)
        session.commit()
        session.refresh(score_row)
        return score_row

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()][:500]
    if not sentences:
        sentences = [text[:512]]

    pos_sum, neg_sum, risk_count, n = 0.0, 0.0, 0, 0
    risk_words = {"risk", "debt", "loss", "decline", "uncertain", "volatility"}

    for sent in sentences:
        inputs = tokenizer(sent, return_tensors="pt", truncation=True, max_length=512).to(device)
        with torch.no_grad():
            out = model(**inputs)
        probs = torch.softmax(out.logits, dim=1)[0]
        # FinBERT labels: positive, negative, neutral
        pos_sum += probs[0].item()
        neg_sum += probs[1].item()
        n += 1
        if any(w in sent.lower() for w in risk_words) and probs[1].item() > 0.4:
            risk_count += 1

    overall = (pos_sum - neg_sum) / n if n else 0.0
    risk_tone = risk_count / n if n else 0.0
    optimism = pos_sum / n if n else 0.0

    score_row = SentimentScore(
        document_id=document_id,
        symbol=doc.symbol,
        fiscal_quarter=doc.fiscal_quarter,
        fiscal_year=doc.fiscal_year,
        overall_score=round(overall, 4),
        risk_tone_index=round(risk_tone, 4),
        optimism_index=round(optimism, 4),
    )
    session.add(score_row)
    session.commit()
    session.refresh(score_row)
    return score_row


def get_sentiment_history(session: Session, symbol: str) -> list[SentimentScore]:
    stmt = select(SentimentScore).where(SentimentScore.symbol == symbol).order_by(SentimentScore.computed_at.desc())
    return list(session.exec(stmt).all())
