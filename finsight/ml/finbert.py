"""
FinBERT singleton — loads ProsusAI/finbert ONCE per process.
Eliminates repeated ~500MB model downloads/loads.

Usage:
    from finsight.ml.finbert import get_finbert, analyze_batch
"""
import re

import torch

_tokenizer = None
_model = None
_device = None


def get_finbert():
    """
    Singleton FinBERT loader. Returns (tokenizer, model, device).
    First call loads the model (~500MB). Subsequent calls return cached refs.
    """
    global _tokenizer, _model, _device
    if _tokenizer is not None:
        return _tokenizer, _model, _device

    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    name = "ProsusAI/finbert"
    _tokenizer = AutoTokenizer.from_pretrained(name)
    _model = AutoModelForSequenceClassification.from_pretrained(name)
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model.to(_device)
    _model.eval()
    return _tokenizer, _model, _device


def analyze_batch(
    sentences: list[str],
    batch_size: int = 32,
) -> list[dict]:
    """
    Batch FinBERT inference with dynamic padding.

    Args:
        sentences: List of text strings to analyze.
        batch_size: Number of sentences per batch (32 optimal for CPU).

    Returns:
        List of dicts with 'positive', 'negative', 'neutral' float scores.
    """
    tokenizer, model, device = get_finbert()
    results = []

    for i in range(0, len(sentences), batch_size):
        batch = sentences[i : i + batch_size]
        inputs = tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,  # Dynamic padding to longest in batch
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)

        probs = torch.softmax(outputs.logits, dim=1)
        # FinBERT labels order: [positive, negative, neutral]
        for j in range(len(batch)):
            results.append({
                "positive": probs[j][0].item(),
                "negative": probs[j][1].item(),
                "neutral": probs[j][2].item(),
            })

    return results


def split_financial_sentences(text: str, min_length: int = 15) -> list[str]:
    """
    Split text into sentences suitable for FinBERT analysis.
    Handles financial abbreviations (Rs., Q3., FY25., vs.) better than
    naive [.!?] splitting.
    """
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if len(s.strip()) >= min_length]
