from __future__ import annotations

import logging
import os
import threading
import tempfile
import uuid
from functools import wraps
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from services.db import get_db_connection, init_db, release_db_connection
from services import upload as upload_service
from services.search import ai_search as run_ai_search
from services.timeline import build_timeline
from services.dashboard import build_dashboard_data
from services.profile import build_profile_data
from services.upload import get_upload_overview, clear_completed_uploads


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024

# Ensure the upload table exists
init_db()

# ------------------------------------------
# Upload task manager
# ------------------------------------------
UPLOAD_TASKS: dict[str, dict] = {}
UPLOAD_TASKS_LOCK = threading.Lock()


def update_upload_task(task_id: str, **kwargs):
    with UPLOAD_TASKS_LOCK:
        if task_id not in UPLOAD_TASKS:
            UPLOAD_TASKS[task_id] = {}
        UPLOAD_TASKS[task_id].update(kwargs)


def get_upload_task(task_id: str):
    with UPLOAD_TASKS_LOCK:
        return UPLOAD_TASKS.get(task_id)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return view_func(*args, **kwargs)

    return wrapper


def get_logged_in_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_db_connection()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, firstName, lastName, email
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        return cur.fetchone()
    except Exception:
        logger.exception("Failed to fetch logged in user")
        return None
    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)


@app.route("/")
def home():
    user = get_logged_in_user()
    return render_template("index.html", user=user)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("register.html", error=None)

    is_json = request.is_json

    if is_json:
        data = request.get_json(silent=True) or {}

        first_name = (
            data.get("firstName")
            or data.get("first_name")
            or data.get("firstname")
            or ""
        ).strip()

        last_name = (
            data.get("lastName")
            or data.get("last_name")
            or data.get("lastname")
            or ""
        ).strip()

        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
    else:
        first_name = (
            request.form.get("firstName")
            or request.form.get("first_name")
            or request.form.get("firstname")
            or ""
        ).strip()

        last_name = (
            request.form.get("lastName")
            or request.form.get("last_name")
            or request.form.get("lastname")
            or ""
        ).strip()

        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

    print("Content-Type:", request.content_type)
    print("First Name:", first_name)
    print("Last Name:", last_name)
    print("Email:", email)

    if not first_name or not email or not password:
        message = "Please fill all required fields."

        if is_json:
            return jsonify({
                "success": False,
                "message": message
            }), 400

        return render_template(
            "register.html",
            error=message
        ), 400

    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        if cur.fetchone():
            message = "Email already exists."

            if is_json:
                return jsonify({
                    "success": False,
                    "message": message
                }), 400

            return render_template(
                "register.html",
                error=message
            ), 400

        password_hash = generate_password_hash(password)

        cur.execute(
            """
            INSERT INTO users
            (firstName, lastName, email, password_hash)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (
                first_name,
                last_name,
                email,
                password_hash,
            ),
        )

        user_id = cur.fetchone()[0]
        conn.commit()

        session["user_id"] = user_id
        session["email"] = email
        session["firstName"] = first_name
        session["lastName"] = last_name

        if is_json:
            return jsonify({
                "success": True,
                "redirect": "/dashboard"
            })

        return redirect("/dashboard")

    except Exception as e:
        conn.rollback()
        logger.exception("Signup failed")

        if is_json:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 500

        return render_template(
            "register.html",
            error=f"Signup failed: {e}"
        ), 500

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not email or not password:
        if is_ajax:
            return jsonify({
                "success": False,
                "error": "Please enter email and password."
            }), 400

        return render_template(
            "login.html",
            error="Please enter email and password."
        ), 400

    conn = get_db_connection()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, firstName, lastName, email, password_hash
            FROM users
            WHERE email = %s
            """,
            (email,),
        )

        user = cur.fetchone()

        if not user or not check_password_hash(user[4], password):
            if is_ajax:
                return jsonify({
                    "success": False,
                    "error": "Invalid email or password."
                }), 401

            return render_template(
                "login.html",
                error="Invalid email or password."
            ), 401

        session["user_id"] = user[0]
        session["email"] = user[3]
        session["firstName"] = user[1]
        session["lastName"] = user[2]

        if is_ajax:
            return jsonify({
                "success": True,
                "message": "Login successful",
                "redirect": "/dashboard"
            })

        return redirect("/dashboard")

    except Exception as e:
        logger.exception("Login failed")

        if is_ajax:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

        return render_template(
            "login.html",
            error=f"Login failed: {str(e)}"
        ), 500

    finally:
        if cur is not None:
            cur.close()

        release_db_connection(conn)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_logged_in_user()
    dashboard_data = build_dashboard_data(session["user_id"])

    return render_template(
        "dashboard.html",
        user=user,
        current_date=datetime.now().strftime("%d %b %Y"),
        greeting="Good day",
        **dashboard_data
    )

@app.route("/profile")
@login_required
def profile():
    profile_data = build_profile_data(session["user_id"])
    return render_template("profile.html", user=profile_data["user"], profile=profile_data)

@app.route("/search")
@login_required
def ai_search():
    user = get_logged_in_user()
    return render_template("search.html", user=user)


@app.route("/timeline")
@login_required
def timeline():
    user = get_logged_in_user()
    return render_template("timeline.html", user=user)

