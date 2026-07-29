# services/dashboard.py
from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List

from services.db import get_db_connection, release_db_connection


def _safe_json(value: Any):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def _extract_keywords(keywords: Any) -> List[str]:
    keywords = _safe_json(keywords)
    if not keywords:
        return []

    if isinstance(keywords, list):
        return [str(k).strip() for k in keywords if str(k).strip()]

    if isinstance(keywords, dict):
        # supports {"keywords": [...]} or {"skills": [...]}
        for key in ("keywords", "skills", "items"):
            val = keywords.get(key)
            if isinstance(val, list):
                return [str(k).strip() for k in val if str(k).strip()]
    return []


def _extract_entities(entities: Any) -> Dict[str, List[str]]:
    entities = _safe_json(entities)
    if not entities:
        return {}

    if isinstance(entities, dict):
        result = {}
        for k, vals in entities.items():
            if isinstance(vals, list):
                clean = [str(v).strip() for v in vals if str(v).strip()]
                if clean:
                    result[k] = clean
        return result

    return {}


def build_dashboard_data(user_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                uf.original_filename,
                uf.created_at,
                uf.upload_status,
                d.summary,
                d.keywords,
                d.entities
            FROM uploaded_files uf
            LEFT JOIN documents d ON d.uploaded_file_id = uf.id
            WHERE uf.user_id = %s
            ORDER BY uf.created_at DESC
        """, (user_id,))

        rows = cur.fetchall()

    finally:
        cur.close()
        release_db_connection(conn)

    total_docs = len(rows)
    recent_docs = []
    skill_counter = Counter()
    milestone_count = 0

    for row in rows:
        original_filename, created_at, upload_status, summary, keywords, entities = row

        kw_list = _extract_keywords(keywords)
        ent_map = _extract_entities(entities)

        for k in kw_list:
            skill_counter[k] += 1

        for category, values in ent_map.items():
            # Pull a few useful categories into the dashboard
            if category.lower() in {"skills", "projects", "certificates", "organizations", "education"}:
                for v in values:
                    skill_counter[v] += 1

        if summary or kw_list or ent_map:
            milestone_count += 1

        recent_docs.append({
            "name": original_filename,
            "status": upload_status or "uploaded",
            "time": created_at.strftime("%b %d, %Y") if created_at else "",
            "summary": (summary[:90] + "…") if summary and len(summary) > 90 else summary,
        })

    top_skills = [name for name, _ in skill_counter.most_common(8)]

    return {
        "stats": {
            "documents": total_docs,
            "skills": max(len(top_skills), 0),
            "milestones": milestone_count,
            "completeness": min(99, 50 + total_docs * 3 + milestone_count * 2),
        },
        "recent_docs": recent_docs[:3],
        "skills": top_skills,
        "timeline": [
            {"title": "Uploaded documents processed", "subtitle": f"{total_docs} files seen", "year": "Now"},
            {"title": "Entity extraction updated", "subtitle": f"{milestone_count} items mapped", "year": "Recent"},
        ],
    }