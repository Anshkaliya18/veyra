from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from services.db import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

CATEGORY_RULES = {
    "Credential": ["certificate", "certification", "credential", "course", "training", "coursera", "udemy", "google cloud", "gcp"],
    "Experience": ["internship", "intern", "experience", "worked", "employment", "job", "associate", "developer", "engineer"],
    "Project": ["project", "built", "developed", "implemented", "created", "designed", "capstone", "portfolio"],
    "Education": ["education", "college", "school", "b.tech", "btech", "degree", "university", "institute", "diploma", "academic"],
    "Achievement": ["award", "achievement", "won", "winner", "rank", "placed", "hackathon", "competition"],
    "Research": ["research", "paper", "publication", "journal", "study", "thesis"],
    "Skill": ["skill", "skills", "technical skills", "technologies", "tools", "frameworks"],
}

DATE_PATTERNS = [
    re.compile(r"\b(?P<year>19\d{2}|20\d{2})[-/](?P<month>0?[1-9]|1[0-2])[-/](?P<day>0?[1-9]|[12]\d|3[01])\b"),
    re.compile(r"\b(?P<day>0?[1-9]|[12]\d|3[01])[-/](?P<month>0?[1-9]|1[0-2])[-/](?P<year>19\d{2}|20\d{2})\b"),
    re.compile(r"\b(?P<month_name>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sept?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(?P<year>19\d{2}|20\d{2})\b", re.I),
    re.compile(r"\b(?P<year>19\d{2}|20\d{2})\b"),
]

RANGE_PATTERNS = [
    re.compile(r"\b(?P<start_month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sept?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(?P<start_year>19\d{2}|20\d{2})\s*[-–—to]+\s*(?P<end_month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sept?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)?\s*(?P<end_year>19\d{2}|20\d{2})?\b", re.I),
    re.compile(r"\b(?P<start_year>19\d{2}|20\d{2})\s*[-–—to]+\s*(?P<end_year>19\d{2}|20\d{2})\b"),
]

DATE_RANGE_SPLIT_RE = re.compile(r"\s*[:\-–—]\s*", re.U)


@dataclass
class TimelineEvent:
    file_id: int
    document_id: Optional[int]
    filename: str
    date: str
    display_date: str
    year: int
    title: str
    description: str
    category: str
    tags: list[str]
    confidence: float
    source: str = "document"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


def _safe_json_loads(value: Any) -> Any:
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