@app.route("/api/timeline", methods=["GET"])
@login_required
def api_timeline():
    return jsonify(build_timeline(session["user_id"]))

@app.route("/settings")
@login_required
def settings():
    user = get_logged_in_user()
    return render_template("settings.html", user=user)


def process_upload_task(task_id: str, temp_file_path: str, filename: str, content_type: str, user_id: int):
    try:
        update_upload_task(
            task_id,
            status="processing",
            stage="Uploading",
            progress=5,
            user_id=user_id,
        )

        with open(temp_file_path, "rb") as f:
            upload_file = FileStorage(
                stream=f,
                filename=filename,
                content_type=content_type,
            )

            update_upload_task(task_id, stage="Processing document", progress=20)

            result = upload_service.upload_file(
                file=upload_file,
                user_id=user_id,
                status_callback=lambda **kwargs: update_upload_task(task_id, **kwargs),
            )

        update_upload_task(
            task_id,
            status="completed",
            stage="Completed",
            progress=100,
            result=result,
        )

    except Exception as e:
        logger.exception("Upload task failed: %s", task_id)
        update_upload_task(
            task_id,
            status="failed",
            stage="Failed",
            progress=100,
            error=str(e),
        )

    finally:
        try:
            os.remove(temp_file_path)
        except Exception:
            pass


@app.route("/upload", methods=["GET", "POST"], strict_slashes=False)
def upload_file():
    if request.method == "GET":
        if "user_id" not in session:
            return redirect("/login")

        user = get_logged_in_user()
        upload_summary = get_upload_overview(session["user_id"])
        return render_template("upload.html", user=user, upload_summary=upload_summary)

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({
            "success": False,
            "message": "No file selected"
        }), 400

    try:
        task_id = str(uuid.uuid4())
        update_upload_task(
            task_id,
            user_id=session["user_id"],
            status="queued",
            stage="Queued",
            progress=0,
        )

        safe_name = secure_filename(file.filename)
        temp_path = Path(tempfile.gettempdir()) / f"{task_id}_{safe_name}"
        file.save(temp_path)

        thread = threading.Thread(
            target=process_upload_task,
            args=(
                task_id,
                str(temp_path),
                file.filename,
                file.content_type,
                session["user_id"],
            ),
            daemon=True,
        )
        thread.start()

        return jsonify({
            "success": True,
            "message": "Upload started",
            "task_id": task_id
        }), 202

    except Exception as e:
        logger.exception("Unexpected upload error")
        return jsonify({
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        }), 500


@app.route("/upload-status/<task_id>", methods=["GET"])
def upload_status(task_id):
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    task = get_upload_task(task_id)
    if task is None:
        return jsonify({
            "success": False,
            "message": "Task not found"
        }), 404

    if task.get("user_id") != session["user_id"]:
        return jsonify({
            "success": False,
            "message": "Access denied"
        }), 403

    return jsonify({
        "success": True,
        "status": task.get("status"),
        "stage": task.get("stage"),
        "progress": task.get("progress"),
        "result": task.get("result"),
        "error": task.get("error")
    })


@app.route("/api/files", methods=["GET"])
def api_files():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required",
            "files": []
        }), 401

    try:
        files = upload_service.get_user_uploads(session["user_id"])
        return jsonify(files), 200

    except Exception as e:
        logger.exception("Failed to load files")
        return jsonify({
            "success": False,
            "message": "Unable to load files",
            "error": str(e),
            "files": []
        }), 500


@app.route("/api/uploads/clear-completed", methods=["POST"])
@login_required
def api_clear_completed_uploads():
    try:
        deleted = clear_completed_uploads(session["user_id"])
        return jsonify({
            "success": True,
            "deleted": deleted,
            "message": f"Cleared {deleted} completed upload(s).",
        }), 200
    except Exception as e:
        logger.exception("Failed to clear completed uploads")
        return jsonify({
            "success": False,
            "message": "Unable to clear completed uploads",
            "error": str(e),
        }), 500
@app.route("/api/search", methods=["POST"])
@login_required
def api_search():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({
            "success": False,
            "message": "Query is required."
        }), 400

    try:
        result = run_ai_search(
            user_id=session["user_id"],
            query=query
        )
        return jsonify(result), 200

    except Exception as e:
        logger.exception("AI Search failed")
        return jsonify({
            "success": False,
            "message": "Search failed",
            "error": str(e)
        }), 500

@app.route("/api/search/documents", methods=["GET"])
@login_required
def api_search_documents():
    from services.search import list_user_documents

    return jsonify(list_user_documents(session["user_id"]))

@app.route("/delete-file/<int:file_id>", methods=["DELETE"])
def delete_file(file_id: int):
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    try:
        deleted = upload_service.delete_user_upload(session["user_id"], file_id)

        if not deleted:
            return jsonify({
                "success": False,
                "message": "File not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "File deleted successfully"
        }), 200

    except Exception as e:
        logger.exception("Delete failed")
        return jsonify({
            "success": False,
            "message": "Unable to delete file",
            "error": str(e)
        }), 500


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(413)
def request_entity_too_large(_):
    return jsonify({
        "success": False,
        "message": "File too large"
    }), 413


if __name__ == "__main__":
    app.run(debug=True)