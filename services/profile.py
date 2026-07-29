from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from services.db import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def _unique(items: List[Any]) -> List[str]:
    out: List[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def _as_iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _first_words(text: str, limit: int = 12) -> str:
    words = [w for w in str(text or "").split() if w]
    return " ".join(words[:limit])


def _infer_doc_kind(title: str, summary: str, keywords: Any, metadata: Any) -> str:
    title_l = f"{title} {summary}".lower()
    metadata_obj = _safe_json(metadata) or {}
    if isinstance(metadata_obj, dict):
        for key in ("document", "content", "search"):
            block = metadata_obj.get(key)
            if isinstance(block, dict):
                title_l += " " + " ".join(str(v).lower() for v in block.values() if v)
            elif block:
                title_l += f" {block}".lower()

    kw_obj = _safe_json(keywords)
    kw_text = ""
    if isinstance(kw_obj, list):
        kw_text = " ".join(str(x).lower() for x in kw_obj)
    elif isinstance(kw_obj, dict):
        kw_text = " ".join(str(x).lower() for x in kw_obj.values())
    elif isinstance(kw_obj, str):
        kw_text = kw_obj.lower()

    haystack = f"{title_l} {kw_text}"

    credential_terms = ("certificate", "certification", "credential", "badge", "license", "award", "credentialed")
    project_terms = ("project", "portfolio", "prototype", "app", "website", "system", "build", "hackathon")

    if any(term in haystack for term in credential_terms):
        return "credentials"
    if any(term in haystack for term in project_terms):
        return "projects"
    return "documents"


def _extract_keywords(keywords: Any) -> List[str]:
    keywords = _safe_json(keywords)
    if not keywords:
        return []
    if isinstance(keywords, list):
        return _unique(keywords)
    if isinstance(keywords, dict):
        values: List[Any] = []
        for key in ("keywords", "skills", "items"):
            val = keywords.get(key)
            if isinstance(val, list):
                values.extend(val)
        return _unique(values)
    return []


def _format_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%d %b %Y")
        except Exception:
            pass
    return str(value or "")


def build_profile_data(user_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, firstName, lastName, email, created_at
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        user_row = cur.fetchone()

        if not user_row:
            return {
                "user": {
                    "id": user_id,
                    "firstName": "User",
                    "lastName": "",
                    "email": "",
                    "created_at": None,
                },
                "stats": {
                    "documents": 0,
                    "completed": 0,
                    "active": 0,
                    "failed": 0,
                    "skills": 0,
                    "projects": 0,
                    "credentials": 0,
                    "completeness": 0,
                },
                "skills": [],
                "recent_documents": [],
                "highlights": [],
                "joined_label": "",
            }

        cur.execute(
            """
            SELECT
                uf.id AS file_id,
                uf.original_filename,
                uf.file_url,
                uf.file_size,
                uf.upload_status,
                uf.error_message,
                uf.created_at,
                uf.updated_at,
                COALESCE(d.summary, '') AS summary,
                d.keywords,
                d.entities,
                d.metadata
            FROM uploaded_files uf
            LEFT JOIN documents d
                ON d.uploaded_file_id = uf.id
            WHERE uf.user_id = %s
            ORDER BY uf.created_at DESC, uf.id DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall() or []

    except Exception:
        logger.exception("Failed to build profile data")
        raise
    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)

    if hasattr(user_row, "keys"):
        user = dict(user_row)
    else:
        user = {
            "id": user_row[0],
            "firstName": user_row[1],
            "lastName": user_row[2],
            "email": user_row[3],
            "created_at": user_row[4],
        }

    total_documents = len(rows)
    completed = 0
    active = 0
    failed = 0
    project_count = 0
    credential_count = 0
    skill_counter: Counter[str] = Counter()
    recent_documents: List[Dict[str, Any]] = []

    for row in rows:
        if hasattr(row, "keys"):
            item = dict(row)
        else:
            item = {
                "file_id": row[0],
                "original_filename": row[1],
                "file_url": row[2],
                "file_size": row[3],
                "upload_status": row[4],
                "error_message": row[5],
                "created_at": row[6],
                "updated_at": row[7],
                "summary": row[8],
                "keywords": row[9],
                "entities": row[10],
                "metadata": row[11],
            }

        status = str(item.get("upload_status") or "").lower()
        if status == "completed":
            completed += 1
        elif status == "failed":
            failed += 1
        else:
            active += 1

        keywords = _extract_keywords(item.get("keywords"))
        for keyword in keywords:
            skill_counter[keyword] += 1

        title = str(item.get("original_filename") or "Untitled")
        summary = str(item.get("summary") or "").strip()
        kind = _infer_doc_kind(title, summary, item.get("keywords"), item.get("metadata"))
        if kind == "projects":
            project_count += 1
        elif kind == "credentials":
            credential_count += 1

        recent_documents.append({
            "name": title,
            "summary": summary or "Processed successfully",
            "status": status or "uploaded",
            "kind": kind,
            "date": _format_label(item.get("created_at")),
            "file_url": item.get("file_url") or "#",
        })

    top_skills = [skill for skill, _ in skill_counter.most_common(8)]
    completeness = min(99, 30 + total_documents * 7 + completed * 4 + len(top_skills) * 2)
    if total_documents == 0:
        completeness = 0

    joined_label = _format_label(user.get("created_at"))

    highlights = []
    if total_documents:
        highlights.append(f"{total_documents} documents in workspace")
    if completed:
        highlights.append(f"{completed} completed uploads")
    if top_skills:
        highlights.append(f"Top skill: {top_skills[0]}")
    if project_count:
        highlights.append(f"{project_count} project-related files")
    if credential_count:
        highlights.append(f"{credential_count} credential files")

    return {
        "user": {
            "id": user.get("id"),
            "firstName": user.get("firstName") or "User",
            "lastName": user.get("lastName") or "",
            "email": user.get("email") or "",
            "created_at": _as_iso(user.get("created_at")),
        },
        "stats": {
            "documents": total_documents,
            "completed": completed,
            "active": active,
            "failed": failed,
            "skills": len(top_skills),
            "projects": project_count,
            "credentials": credential_count,
            "completeness": completeness,
        },
        "skills": top_skills,
        "recent_documents": recent_documents[:4],
        "highlights": highlights[:4],
        "joined_label": joined_label,
    }
