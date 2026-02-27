"""Utility metrics used for extraction quality comparison."""

import difflib
import re


def character_similarity(a: str, b: str) -> float:
    """Compute character-level similarity ratio between two strings."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def tokenize(text: str) -> set[str]:
    """Normalize to lowercase alphanumeric tokens and return unique words."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return set(text.split())


def word_metrics(pred: str, gold: str) -> tuple[float, float, float]:
    """Return precision, recall and F1 on unique token overlap."""
    pred_tokens = tokenize(pred)
    gold_tokens = tokenize(gold)

    if not pred_tokens or not gold_tokens:
        return (0.0, 0.0, 0.0)

    overlap = len(pred_tokens & gold_tokens)
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)

    if precision + recall == 0:
        return (0.0, 0.0, 0.0)

    f1 = 2 * precision * recall / (precision + recall)
    return (precision, recall, f1)


def normalize_spaces(text: str) -> str:
    """Collapse repeated whitespace for robust text matching."""
    return re.sub(r"\s+", " ", (text or "").strip())


def is_exact_substring_relaxed(extracted_abstract: str, original_text: str) -> bool:
    """Check if normalized extracted text appears in normalized OCR text."""
    if not extracted_abstract or extracted_abstract.strip().lower() == "none":
        return False

    extracted = normalize_spaces(extracted_abstract)
    original = normalize_spaces(original_text)
    return extracted in original
