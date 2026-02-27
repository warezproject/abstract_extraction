"""Parallel processing pipeline for PDF extraction jobs."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .config import AppConfig
from .llm import AbstractLLMService
from .metrics import (
    character_similarity,
    is_exact_substring_relaxed,
    word_metrics,
)
from .ocr import pdf_to_text_google_ocr
from .storage import load_ext_log, save_ext_log


def _failed_result(file_stem: str, scopus_abstract: str = "") -> dict:
    """Return a consistent failure payload for downstream logging."""
    return {
        "file": file_stem,
        "google_text": "",
        "gpt_abstract": "None",
        "scopus_abstract": scopus_abstract,
        "char_similarity": 0.0,
        "word_precision": 0.0,
        "word_recall": 0.0,
        "word_f1": 0.0,
        "confidence": "",
        "reason": "",
        "is_substring": 0,
        "ocr_status": "exception",
        "gpt_status": "exception",
    }


def process_pdf(
    idx: int,
    total: int,
    pdf_path: Path,
    abstract_map: dict[str, str],
    config: AppConfig,
    llm_service: AbstractLLMService,
    pages: tuple[int, int] = (0, 1),
    dpi: int = 250,
) -> dict:
    """Process one PDF and return extraction/evaluation payload."""
    basename = pdf_path.name
    file_stem = pdf_path.stem

    try:
        logging.info("[%s/%s] Processing %s", idx + 1, total, basename)

        # Extraction cache prevents repeated LLM calls on reruns.
        cached_result = load_ext_log(file_stem, config.ext_dir)
        if cached_result is not None:
            cached_result.setdefault("file", file_stem)
            cached_result["status"] = "cached"
            return cached_result

        ocr_text = pdf_to_text_google_ocr(
            pdf_path=pdf_path,
            ocr_dir=config.ocr_dir,
            pages=pages,
            dpi=dpi,
        )
        ocr_status = "success" if ocr_text else "fail"

        abstract = llm_service.extract_abstract_from_text(ocr_text) if ocr_text else "None"
        gpt_status = "success" if abstract and abstract.strip().lower() != "none" else "fail"

        verification = (
            llm_service.verify_abstract(abstract, ocr_text)
            if ocr_text and gpt_status == "success"
            else {"confidence": "", "reason": ""}
        )

        scopus_abstract = abstract_map.get(basename, "")
        char_sim = character_similarity(abstract, scopus_abstract)
        word_precision, word_recall, word_f1 = word_metrics(abstract, scopus_abstract)

        result = {
            "file": file_stem,
            "google_text": ocr_text,
            "gpt_abstract": abstract,
            "scopus_abstract": scopus_abstract,
            "char_similarity": round(char_sim, 4),
            "word_precision": round(word_precision, 4),
            "word_recall": round(word_recall, 4),
            "word_f1": round(word_f1, 4),
            "confidence": verification.get("confidence", ""),
            "reason": verification.get("reason", ""),
            "is_substring": int(is_exact_substring_relaxed(abstract, ocr_text)),
            "ocr_status": ocr_status,
            "gpt_status": gpt_status,
        }

        save_ext_log(file_stem, result, config.ext_dir)
        return result

    except Exception as exc:
        logging.error("Failed processing %s: %s", pdf_path, exc)
        return _failed_result(file_stem, abstract_map.get(basename, ""))


def run_batch(
    selected_pdfs: list[Path],
    abstract_map: dict[str, str],
    config: AppConfig,
    llm_service: AbstractLLMService,
    max_workers: int,
    pages: tuple[int, int] = (0, 1),
    dpi: int = 250,
    results_sink: list[dict] | None = None,
    on_progress=None,
) -> list[dict]:
    """Run PDF processing in parallel and append results as tasks complete."""
    total = len(selected_pdfs)
    results = results_sink if results_sink is not None else []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                process_pdf,
                idx,
                total,
                pdf,
                abstract_map,
                config,
                llm_service,
                pages,
                dpi,
            ): (idx, pdf)
            for idx, pdf in enumerate(selected_pdfs)
        }

        for future in as_completed(future_map):
            idx, pdf = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                logging.error("Unexpected worker failure for %s: %s", pdf, exc)
                result = _failed_result(pdf.stem, abstract_map.get(pdf.name, ""))

            # `status` is internal-only metadata; keep output schema stable.
            result.pop("status", None)
            results.append(result)

            if on_progress is not None:
                on_progress(idx, total, result)

    return results
