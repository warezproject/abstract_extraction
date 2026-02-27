"""Command-line interface for the abstract extraction pipeline.

This module is intentionally focused on user interaction and runtime wiring:
- parse CLI options
- validate preconditions
- select target PDFs
- call the processing pipeline and save logs
"""

import argparse
import logging
import signal
from pathlib import Path

from .config import AppConfig, DEFAULT_MODEL


def parse_args(argv=None):
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract paper abstracts from PDFs using Google OCR + OpenAI."
    )

    parser.add_argument("--pdf-dir", type=Path, default=Path("PDF"), help="PDF input directory")
    parser.add_argument("--ext-dir", type=Path, default=Path("EXT_vision"), help="Extraction cache directory")
    parser.add_argument("--ocr-dir", type=Path, default=Path("OCR_vision"), help="OCR cache directory")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"), help="Output log directory")
    parser.add_argument(
        "--scopus-csv",
        type=Path,
        default=Path("scopus_eng_20250325.csv"),
        help="Scopus CSV file path",
    )

    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model name")
    parser.add_argument("--google-credentials", type=Path, default=None, help="Path to Google service-account JSON")
    parser.add_argument("--max-workers", type=int, default=6, help="Parallel worker count")
    parser.add_argument("--dpi", type=int, default=250, help="DPI for PDF page rendering")
    parser.add_argument("--page-start", type=int, default=0, help="Start page index (0-based)")
    parser.add_argument("--page-end", type=int, default=1, help="End page index (0-based)")

    # Only one target mode can be used at a time.
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file", help="Single file name to process (e.g., 12345.pdf)")
    group.add_argument("--count", type=int, help="Process first N files from sorted list")

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Use interactive selection mode when --file/--count is omitted",
    )

    args = parser.parse_args(argv)

    # Fast local validation prevents deeper runtime failures.
    if args.max_workers < 1:
        parser.error("--max-workers must be >= 1")
    if args.count is not None and args.count < 1:
        parser.error("--count must be >= 1")
    if args.page_start < 0 or args.page_end < args.page_start:
        parser.error("Page range is invalid. Use 0 <= page-start <= page-end.")

    return args


def _resolve_single_file(file_name: str, pdf_files: list[Path]) -> list[Path]:
    """Return an exact filename match (normalizing missing '.pdf' suffix)."""
    file_name = file_name if file_name.lower().endswith(".pdf") else f"{file_name}.pdf"
    return [pdf for pdf in pdf_files if pdf.name == file_name]


def _select_pdfs_interactive(pdf_files: list[Path]) -> list[Path]:
    """Ask the user which subset to process when interactive mode is enabled."""
    print("==== Execution Mode ====")
    print("1. Process one file")
    print("2. Process first N files")

    choice = input("Select mode (1 or 2): ").strip()

    if choice == "1":
        raw_name = input("Enter file name (e.g., 12345 or 12345.pdf): ").strip()
        selected = _resolve_single_file(raw_name, pdf_files)
        if not selected:
            print(f"File not found: {raw_name}")
        return selected

    if choice == "2":
        raw_count = input(f"Enter count (1 to {len(pdf_files)}): ").strip()
        if not raw_count.isdigit():
            print("Count must be a number.")
            return []
        count = int(raw_count)
        if count < 1 or count > len(pdf_files):
            print("Count out of range.")
            return []
        return pdf_files[:count]

    print("Invalid selection.")
    return []


def _select_target_pdfs(args, pdf_files: list[Path]) -> list[Path]:
    """Resolve selected PDF files from --file / --count / --interactive."""
    # Priority order is explicit mode first, interactive fallback second.
    if args.file:
        return _resolve_single_file(args.file, pdf_files)

    if args.count is not None:
        return pdf_files[: args.count]

    if args.interactive:
        return _select_pdfs_interactive(pdf_files)

    return []


def main(argv=None) -> int:
    """Run CLI workflow and return process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    args = parse_args(argv)
    config = AppConfig.from_args(args)

    # Keep heavy imports lazy-loaded so `--help` works before dependency setup.
    try:
        from .llm import AbstractLLMService
        from .pipeline import run_batch
        from .storage import list_local_pdfs, load_scopus_abstracts, save_csv_log
    except ImportError as exc:
        missing = getattr(exc, "name", "unknown dependency")
        logging.error(
            "Missing dependency '%s'. Run: pip install -r requirements.txt",
            missing,
        )
        return 1

    # Create output/cache folders before runtime begins.
    config.ensure_directories()

    try:
        config.validate()
    except ValueError as exc:
        logging.error("%s", exc)
        return 1

    # Apply GOOGLE_APPLICATION_CREDENTIALS for downstream SDK clients.
    config.apply_runtime_environment()

    pdf_files = list_local_pdfs(config.pdf_dir)
    if not pdf_files:
        logging.error("No PDF files found in %s", config.pdf_dir)
        return 1

    selected = _select_target_pdfs(args, pdf_files)
    if not selected:
        logging.error("No target PDF selected. Use --file, --count, or --interactive.")
        return 1

    abstract_map = load_scopus_abstracts(config.scopus_csv_path)
    llm_service = AbstractLLMService(api_key=config.openai_api_key, model=config.openai_model)

    # Results are collected in memory, then written once as a timestamped CSV.
    results: list[dict] = []

    def on_progress(idx: int, total: int, result: dict) -> None:
        print(f"===> [{idx + 1}/{total}] {result['file']} done")

    interrupted = {"value": False}

    def signal_handler(_sig, _frame):
        # Convert Ctrl+C into a controlled shutdown path.
        interrupted["value"] = True
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)

    try:
        run_batch(
            selected_pdfs=selected,
            abstract_map=abstract_map,
            config=config,
            llm_service=llm_service,
            max_workers=args.max_workers,
            pages=(args.page_start, args.page_end),
            dpi=args.dpi,
            results_sink=results,
            on_progress=on_progress,
        )
    except KeyboardInterrupt:
        logging.warning("Interrupted by user. Saving partial results.")
    finally:
        if results:
            out_path = save_csv_log(results, config.log_dir)
            logging.info("Saved log: %s", out_path)
        elif interrupted["value"]:
            logging.warning("Interrupted before any result was produced.")

    return 130 if interrupted["value"] else 0
