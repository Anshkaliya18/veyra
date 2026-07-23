# services/upload.py
from __future__ import annotations

import logging
import mimetypes
import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import tempfile

from dotenv import load_dotenv
from supabase import Client, create_client
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from services.extractor import extract_text
from services.db import get_db_connection, release_db_connection
from services.summarizer import summarize_document

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "documents").strip()

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".csv",
    ".xlsx",
    ".xls",
}

_supabase: Optional[Client] = None


class UploadError(Exception):
    pass


def get_supabase_client() -> Client:
    global _supabase

    if _supabase is not None:
        return _supabase

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise UploadError("SUPABASE_URL or SUPABASE_KEY is missing")

    _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def _allowed_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def _read_file_bytes(file: FileStorage) -> bytes:
    file.stream.seek(0)
    data = file.read()
    file.stream.seek(0)
    return data


def _get_file_size(file: FileStorage) -> int:
    content_length = getattr(file, "content_length", None)
    if isinstance(content_length, int) and content_length > 0:
        return content_length

    data = _read_file_bytes(file)
    return len(data)


def _make_stored_filename(original_filename: str) -> str:
    original_filename = secure_filename(original_filename or "upload")
    ext = Path(original_filename).suffix.lower()
    base = Path(original_filename).stem or "file"
    unique_id = uuid.uuid4().hex
    return f"{base}_{unique_id}{ext}"


def _build_storage_path(user_id: int, stored_filename: str) -> str:
    return f"user_{user_id}/{stored_filename}"


def _get_file_url(bucket_name: str, storage_path: str) -> str:
    supabase = get_supabase_client()
    try:
        return supabase.storage.from_(bucket_name).get_public_url(storage_path)
    except Exception:
        # If the bucket is private, keep the storage path.
        return storage_path


def _upload_to_supabase(file: FileStorage, user_id: int) -> Dict[str, Any]:
    if not file or not getattr(file, "filename", None):
        raise UploadError("No file provided")

    if not _allowed_file(file.filename):
        raise UploadError(f"Unsupported file type: {Path(file.filename).suffix.lower()}")

    file_size = _get_file_size(file)
    if file_size > MAX_UPLOAD_BYTES:
        raise UploadError(f"File too large. Maximum allowed is {MAX_UPLOAD_MB} MB")

    original_filename = secure_filename(file.filename)
    stored_filename = _make_stored_filename(original_filename)
    storage_path = _build_storage_path(user_id, stored_filename)

    content_type = file.mimetype
    if not content_type:
        content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

    supabase = get_supabase_client()
    file_bytes = _read_file_bytes(file)

    try:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": content_type,
                "x-upsert": "false",
            },
        )
    except Exception as exc:
        logger.exception("Supabase upload failed")
        raise UploadError(f"Failed to upload file to storage: {exc}") from exc

    file_url = _get_file_url(SUPABASE_BUCKET, storage_path)

    return {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "storage_path": storage_path,
        "file_url": file_url,
        "content_type": content_type,
        "file_size": file_size,
    }


def _insert_uploaded_file_row(
    *,
    user_id: int,
    original_filename: str,
    stored_filename: str,
    storage_path: str,
    file_url: str,
    content_type: str,
    file_size: int,
    upload_status: str = "uploaded",
    error_message: Optional[str] = None,
) -> int:
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO uploaded_files (
                user_id,
                original_filename,
                stored_filename,
                storage_path,
                file_url,
                content_type,
                file_size,
                upload_status,
                error_message,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            RETURNING id
            """,
            (
                user_id,
                original_filename,
                stored_filename,
                storage_path,
                file_url,
                content_type,
                file_size,
                upload_status,
                error_message,
            ),
        )
        file_id = cur.fetchone()[0]
        conn.commit()
        return int(file_id)

    except Exception:
        conn.rollback()
        logger.exception("Failed to insert uploaded_files row")
        raise

    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)

def _create_document(uploaded_file_id: int) -> int:
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO documents (
                uploaded_file_id,
                extraction_status,
                summary_status,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                'pending',
                'pending',
                NOW(),
                NOW()
            )
            RETURNING id
        """, (uploaded_file_id,))

        document_id = cur.fetchone()[0]

        conn.commit()

        return int(document_id)

    except Exception:
        conn.rollback()
        logger.exception("Failed to create document")
        raise

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)

