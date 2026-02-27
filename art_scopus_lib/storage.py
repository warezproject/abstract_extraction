"""Filesystem and CSV/JSON storage helpers.

This module keeps data loading/saving logic separated from runtime control
and API interaction logic.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


# Unified output schema used by CSV logs and cached extraction payloads.
LOG_FIELDS = [
    "file",
    "google_text",
    "gpt_abstract",
    "scopus_abstract",
    "char_similarity",
    "word_precision",
    "word_recall",
    "word_f1",
    "confidence",
    "reason",
    "is_substring",
    "ocr_status",
    "gpt_status",
]


def list_local_pdfs(pdf_dir: Path) -> list[Path]:
    """Return all PDF files sorted by filename for deterministic processing."""
    return sorted(pdf_dir.glob("*.pdf"), key=lambda p: p.name)


def load_scopus_abstracts(csv_path: Path) -> dict[str, str]:
    """Load Scopus abstract lookup table keyed by PDF filename."""
    df = pd.read_csv(csv_path)

    if "art_id" not in df.columns:
        raise ValueError("CSV must include 'art_id' column")

    abstract_map: dict[str, str] = {}
    for _, row in df.iterrows():
        filename = str(row["art_id"]).strip()
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        abstract_map[filename] = str(row.get("abstr", "")).strip()

    return abstract_map


def save_ocr_text(file_id: str, ocr_text: str, ocr_dir: Path) -> None:
    """Write OCR text cache for a single file."""
    payload = {"ocr_text": ocr_text}
    path = ocr_dir / f"{file_id}.json"
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def load_ocr_text(file_id: str, ocr_dir: Path) -> str | None:
    """Load OCR cache for a file if present."""
    path = ocr_dir / f"{file_id}.json"
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    return payload.get("ocr_text")


def save_ext_log(file_id: str, result: dict, ext_dir: Path) -> None:
    """Save extraction payload for a file into EXT cache."""
    to_save = dict(result)
    to_save.pop("status", None)

    path = ext_dir / f"{file_id}.json"
    with path.open("w", encoding="utf-8") as fp:
        json.dump(to_save, fp, ensure_ascii=False, indent=2)


def load_ext_log(file_id: str, ext_dir: Path) -> dict | None:
    """Load extraction cache for a file if present."""
    path = ext_dir / f"{file_id}.json"
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    payload.pop("status", None)
    return payload


def save_csv_log(entries: list[dict], log_dir: Path) -> Path:
    """Write batch results as a timestamped CSV and return the output path."""
    timestamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"abstract_extraction_{timestamp}.csv"

    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(entries)

    return path
