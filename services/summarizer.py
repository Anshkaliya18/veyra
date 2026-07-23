import os
import json
import logging

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are Veyra AI, an advanced document understanding engine.

Your task is to analyze the uploaded document and extract only the important information.

Rules:
- Return ONLY valid JSON.
- Do NOT return markdown.
- Do NOT wrap the response in ```json.
- Keep all text concise.
- Summary must be between 50-100 words.
- Remove duplicate information.
- Do not hallucinate or invent facts.
- If information is missing, use "" for strings and [] for arrays.
- Preserve original names, titles, and organizations.

Extract and summarize the document into the following JSON schema:

{
  "document": {
    "title": "",
    "type": "",
    "category": "",
    "language": "",
    "summary": "",
    "purpose": "",
    "confidence": 0.0
  },

  "key_information": {
    "skills": [],
    "technologies": [],
    "projects": [],
    "certifications": [],
    "internships": [],
    "companies": [],
    "organizations": [],
    "education": [],
    "people": [],
    "achievements": []
  },

  "metadata": {
    "dates": [],
    "emails": [],
    "phones": [],
    "websites": [],
    "github": [],
    "keywords": []
  },

  "search_summary": {
    "one_line": "",
    "important_points": [
      "",
      "",
      "",
      "",
      ""
    ]
  }
}
"""

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY").strip()
)

def summarize_document(document_text: str) -> dict:
    """
    Analyze extracted document text using OpenRouter AI.

    Returns:
    {
        "success": True,
        "data": {...}
    }

    or

    {
        "success": False,
        "error": "..."
    }
    """

    if not document_text or not document_text.strip():
        return {
            "success": False,
            "error": "Document text is empty."
        }

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b:free",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": document_text[:50000]
                }
            ]
        )

        raw = response.choices[0].message.content.strip()

        try:
            data = json.loads(raw)

            return {
                "success": True,
                "data": data
            }

        except json.JSONDecodeError:

            logger.exception("AI returned invalid JSON")

            return {
                "success": False,
                "error": "Invalid JSON returned by AI.",
                "raw": raw
            }

    except Exception as e:

        logger.exception("OpenRouter request failed")

        return {
            "success": False,
            "error": str(e)
        }