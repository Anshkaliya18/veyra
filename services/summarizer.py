from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Callable, Optional

from dotenv import load_dotenv
from openai import OpenAI



load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openai/gpt-oss-20b:free"
)

MAX_DOCUMENT_CHARS = 45000

TEMPERATURE = 0.2

MAX_RETRIES = 3

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# ---------------------------------------------------------
# Prompt
# ---------------------------------------------------------

SYSTEM_PROMPT = """
You are Veyra AI.

Your job is to understand any uploaded document.

Rules:

- Return ONLY valid JSON.
- Never return markdown.
- Never use ```json.
- Never explain your answer.
- Never hallucinate.
- If something is missing use:
  "" for strings
  [] for arrays
  0 for numbers

Return exactly this JSON structure.

{
    "document": {
        "title": "",
        "document_type": "",
        "category": "",
        "language": "",
        "summary": "",
        "purpose": "",
        "confidence": 0
    },

    "entities": {
        "people": [],
        "organizations": [],
        "locations": [],
        "emails": [],
        "phones": [],
        "websites": []
    },

    "content": {
        "keywords": [],
        "topics": [],
        "skills": [],
        "technologies": [],
        "important_points": [],
        "timeline": []
    },

    "search": {
        "one_line": "",
        "embedding_text": ""
    }
}
"""

# ---------------------------------------------------------
# Progress helper
# ---------------------------------------------------------

StatusCallback = Optional[
    Callable[..., None]
]


def update_status(
    callback: StatusCallback,
    stage: str,
    progress: int
):
    """
    Send progress updates to upload.py
    """

    if callback is None:
        return

    try:
        callback(
            stage=stage,
            progress=progress
        )
    except Exception:
        logger.exception("Status callback failed")

import re


def prepare_document(text: str) -> str:
    """
    Clean extracted document text before sending to AI.
    """

    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\t", " ")
    text = text.replace("\x00", "")

    text = re.sub(r"[\x01-\x08\x0B\x0C\x0E-\x1F]", "", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def parse_json(text: str) -> dict:
    """
    Parse AI JSON safely.
    """

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON found.")

    return json.loads(text[start : end + 1])

# ---------------------------------------------------------
# Response cleanup
# ---------------------------------------------------------

def remove_markdown(text: str) -> str:

    text = text.strip()

    text = re.sub(
        r"^```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```",
        "",
        text
    )

    text = re.sub(
        r"```$",
        "",
        text
    )

    return text.strip()


# ---------------------------------------------------------
# OpenRouter request
# ---------------------------------------------------------

def ask_ai(document: str) -> str:

    response = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": document,
            },
        ],
    )

    return response.choices[0].message.content.strip()


# ---------------------------------------------------------
# Main function
# ---------------------------------------------------------

def summarize_document(
    document_text: str,
    status_callback: StatusCallback = None,
) -> dict:

    if not document_text or not document_text.strip():
        return {
            "success": False,
            "error": "Document text is empty."
        }

    update_status(
        status_callback,
        "Cleaning Text",
        72,
    )

    cleaned_document = prepare_document(document_text)

    update_status(
        status_callback,
        "Preparing AI",
        76,
    )

    if len(cleaned_document) > MAX_DOCUMENT_CHARS:
        cleaned_document = cleaned_document[:MAX_DOCUMENT_CHARS]

    last_error = None

    for attempt in range(MAX_RETRIES):

        try:

            update_status(
                status_callback,
                "Sending to AI",
                80,
            )

            raw_response = ask_ai(cleaned_document)

            update_status(
                status_callback,
                "Waiting for AI",
                90,
            )

            raw_response = remove_markdown(raw_response)

            update_status(
                status_callback,
                "Parsing JSON",
                94,
            )

            try:
                data = parse_json(raw_response)

            except Exception:

                logger.warning(
                    "Attempt %d returned invalid JSON",
                    attempt + 1
                )

                last_error = "Invalid JSON returned by AI."

                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                    continue

                return {
                    "success": False,
                    "error": last_error,
                    "raw": raw_response,
                }

            update_status(
                status_callback,
                "Validating Summary",
                97,
            )

            # -------------------------------------------------
            # Ensure required top-level sections exist
            # -------------------------------------------------

            data.setdefault("document", {})
            data.setdefault("entities", {})
            data.setdefault("content", {})
            data.setdefault("search", {})

            document = data["document"]
            entities = data["entities"]
            content = data["content"]
            search = data["search"]

            # -------------------------------------------------
            # Document defaults
            # -------------------------------------------------

            document.setdefault("title", "")
            document.setdefault("document_type", "")
            document.setdefault("category", "")
            document.setdefault("language", "")
            document.setdefault("summary", "")
            document.setdefault("purpose", "")
            document.setdefault("confidence", 0)

            # -------------------------------------------------
            # Entity defaults
            # -------------------------------------------------

            for key in (
                "people",
                "organizations",
                "locations",
                "emails",
                "phones",
                "websites",
            ):
                entities.setdefault(key, [])

            # -------------------------------------------------
            # Content defaults
            # -------------------------------------------------

            for key in (
                "keywords",
                "topics",
                "skills",
                "technologies",
                "important_points",
                "timeline",
            ):
                content.setdefault(key, [])

            # -------------------------------------------------
            # Search defaults
            # -------------------------------------------------

            search.setdefault("one_line", "")

            if not search.get("embedding_text"):
                search["embedding_text"] = cleaned_document[:3000]

            # -------------------------------------------------
            # Clean list values
            # -------------------------------------------------

            def clean_list(values):

                if not isinstance(values, list):
                    return []

                cleaned = []

                for item in values:

                    if item is None:
                        continue

                    item = str(item).strip()

                    if not item:
                        continue

                    if item not in cleaned:
                        cleaned.append(item)

                return cleaned

            for section in (entities, content):
                for key, value in section.items():
                    if isinstance(value, list):
                        section[key] = clean_list(value)

            # -------------------------------------------------
            # Normalize confidence
            # -------------------------------------------------

            try:
                confidence = float(document["confidence"])
            except Exception:
                confidence = 0.0

            confidence = max(0.0, min(confidence, 1.0))

            document["confidence"] = confidence

            update_status(
                status_callback,
                "Summary Complete",
                100,
            )

            return {
                "success": True,
                "data": data,
            }

        except Exception as e:

            logger.exception(
                "OpenRouter request failed "
                "(attempt %d/%d)",
                attempt + 1,
                MAX_RETRIES,
            )

            last_error = str(e)

            if attempt < MAX_RETRIES - 1:

                update_status(
                    status_callback,
                    "Retrying AI",
                    82,
                )

                time.sleep(2)
                continue

    update_status(
        status_callback,
        "Failed",
        100,
    )

    return {
        "success": False,
        "error": last_error or "Unknown AI error."
    }