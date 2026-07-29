# services/search.py
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from openai import OpenAI

from services.db import get_db_connection, release_db_connection

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
TEMPERATURE = float(os.getenv("SEARCH_TEMPERATURE", "0.2"))

MAX_CANDIDATE_DOCS = int(os.getenv("SEARCH_MAX_CANDIDATE_DOCS", "100"))
MAX_CONTEXT_DOCS = int(os.getenv("SEARCH_MAX_CONTEXT_DOCS", "5"))
MAX_CONTEXT_CHARS = int(os.getenv("SEARCH_MAX_CONTEXT_CHARS", "16000"))
MAX_EXCERPT_CHARS = int(os.getenv("SEARCH_MAX_EXCERPT_CHARS", "1600"))
MIN_RELEVANCE_SCORE = float(os.getenv("SEARCH_MIN_RELEVANCE_SCORE", "4.0"))

StatusCallback = Optional[Callable[..., None]]

if OPENROUTER_API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
else:
    client = None


class SearchError(Exception):
    pass


# ---------------------------------------------------------
# Progress helper
# ---------------------------------------------------------

def update_status(callback: StatusCallback, stage: str, progress: int) -> None:
    if callback is None:
        return

    try:
        callback(stage=stage, progress=progress)
    except Exception:
        logger.exception("Search status callback failed")


# ---------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------