def _unique_list(items: Iterable[Any]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        if text not in seen:
            seen.append(text)
    return seen


def _flatten_values(value: Any) -> list[str]:
    results: list[str] = []
    if value is None:
        return results
    if isinstance(value, dict):
        for v in value.values():
            results.extend(_flatten_values(v))
        return results
    if isinstance(value, list):
        for v in value:
            results.extend(_flatten_values(v))
        return results
    text = _normalize_text(value).strip()
    if text:
        results.append(text)
    return results


def _first_sentence(text: str) -> str:
    text = _normalize_text(text).strip()
    if not text:
        return ""
    match = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return match[0].strip() if match else text


def _guess_title(metadata: dict[str, Any], summary: str, filename: str) -> str:
    document_meta = metadata.get("document", {}) if isinstance(metadata, dict) else {}
    title = _normalize_text(document_meta.get("title") if isinstance(document_meta, dict) else "").strip()
    if title:
        return title
    sentence = _first_sentence(summary)
    if sentence:
        return sentence[:120].rstrip()
    cleaned = re.sub(r"[_\-]+", " ", Path(filename).stem if filename else filename)
    cleaned = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", cleaned)
    return cleaned.strip() or filename or "Untitled"


def _detect_category(text: str) -> str:
    haystack = text.lower()
    best_category = "General"
    best_score = 0
    for category, keywords in CATEGORY_RULES.items():
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


def _extract_date_from_text(text: str) -> tuple[Optional[date], str]:
    if not text:
        return None, ""

    normalized = _normalize_text(text)
    candidate = None
    candidate_label = ""

    for pattern in RANGE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        gd = match.groupdict()
        if "start_month" in gd and gd.get("start_month") and gd.get("start_year"):
            sm = MONTHS.get(gd["start_month"].lower()[:4], MONTHS.get(gd["start_month"].lower()[:3], None))
            if sm is None:
                sm = MONTHS.get(gd["start_month"].lower(), None)
            sy = int(gd["start_year"])
            if sm:
                candidate = date(sy, sm, 1)
                candidate_label = match.group(0)
                return candidate, candidate_label
        if gd.get("start_year"):
            sy = int(gd["start_year"])
            candidate = date(sy, 1, 1)
            candidate_label = match.group(0)
            return candidate, candidate_label

    for pattern in DATE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        gd = match.groupdict()
        if gd.get("month_name") and gd.get("year"):
            month_key = gd["month_name"].lower()
            month = MONTHS.get(month_key[:3], MONTHS.get(month_key))
            if month:
                candidate = date(int(gd["year"]), month, 1)
                candidate_label = match.group(0)
                return candidate, candidate_label
        if gd.get("year") and gd.get("month") and gd.get("day"):
            try:
                candidate = date(int(gd["year"]), int(gd["month"]), int(gd["day"]))
                candidate_label = match.group(0)
                return candidate, candidate_label
            except Exception:
                continue
        if gd.get("year"):
            candidate = date(int(gd["year"]), 1, 1)
            candidate_label = match.group(0)
            return candidate, candidate_label

    return None, ""


def _parse_timeline_segment(segment: str) -> tuple[str, str, Optional[date], str]:
    raw = _normalize_text(segment).strip()
    if not raw:
        return "", "", None, ""

    parts = re.split(r"\s*[:\-–—]\s*", raw, maxsplit=1)
    date_part = parts[0].strip() if parts else raw
    desc_part = parts[1].strip() if len(parts) > 1 else raw

    dt, label = _extract_date_from_text(date_part)
    if dt is None:
        dt, label = _extract_date_from_text(raw)

    title = desc_part or raw
    description = raw
    return title, description, dt, label


def _clean_description(text: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", _normalize_text(text).strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _tags_from_metadata(metadata: dict[str, Any], limit: int = 5) -> list[str]:
    tags: list[str] = []
    if not isinstance(metadata, dict):
        return tags

    content = metadata.get("content", {}) if isinstance(metadata.get("content", {}), dict) else {}
    for key in ("keywords", "skills", "technologies", "topics"):
        value = content.get(key)
        if value:
            tags.extend(_flatten_values(value))

    document_meta = metadata.get("document", {}) if isinstance(metadata.get("document", {}), dict) else {}
    for key in ("category", "document_type", "purpose"):
        value = document_meta.get(key)
        if value:
            tags.extend(_flatten_values(value))

    search_meta = metadata.get("search", {}) if isinstance(metadata.get("search", {}), dict) else {}
    for key in ("keywords", "one_line"):
        value = search_meta.get(key)
        if value:
            tags.extend(_flatten_values(value))

    return _unique_list(tags)[:limit]


def _extract_entities(metadata: dict[str, Any]) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    entities = metadata.get("entities", {})
    return _unique_list(_flatten_values(entities))


def _extract_keywords(metadata: dict[str, Any]) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    content = metadata.get("content", {}) if isinstance(metadata.get("content", {}), dict) else {}
    search = metadata.get("search", {}) if isinstance(metadata.get("search", {}), dict) else {}
    keywords: list[str] = []
    keywords.extend(_flatten_values(content.get("keywords")))
    keywords.extend(_flatten_values(content.get("topics")))
    keywords.extend(_flatten_values(search.get("keywords")))
    return _unique_list(keywords)


def _best_document_date(row: dict[str, Any], metadata: dict[str, Any], text_sources: list[str]) -> tuple[date, str]:
    for source in text_sources:
        dt, label = _extract_date_from_text(source)
        if dt is not None:
            return dt, label or dt.isoformat()

    document_meta = metadata.get("document", {}) if isinstance(metadata, dict) else {}
    for key in ("summary", "purpose", "title"):
        val = document_meta.get(key) if isinstance(document_meta, dict) else None
        if val:
            dt, label = _extract_date_from_text(_normalize_text(val))
            if dt is not None:
                return dt, label or dt.isoformat()

    for key in ("document_created_at", "document_updated_at", "file_created_at", "file_updated_at"):
        val = row.get(key)
        if val:
            if isinstance(val, datetime):
                return val.date(), val.strftime("%b %Y")
            if isinstance(val, str):
                try:
                    parsed = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return parsed.date(), parsed.strftime("%b %Y")
                except Exception:
                    continue

    return date.today(), date.today().strftime("%b %Y")


def _confidence_from_fields(summary: str, keywords: list[str], entities: list[str], has_date: bool, category: str) -> float:
    score = 0.0
    if summary:
        score += 0.3
    if keywords:
        score += 0.2
    if entities:
        score += 0.2
    if has_date:
        score += 0.2
    if category != "General":
        score += 0.1
    return max(0.0, min(score, 1.0))


def _infer_events_for_document(row: dict[str, Any]) -> list[TimelineEvent]:
    file_id = int(row["file_id"])
    document_id = int(row["document_id"]) if row.get("document_id") is not None else None
    filename = _normalize_text(row.get("original_filename") or row.get("stored_filename") or "Untitled")
    summary = _normalize_text(row.get("summary") or "").strip()
    raw_text = _normalize_text(row.get("raw_text") or "").strip()
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = _safe_json_loads(metadata) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    keywords = _extract_keywords(metadata)
    entities = _extract_entities(metadata)
    tags = _tags_from_metadata(metadata)

    title = _guess_title(metadata, summary, filename)
    category_source_text = " ".join([filename, title, summary, raw_text, " ".join(keywords), " ".join(entities), _normalize_text(metadata)])
    category = _detect_category(category_source_text)

    text_sources: list[str] = []
    content_meta = metadata.get("content", {}) if isinstance(metadata.get("content", {}), dict) else {}
    timeline_items = content_meta.get("timeline") or []
    if isinstance(timeline_items, list):
        text_sources.extend(_normalize_text(x) for x in timeline_items if x)
    elif timeline_items:
        text_sources.extend(_normalize_text(timeline_items).splitlines())

    important_points = content_meta.get("important_points") or []
    if isinstance(important_points, list):
        text_sources.extend(_normalize_text(x) for x in important_points if x)
    elif important_points:
        text_sources.extend(_normalize_text(important_points).splitlines())

    if summary:
        text_sources.append(summary)
    if raw_text:
        text_sources.append(raw_text)

    events: list[TimelineEvent] = []

    # Prefer structured timeline items if available
    structured_items = []
    for item in timeline_items if isinstance(timeline_items, list) else []:
        text = _normalize_text(item).strip()
        if text:
            structured_items.append(text)

    for item in structured_items:
        item_title, item_desc, item_date, item_label = _parse_timeline_segment(item)
        if item_date is None:
            continue
        item_category = _detect_category(item)
        item_tags = _unique_list(tags + _flatten_values(item))[:5]
        events.append(
            TimelineEvent(
                file_id=file_id,
                document_id=document_id,
                filename=filename,
                date=item_date.isoformat(),
                display_date=item_label or item_date.strftime("%b %Y"),
                year=item_date.year,
                title=item_title or title,
                description=_clean_description(item_desc or item),
                category=item_category,
                tags=item_tags,
                confidence=_confidence_from_fields(summary, keywords, entities, True, item_category),
            )
        )

    if events:
        return events

    best_date, label = _best_document_date(row, metadata, text_sources)
    description = summary or _clean_description(raw_text, 260) or _clean_description(filename, 260)
    if not description:
        description = filename

    events.append(
        TimelineEvent(
            file_id=file_id,
            document_id=document_id,
            filename=filename,
            date=best_date.isoformat(),
            display_date=label or best_date.strftime("%b %Y"),
            year=best_date.year,
            title=title,
            description=description,
            category=category,
            tags=(tags + keywords + entities)[:5],
            confidence=_confidence_from_fields(summary, keywords, entities, True, category),
        )
    )

    return events


def _fetch_user_documents(user_id: int) -> list[dict[str, Any]]:
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
            """,
            (user_id,),
        )
        rows = cur.fetchall() or []

        columns = [
            "file_id",
            "document_id",
            "original_filename",
            "stored_filename",
            "file_url",
            "file_size",
            "upload_status",
            "error_message",
            "file_created_at",
            "file_updated_at",
            "raw_text",
            "summary",
            "keywords",
            "entities",
            "metadata",
            "language",
            "extraction_status",
            "summary_status",
            "document_created_at",
            "document_updated_at",
        ]

        documents: list[dict[str, Any]] = []
        for row in rows:
            if hasattr(row, "keys"):
                documents.append(dict(row))
            else:
                documents.append({columns[i]: row[i] for i in range(min(len(columns), len(row)))})
        return documents
    except Exception:
        logger.exception("Failed to fetch user documents for timeline")
        raise
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        release_db_connection(conn)


def _sort_key(event: TimelineEvent) -> tuple:
    try:
        dt = datetime.fromisoformat(event.date)
    except Exception:
        dt = datetime(event.year, 1, 1)
    return (dt, event.confidence, event.file_id)


def build_timeline(user_id: int) -> dict[str, Any]:
    if user_id is None:
        return {"success": False, "message": "user_id is required.", "events": [], "stats": {}}

    documents = _fetch_user_documents(user_id)
    if not documents:
        return {
            "success": True,
            "events": [],
            "stats": {
                "total": 0,
                "years": 0,
                "projects": 0,
                "education": 0,
                "experience": 0,
                "credentials": 0,
                "achievements": 0,
                "research": 0,
                "general": 0,
            },
        }

    events: list[TimelineEvent] = []
    for doc in documents:
        try:
            events.extend(_infer_events_for_document(doc))
        except Exception:
            logger.exception("Failed to build timeline event for file_id=%s", doc.get("file_id"))

    # De-duplicate by date/title/category/filename
    deduped: list[TimelineEvent] = []
    seen: set[tuple[str, str, str, str]] = set()
    for event in events:
        key = (
            event.date,
            event.title.lower().strip(),
            event.category.lower().strip(),
            event.filename.lower().strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)

    deduped.sort(key=_sort_key, reverse=True)

    stats = {
        "total": len(deduped),
        "years": len({e.year for e in deduped}),
        "projects": sum(1 for e in deduped if e.category == "Project"),
        "education": sum(1 for e in deduped if e.category == "Education"),
        "experience": sum(1 for e in deduped if e.category == "Experience"),
        "credentials": sum(1 for e in deduped if e.category == "Credential"),
        "achievements": sum(1 for e in deduped if e.category == "Achievement"),
        "research": sum(1 for e in deduped if e.category == "Research"),
        "general": sum(1 for e in deduped if e.category == "General"),
    }

    return {
        "success": True,
        "events": [e.to_dict() for e in deduped],
        "stats": stats,
    }


# Optional helper if you want to test this module directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        print(build_timeline(1))
    except Exception as exc:
        print("Timeline build failed:", exc)