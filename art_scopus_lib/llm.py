"""OpenAI interaction layer.

The pipeline only calls this module for model requests so prompt behavior and
response parsing are isolated in one place.
"""

import json
import random
import time

from openai import OpenAI

from .retry_utils import retry_on_exception


class AbstractLLMService:
    """Encapsulates all OpenAI calls used by this project."""

    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    @retry_on_exception(default_return="None")
    def extract_abstract_from_text(self, ocr_text: str) -> str:
        """Extract the abstract body from OCR text, or return 'None'."""
        system_message = (
            "You extract only the abstract body from scientific documents. "
            "If no clear abstract exists, return 'None'. "
            "Never return introduction text as abstract."
        )
        user_message = (
            "Text below is from the first two pages. "
            "Return only the pure abstract body with no heading/keywords. "
            "If uncertain, return 'None'.\n\n"
            f"{ocr_text}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        )

        # Brief jitter reduces bursty API traffic when workers finish together.
        time.sleep(random.uniform(0.5, 1.0))
        return response.choices[0].message.content.strip()

    @retry_on_exception(default_return={"confidence": "", "reason": ""})
    def verify_abstract(self, abstract: str, page_text: str) -> dict:
        """Score confidence that candidate text is a real abstract."""
        system_message = (
            "You evaluate if candidate text is an abstract of a paper. "
            "Respond in JSON only: {\"confidence\":\"95%\",\"reason\":\"...\"}. "
            "If candidate resembles introduction/body text, lower confidence."
        )
        user_message = (
            f"[Candidate Abstract]\n{abstract}\n\n"
            f"[First 1-2 Page Text]\n{page_text}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        )
        time.sleep(random.uniform(0.5, 1.0))

        # Model output is expected JSON, but this fallback keeps logs useful
        # when the model returns plain text unexpectedly.
        raw_text = response.choices[0].message.content
        try:
            parsed = json.loads(raw_text)
            return {
                "confidence": parsed.get("confidence", ""),
                "reason": parsed.get("reason", ""),
            }
        except Exception:
            return {"confidence": "", "reason": raw_text}
