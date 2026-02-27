"""Google Vision OCR helper functions."""

import io
import logging
import random
import time
from pathlib import Path

from google.cloud import vision
from pdf2image import convert_from_path

from .retry_utils import retry_on_exception
from .storage import load_ocr_text, save_ocr_text


@retry_on_exception(default_return="")
def pdf_to_text_google_ocr(
    pdf_path: Path,
    ocr_dir: Path,
    pages: tuple[int, int] = (0, 1),
    dpi: int = 250,
) -> str:
    """Run OCR on selected pages using Google Vision with disk caching."""
    file_id = pdf_path.stem

    # OCR cache prevents repeated billing/calls when rerunning experiments.
    cached = load_ocr_text(file_id, ocr_dir)
    if cached is not None:
        logging.info("Loaded OCR cache: %s.json", file_id)
        return cached

    vision_client = vision.ImageAnnotatorClient()
    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        first_page=pages[0] + 1,
        last_page=pages[1] + 1,
    )

    full_text = ""
    for page_idx, image_pil in enumerate(images, start=pages[0] + 1):
        buffer = io.BytesIO()
        image_pil.save(buffer, format="JPEG")

        image = vision.Image(content=buffer.getvalue())
        context = vision.ImageContext(language_hints=["en"])
        response = vision_client.text_detection(image=image, image_context=context)

        if response.text_annotations:
            full_text += response.text_annotations[0].description + "\n"

        logging.info("OCR complete: %s page=%s", pdf_path.name, page_idx)

        # Small random delay helps avoid synchronized bursts under parallel load.
        time.sleep(random.uniform(0.5, 1.0))

    save_ocr_text(file_id, full_text, ocr_dir)
    return full_text
