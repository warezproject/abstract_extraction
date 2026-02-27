"""Runtime configuration model.

This module centralizes path and credential handling so the rest of the code
can assume validated configuration.
"""

from dataclasses import dataclass
from pathlib import Path
import os

DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"


@dataclass
class AppConfig:
    """Holds runtime paths and credentials for a single execution."""

    pdf_dir: Path
    ext_dir: Path
    ocr_dir: Path
    log_dir: Path
    scopus_csv_path: Path
    openai_model: str = DEFAULT_MODEL
    google_credentials: str | None = None
    openai_api_key: str | None = None

    @classmethod
    def from_args(cls, args) -> "AppConfig":
        """Build AppConfig from CLI args and environment variables.

        Precedence rule for Google credentials:
        1) --google-credentials argument
        2) GOOGLE_APPLICATION_CREDENTIALS environment variable
        """
        google_credentials = (
            str(args.google_credentials)
            if args.google_credentials
            else os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
        openai_api_key = os.getenv("OPENAI_API_KEY")

        return cls(
            pdf_dir=args.pdf_dir,
            ext_dir=args.ext_dir,
            ocr_dir=args.ocr_dir,
            log_dir=args.log_dir,
            scopus_csv_path=args.scopus_csv,
            openai_model=args.model,
            google_credentials=google_credentials,
            openai_api_key=openai_api_key,
        )

    def ensure_directories(self) -> None:
        """Create output/cache directories if they do not exist."""
        self.ext_dir.mkdir(parents=True, exist_ok=True)
        self.ocr_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def apply_runtime_environment(self) -> None:
        """Set credential path for the Google Vision SDK at runtime."""
        if self.google_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.google_credentials

    def validate(self) -> None:
        """Raise ValueError if required inputs or credentials are missing."""
        problems: list[str] = []

        if not self.pdf_dir.exists():
            problems.append(f"PDF directory not found: {self.pdf_dir}")
        if not self.scopus_csv_path.exists():
            problems.append(f"Scopus CSV not found: {self.scopus_csv_path}")
        if not self.openai_api_key:
            problems.append("Environment variable OPENAI_API_KEY is required.")
        if not self.google_credentials:
            problems.append(
                "Google credentials are required. Set GOOGLE_APPLICATION_CREDENTIALS "
                "or pass --google-credentials."
            )

        if problems:
            joined = "\n- ".join([""] + problems)
            raise ValueError(f"Configuration error:{joined}")