def _save_extracted_text(uploaded_file_id: int, raw_text: str):
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute("""
            UPDATE documents
            SET
                raw_text = %s,
                extraction_status = 'completed',
                updated_at = NOW()
            WHERE uploaded_file_id = %s
        """,
        (
            raw_text,
            uploaded_file_id
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        logger.exception("Failed to save extracted text")
        raise

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)

def _save_summary_result(uploaded_file_id: int, ai_data: dict):
    """
    Save AI summary results into the documents table.
    """

    document = ai_data.get("document", {})
    key_information = ai_data.get("key_information", {})
    metadata = ai_data.get("metadata", {})

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE documents
                SET
                    summary = %s,
                    keywords = %s,
                    entities = %s,
                    metadata = %s,
                    language = %s,
                    summary_status = 'completed',
                    updated_at = NOW()
                WHERE uploaded_file_id = %s
                """,
                (
                    document.get("summary", ""),
                    json.dumps(metadata.get("keywords", [])),
                    json.dumps(key_information),
                    json.dumps(metadata),
                    document.get("language", ""),
                    uploaded_file_id,
                )
            )

        conn.commit()

    finally:
        conn.close()

def _mark_upload_failed(file_id: int, error_message: str) -> None:
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE uploaded_files
            SET upload_status = %s,
                error_message = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            ("failed", error_message[:2000], file_id),
        )
        conn.commit()

    except Exception:
        conn.rollback()
        logger.exception("Failed to mark upload as failed")

    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)


def _delete_from_supabase(storage_path: str) -> None:
    try:
        supabase = get_supabase_client()
        supabase.storage.from_(SUPABASE_BUCKET).remove([storage_path])
    except Exception:
        logger.exception("Failed to delete file from Supabase: %s", storage_path)


def upload_file(file: FileStorage, user_id: int) -> Dict[str, Any]:
    """
    Upload a file to Supabase Storage and save metadata in uploaded_files.

    Returns:
        {
            "success": True,
            "file_id": int,
            "original_filename": str,
            "stored_filename": str,
            "storage_path": str,
            "file_url": str,
            "file_size": int,
            "content_type": str
        }
    """
    if user_id is None:
        raise UploadError("user_id is required")

    if not file:
        raise UploadError("No file provided")

    if not getattr(file, "filename", ""):
        raise UploadError("Filename is missing")

    uploaded = _upload_to_supabase(file, user_id)

    file_id = None
    try:
        file_id = _insert_uploaded_file_row(
            user_id=user_id,
            original_filename=uploaded["original_filename"],
            stored_filename=uploaded["stored_filename"],
            storage_path=uploaded["storage_path"],
            file_url=uploaded["file_url"],
            content_type=uploaded["content_type"],
            file_size=uploaded["file_size"],
            upload_status="uploaded",
            error_message=None,
        )
        document_id = _create_document(file_id)

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(uploaded["stored_filename"]).suffix
        )

        try:
            # Save uploaded file temporarily
            file.save(temp_file.name)
            temp_file.close()

            # Extract text
            result = extract_text(temp_file.name)

            if result["success"]:

                text = result["text"]

                # Save extracted text into database
                _save_extracted_text(
                    uploaded_file_id=file_id,
                    raw_text=text
                )

                ai_result = summarize_document(text)

                if ai_result["success"]:

                    _save_summary_result(
                        uploaded_file_id=file_id,
                        ai_data=ai_result["data"]
                    )

                else:
                    logger.warning(
                        "AI summarization failed: %s",
                        ai_result["error"]
                    )

            else:
                logger.warning(
                    "Text extraction failed: %s",
                    result["error"]
                )

        except Exception as e:
            logger.exception("Extraction pipeline failed")
            raise UploadError(f"Extraction failed: {e}") from e

        finally:
            # Always delete temporary file
            try:
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
            except Exception:
                logger.warning(
                    "Could not delete temporary file: %s",
                    temp_file.name
                )

        return {
            "success": True,
            "file_id": file_id,
            "document_id": document_id,
            **uploaded,
        }

    except Exception as exc:
        logger.exception("Upload record save failed")

        # Clean up the uploaded storage object if DB insert fails
        _delete_from_supabase(uploaded["storage_path"])

        if file_id is not None:
            _mark_upload_failed(file_id, str(exc))

        raise UploadError(f"Failed to save upload record: {exc}") from exc


def get_user_uploads(user_id: int) -> list[dict[str, Any]]:
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, original_filename, stored_filename, storage_path,
                   file_url, content_type, file_size, upload_status,
                   error_message, created_at, updated_at
            FROM uploaded_files
            WHERE user_id = %s
            ORDER BY id DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return []

        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]

    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)


def delete_user_upload(user_id: int, file_id: int) -> bool:
    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT storage_path
            FROM uploaded_files
            WHERE id = %s AND user_id = %s
            """,
            (file_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return False

        storage_path = row[0]

        try:
            _delete_from_supabase(storage_path)
        except Exception:
            # Continue deleting DB row even if storage deletion fails.
            pass

        cur.execute(
            "DELETE FROM uploaded_files WHERE id = %s AND user_id = %s",
            (file_id, user_id),
        )
        conn.commit()
        return True

    except Exception:
        conn.rollback()
        logger.exception("Failed to delete user upload")
        raise

    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)