def strip_markdown(text: str) -> str:
    text = (text or "").strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = strip_markdown(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in AI response.")

    return json.loads(cleaned[start : end + 1])


def safe_json_loads(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return value

    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        return value


# ---------------------------------------------------------
# Text helpers
# ---------------------------------------------------------

def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    return str(value)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9_+-]{1,}", text.lower())


def unique_list(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item is None:
            continue
        s = str(item).strip()
        if not s:
            continue
        if s not in out:
            out.append(s)
    return out


def join_nonempty(*parts: Any, sep: str = "\n") -> str:
    cleaned = []
    for part in parts:
        if part is None:
            continue
        text = normalize_text(part).strip()
        if text:
            cleaned.append(text)
    return sep.join(cleaned)


def truncate_text(text: str, limit: int) -> str:
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...[truncated]..."


def parse_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    return None

# ---------------------------------------------------------
# Query expansion
# ---------------------------------------------------------

SYNONYMS: dict[str, list[str]] = {
    "skills": [
        "skills",
        "technical skills",
        "technologies",
        "tools",
        "frameworks",
        "languages",
        "experience",
    ],
    "strongest": [
        "strongest",
        "best",
        "top",
        "main",
        "key",
        "important",
    ],
    "projects": [
        "projects",
        "project",
        "work",
        "portfolio",
    ],
    "internship": [
        "internship",
        "internships",
        "training",
        "experience",
        "work experience",
    ],
    "certificate": [
        "certificate",
        "certificates",
        "certification",
        "credential",
    ],
    "education": [
        "education",
        "college",
        "degree",
        "study",
        "school",
    ],
}

QUESTION_EXPANSIONS: dict[str, str] = {
    "what are my strongest skills": "skills technical skills technologies tools frameworks languages experience",
    "what are my best skills": "skills technical skills technologies tools frameworks languages experience",
    "show my strongest skills": "skills technical skills technologies tools frameworks languages experience",
    "what skills do i have": "skills technical skills technologies tools frameworks languages experience",
    "show my projects": "projects project work portfolio",
    "show my internships": "internship internship experience training work experience",
    "show my certificates": "certificate certification credential",
    "show my education": "education college degree school",
}


def expand_query(query: str) -> str:
    q = normalize_text(query).strip().lower()
    if not q:
        return ""

    expanded: list[str] = [q]

    for key, extra in QUESTION_EXPANSIONS.items():
        if key in q:
            expanded.append(extra)

    for token, synonyms in SYNONYMS.items():
        if token in q:
            expanded.extend(synonyms)

    return " ".join(unique_list(tokenize(" ".join(expanded))))
# ---------------------------------------------------------
# Data model
# ---------------------------------------------------------

@dataclass
class SearchDocument:
    file_id: int
    document_id: Optional[int]
    original_filename: str
    stored_filename: str
    file_url: str
    file_size: Optional[int]
    upload_status: str
    error_message: Optional[str]
    raw_text: str
    summary: str
    keywords: list[str]
    entities: dict[str, Any]
    metadata: dict[str, Any]
    language: str
    extraction_status: str
    summary_status: str
    file_created_at: Optional[str]
    file_updated_at: Optional[str]
    document_created_at: Optional[str]
    document_updated_at: Optional[str]
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------
# Database loading
# ---------------------------------------------------------

def fetch_user_documents(
    user_id: int,
    limit: int = MAX_CANDIDATE_DOCS,
) -> list[SearchDocument]:
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                uf.id AS file_id,
                d.id AS document_id,
                uf.original_filename,
                uf.stored_filename,
                uf.file_url,
                uf.file_size,
                uf.upload_status,
                uf.error_message,
                uf.created_at AS file_created_at,
                uf.updated_at AS file_updated_at,
                COALESCE(d.raw_text, '') AS raw_text,
                COALESCE(d.summary, '') AS summary,
                d.keywords,
                d.entities,
                d.metadata,
                COALESCE(d.language, '') AS language,
                COALESCE(d.extraction_status, '') AS extraction_status,
                COALESCE(d.summary_status, '') AS summary_status,
                d.created_at AS document_created_at,
                d.updated_at AS document_updated_at
            FROM uploaded_files uf
            LEFT JOIN documents d
                ON d.uploaded_file_id = uf.id
            WHERE uf.user_id = %s
            ORDER BY uf.id DESC
            LIMIT %s
            """,
            (user_id, limit),
        )

        rows = cur.fetchall()
        if not rows:
            return []

        docs: list[SearchDocument] = []

        for row in rows:
            (
                file_id,
                document_id,
                original_filename,
                stored_filename,
                file_url,
                file_size,
                upload_status,
                error_message,
                file_created_at,
                file_updated_at,
                raw_text,
                summary,
                keywords,
                entities,
                metadata,
                language,
                extraction_status,
                summary_status,
                document_created_at,
                document_updated_at,
            ) = row

            keywords_obj = safe_json_loads(keywords)
            if isinstance(keywords_obj, list):
                keywords_list = unique_list(keywords_obj)
            elif isinstance(keywords_obj, dict):
                keywords_list = unique_list(list(keywords_obj.values()))
            elif isinstance(keywords_obj, str):
                keywords_list = unique_list([keywords_obj])
            else:
                keywords_list = []

            entities_obj = safe_json_loads(entities)
            if not isinstance(entities_obj, dict):
                entities_obj = {}

            metadata_obj = safe_json_loads(metadata)
            if not isinstance(metadata_obj, dict):
                metadata_obj = {}

            docs.append(
                SearchDocument(
                    file_id=int(file_id),
                    document_id=int(document_id) if document_id is not None else None,
                    original_filename=normalize_text(original_filename),
                    stored_filename=normalize_text(stored_filename),
                    file_url=normalize_text(file_url),
                    file_size=int(file_size) if file_size is not None else None,
                    upload_status=normalize_text(upload_status),
                    error_message=normalize_text(error_message) if error_message else None,
                    raw_text=normalize_text(raw_text),
                    summary=normalize_text(summary),
                    keywords=keywords_list,
                    entities=entities_obj,
                    metadata=metadata_obj,
                    language=normalize_text(language),
                    extraction_status=normalize_text(extraction_status),
                    summary_status=normalize_text(summary_status),
                    file_created_at=(
                        file_created_at.isoformat()
                        if hasattr(file_created_at, "isoformat")
                        else normalize_text(file_created_at) or None
                    ),
                    file_updated_at=(
                        file_updated_at.isoformat()
                        if hasattr(file_updated_at, "isoformat")
                        else normalize_text(file_updated_at) or None
                    ),
                    document_created_at=(
                        document_created_at.isoformat()
                        if hasattr(document_created_at, "isoformat")
                        else normalize_text(document_created_at) or None
                    ),
                    document_updated_at=(
                        document_updated_at.isoformat()
                        if hasattr(document_updated_at, "isoformat")
                        else normalize_text(document_updated_at) or None
                    ),
                )
            )

        return docs

    except Exception:
        logger.exception("Failed to fetch user documents")
        raise

    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)


# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------

def build_search_blob(doc: SearchDocument) -> str:
    entity_text = normalize_text(doc.entities)
    metadata_text = normalize_text(doc.metadata)

    parts = [
        doc.original_filename,
        doc.stored_filename,
        doc.summary,
        " ".join(doc.keywords),
        entity_text,
        metadata_text,
        doc.language,
        doc.raw_text[:4000],
    ]
    return " \n ".join([p for p in parts if p])


def recency_bonus(doc: SearchDocument) -> float:
    ts = (
        parse_timestamp(doc.document_updated_at)
        or parse_timestamp(doc.file_updated_at)
        or parse_timestamp(doc.document_created_at)
        or parse_timestamp(doc.file_created_at)
    )

    if not ts:
        return 0.0

    age_days = max((datetime.utcnow() - ts.replace(tzinfo=None)).days, 0)
    if age_days <= 2:
        return 1.25
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.75
    if age_days <= 90:
        return 0.35
    return 0.1

def score_document(query: str, doc: SearchDocument) -> float:
    q = query.lower().strip()
    if not q:
        return 0.0

    q_tokens = tokenize(q)
    if not q_tokens:
        return 0.0

    blob = build_search_blob(doc).lower()
    blob_tokens = tokenize(blob)

    score = 0.0
    q_set = set(q_tokens)
    blob_set = set(blob_tokens)

    # Strong signals
    if q in doc.original_filename.lower():
        score += 8.0
    if q in doc.summary.lower():
        score += 6.0
    if q in blob:
        score += 4.0

    # Intent-based boosts
    if "skill" in q:
        doc_text = f"{doc.summary} {doc.raw_text} {doc.metadata}".lower()
        if any(term in doc_text for term in ("skill", "skills", "technical skills", "technologies", "tools", "frameworks", "languages")):
            score += 4.5

    if "project" in q:
        if any(term in blob for term in ("project", "projects", "portfolio")):
            score += 3.0

    if "internship" in q or "experience" in q:
        if any(term in blob for term in ("internship", "experience", "training", "work experience")):
            score += 3.0

    if "certificate" in q or "certificates" in q or "certification" in q:
        if any(term in blob for term in ("certificate", "certificates", "certification", "credential")):
            score += 3.0

    # Token overlap
    overlap = sum(1 for t in q_set if t in blob_set)
    score += overlap * 2.5

    # Keyword / entity / metadata boosts
    kw_set = {k.lower() for k in doc.keywords}
    kw_overlap = sum(1 for t in q_set if t in kw_set)
    score += kw_overlap * 3.0

    ent_text = normalize_text(doc.entities).lower()
    if ent_text:
        for t in q_set:
            if t in ent_text:
                score += 0.9

    meta_text = normalize_text(doc.metadata).lower()
    if meta_text:
        for t in q_set:
            if t in meta_text:
                score += 0.7

    # Summary and raw text density
    if doc.summary:
        score += min(len(q_set & set(tokenize(doc.summary))) * 1.6, 7.0)
    if doc.raw_text:
        score += min(len(q_set & set(tokenize(doc.raw_text[:6000]))) * 1.0, 6.0)

    # Filename hints
    filename_text = f"{doc.original_filename} {doc.stored_filename}".lower()
    for t in q_set:
        if t in filename_text:
            score += 0.8

    # Recency boost
    score += recency_bonus(doc)

    if score < MIN_RELEVANCE_SCORE:
        return 0.0

    return score

def rank_documents(
    query: str,
    documents: list[SearchDocument],
    limit: int = MAX_CONTEXT_DOCS,
) -> list[SearchDocument]:
    scored: list[SearchDocument] = []

    for doc in documents:
        doc.score = score_document(query, doc)
        if doc.score >= MIN_RELEVANCE_SCORE:
            scored.append(doc)

    scored.sort(
        key=lambda d: (d.score, d.document_updated_at or "", d.file_id),
        reverse=True,
    )

    return scored[:limit]
# ---------------------------------------------------------
# Context builder
# ---------------------------------------------------------

def format_keywords(keywords: list[str]) -> str:
    return ", ".join(unique_list(keywords))


def format_entities(entities: dict[str, Any]) -> str:
    if not entities:
        return ""

    parts = []
    for key in sorted(entities.keys()):
        value = entities.get(key)
        if value is None:
            continue

        if isinstance(value, list):
            items = unique_list(value)
            if items:
                parts.append(f"{key}: {', '.join(items)}")
        elif isinstance(value, dict):
            text = normalize_text(value).strip()
            if text and text != "{}":
                parts.append(f"{key}: {text}")
        else:
            text = normalize_text(value).strip()
            if text:
                parts.append(f"{key}: {text}")

    return "\n".join(parts)


def format_metadata(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ""

    parts = []
    for key in sorted(metadata.keys()):
        value = metadata.get(key)
        if value is None:
            continue

        if isinstance(value, list):
            items = unique_list(value)
            if items:
                parts.append(f"{key}: {', '.join(items)}")
        elif isinstance(value, dict):
            text = normalize_text(value).strip()
            if text and text != "{}":
                parts.append(f"{key}: {text}")
        else:
            text = normalize_text(value).strip()
            if text:
                parts.append(f"{key}: {text}")

    return "\n".join(parts)


def build_context(docs: list[SearchDocument]) -> str:
    sections: list[str] = []

    for index, doc in enumerate(docs, start=1):
        excerpt = truncate_text(doc.raw_text, MAX_EXCERPT_CHARS)
        keywords = format_keywords(doc.keywords)
        entities = format_entities(doc.entities)
        metadata = format_metadata(doc.metadata)

        section = f"""
[Document {index}]
File ID: {doc.file_id}
Document ID: {doc.document_id if doc.document_id is not None else ""}
Filename: {doc.original_filename}
Upload Status: {doc.upload_status}
Extraction Status: {doc.extraction_status}
Summary Status: {doc.summary_status}
Language: {doc.language}
Score: {doc.score:.2f}

Summary:
{doc.summary or ""}

Keywords:
{keywords}

Entities:
{entities}

Metadata:
{metadata}

Text Excerpt:
{excerpt}
""".strip()

        sections.append(section)

    context = "\n\n---\n\n".join(sections)

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[: MAX_CONTEXT_CHARS - 20].rstrip() + "\n...[context truncated]..."

    return context


# ---------------------------------------------------------
# AI answer generation
# ---------------------------------------------------------

SEARCH_SYSTEM_PROMPT = """
You are Veyra AI Search.

Use only the provided document context.
Do not invent facts.
If the documents do not contain the answer, say that clearly.

Return ONLY valid JSON.
Do not use markdown.
Do not wrap the answer in triple backticks.

Required JSON shape:

{
  "answer": "",
  "confidence": 0.0,
  "matched_documents": [
    {
      "file_id": 0,
      "document_id": 0,
      "filename": "",
      "reason": ""
    }
  ],
  "follow_up": "",
  "keywords": []
}
"""


def ask_ai(question: str, context: str) -> str:
    if client is None:
        raise SearchError(
            "OPENROUTER_API_KEY is missing. AI search cannot call the model."
        )

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        temperature=TEMPERATURE,
        messages=[
            {
                "role": "system",
                "content": SEARCH_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"""
User question:
{question}

Document context:
{context}
""".strip(),
            },
        ],
    )

    content = response.choices[0].message.content or ""
    return content.strip()


def fallback_answer(query: str, docs: list[SearchDocument]) -> dict[str, Any]:
    if not docs:
        return {
            "answer": "I could not find any matching documents.",
            "confidence": 0.0,
            "matched_documents": [],
            "follow_up": "",
            "keywords": tokenize(query)[:10],
        }

    top = docs[0]
    answer_parts = [
        f"I found {len(docs)} matching document(s).",
        f"Top match: {top.original_filename}.",
    ]

    if top.summary:
        answer_parts.append(f"Summary: {top.summary[:600]}")
    elif top.raw_text:
        answer_parts.append(f"Excerpt: {top.raw_text[:600]}")

    return {
        "answer": " ".join(answer_parts),
        "confidence": min(max(top.score / 10.0, 0.25), 0.85),
        "matched_documents": [
            {
                "file_id": doc.file_id,
                "document_id": doc.document_id,
                "filename": doc.original_filename,
                "reason": "High textual match" if i == 0 else "Related document",
            }
            for i, doc in enumerate(docs[:5])
        ],
        "follow_up": "",
        "keywords": unique_list(tokenize(query))[:10],
    }


def normalize_ai_result(data: dict[str, Any]) -> dict[str, Any]:
    data = data or {}

    data.setdefault("answer", "")
    data.setdefault("confidence", 0.0)
    data.setdefault("matched_documents", [])
    data.setdefault("follow_up", "")
    data.setdefault("keywords", [])

    try:
        data["confidence"] = float(data["confidence"])
    except Exception:
        data["confidence"] = 0.0

    data["confidence"] = max(0.0, min(data["confidence"], 1.0))

    if not isinstance(data["matched_documents"], list):
        data["matched_documents"] = []

    if not isinstance(data["keywords"], list):
        data["keywords"] = []

    data["matched_documents"] = [
        md if isinstance(md, dict) else {"filename": normalize_text(md)}
        for md in data["matched_documents"]
    ]

    data["keywords"] = unique_list(data["keywords"])

    return data


# ---------------------------------------------------------
# Main search API
# ---------------------------------------------------------

def ai_search(
    user_id: int,
    query: str,
    limit: int = MAX_CONTEXT_DOCS,
    status_callback: StatusCallback = None,
) -> dict[str, Any]:
    if user_id is None:
        return {
            "success": False,
            "error": "user_id is required.",
        }

    query = normalize_text(query).strip()
    if not query:
        return {
            "success": False,
            "error": "Query is empty.",
        }

    update_status(status_callback, "Searching documents", 10)

    documents = fetch_user_documents(user_id, limit=MAX_CANDIDATE_DOCS)

    if not documents:
        update_status(status_callback, "Completed", 100)
        return {
            "success": True,
            "query": query,
            "answer": "No documents found in your workspace.",
            "confidence": 0.0,
            "documents": [],
            "matched_documents": [],
            "mode": "empty",
        }

    update_status(status_callback, "Ranking matches", 25)

    search_query = expand_query(query)
    ranked = rank_documents(search_query, documents, limit=limit)

    if not ranked or ranked[0].score <= 0:
        update_status(status_callback, "Completed", 100)
        return {
            "success": True,
            "query": query,
            "answer": "I found your documents, but none matched the search strongly.",
            "confidence": 0.0,
            "documents": [doc.to_dict() for doc in ranked[:limit]],
            "matched_documents": [],
            "mode": "ranking_only",
        }

    update_status(status_callback, "Building context", 45)

    context = build_context(ranked)

    # If the model key is missing, return a useful fallback.
    if client is None:
        update_status(status_callback, "Completed", 100)
        fb = fallback_answer(query, ranked)
        return {
            "success": True,
            "query": query,
            "answer": fb["answer"],
            "confidence": fb["confidence"],
            "documents": [doc.to_dict() for doc in ranked],
            "matched_documents": fb["matched_documents"],
            "keywords": fb["keywords"],
            "mode": "fallback_no_ai",
        }

    try:
        update_status(status_callback, "Querying AI", 70)

        raw_response = ask_ai(query, context)

        update_status(status_callback, "Parsing response", 88)

        try:
            ai_data = extract_json_object(raw_response)
        except Exception:
            logger.warning("AI search returned invalid JSON. Using fallback.")
            fb = fallback_answer(query, ranked)
            update_status(status_callback, "Completed", 100)
            return {
                "success": True,
                "query": query,
                "answer": fb["answer"],
                "confidence": fb["confidence"],
                "documents": [doc.to_dict() for doc in ranked],
                "matched_documents": fb["matched_documents"],
                "keywords": fb["keywords"],
                "raw_response": raw_response,
                "mode": "fallback_invalid_json",
            }

        ai_data = normalize_ai_result(ai_data)

        if not ai_data.get("matched_documents"):
            ai_data["matched_documents"] = [
                {
                    "file_id": doc.file_id,
                    "document_id": doc.document_id,
                    "filename": doc.original_filename,
                    "reason": "Ranked match",
                }
                for doc in ranked[:3]
            ]

        update_status(status_callback, "Completed", 100)

        return {
            "success": True,
            "query": query,
            "answer": ai_data["answer"],
            "confidence": ai_data["confidence"],
            "documents": [doc.to_dict() for doc in ranked],
            "matched_documents": ai_data["matched_documents"],
            "follow_up": ai_data["follow_up"],
            "keywords": ai_data["keywords"],
            "raw_response": raw_response,
            "mode": "ai",
        }

    except Exception as exc:
        logger.exception("AI search failed")
        fb = fallback_answer(query, ranked)
        update_status(status_callback, "Completed", 100)
        return {
            "success": True,
            "query": query,
            "answer": fb["answer"],
            "confidence": fb["confidence"],
            "documents": [doc.to_dict() for doc in ranked],
            "matched_documents": fb["matched_documents"],
            "keywords": fb["keywords"],
            "error": str(exc),
            "mode": "fallback_error",
        }


# ---------------------------------------------------------
# Optional helper for routes
# ---------------------------------------------------------

def search_documents(user_id: int, query: str, limit: int = MAX_CONTEXT_DOCS) -> dict[str, Any]:
    return ai_search(user_id=user_id, query=query, limit=limit)

def list_user_documents(user_id: int) -> dict[str, Any]:
    docs = fetch_user_documents(user_id, limit=MAX_CANDIDATE_DOCS)
    return {
        "success": True,
        "count": len(docs),
        "documents": [doc.to_dict() for doc in docs],
    }