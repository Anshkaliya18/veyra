from __future__ import annotations

import logging
import os
from functools import wraps
from datetime import datetime

import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from services.db import get_db_connection, init_db, release_db_connection
from services import upload as upload_service

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024

# Ensure the upload table exists
init_db()


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
        return render_template("signup.html", error=None)

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

    if not first_name or not last_name or not email or not password:
        return render_template("signup.html", error="Please fill all required fields."), 400

    conn = get_db_connection()
    cur = None
    try:
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return render_template("signup.html", error="Email already exists."), 400

        password_hash = generate_password_hash(password)

        cur.execute(
            """
            INSERT INTO users (firstName, lastName, email, password_hash)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (first_name, last_name, email, password_hash),
        )
        user_id = cur.fetchone()[0]
        conn.commit()

        session["user_id"] = user_id
        session["email"] = email
        session["firstName"] = first_name
        session["lastName"] = last_name

        return redirect("/dashboard")

    except Exception as e:
        conn.rollback()
        logger.exception("Signup failed")
        return render_template("signup.html", error=f"Signup failed: {str(e)}"), 500

    finally:
        if cur is not None:
            cur.close()
        release_db_connection(conn)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    # Check if request came from fetch/AJAX
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

        # Save session
        session["user_id"] = user[0]
        session["email"] = user[3]
        session["firstName"] = user[1]
        session["lastName"] = user[2]

        # AJAX login
        if is_ajax:
            return jsonify({
                "success": True,
                "message": "Login successful",
                "redirect": "/dashboard"
            })

        # Normal form login
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


from datetime import datetime

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_logged_in_user()

    now = datetime.now()
    hour = now.hour

    if 5 <= hour < 12:
        greeting = "Good Morning"
    elif 12 <= hour < 17:
        greeting = "Good Afternoon"
    elif 17 <= hour < 21:
        greeting = "Good Evening"
    else:
        greeting = "Good Night"

    current_date = now.strftime("%A, %d %B %Y")
    # Example: Wednesday, 22 July 2026

    return render_template(
        "dashboard.html",
        user=user,
        greeting=greeting,
        current_date=current_date
    )

@app.route("/profile")
@login_required
def profile():
    user = get_logged_in_user()
    return render_template("profile.html", user=user)


@app.route("/graph")
@login_required
def graph():
    user = get_logged_in_user()
    return render_template("graph.html", user=user)


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


@app.route("/settings")
@login_required
def settings():
    user = get_logged_in_user()
    return render_template("settings.html", user=user)


@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "GET":
        if "user_id" not in session:
            return redirect("/login")

        user = get_logged_in_user()
        return render_template("upload.html", user=user)

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
        result = upload_service.upload_file(
            file=file,
            user_id=session["user_id"]
        )
        return jsonify(result), 200

    except upload_service.UploadError as e:
        logger.warning("Upload failed for user %s: %s", session["user_id"], e)
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400

    except Exception as e:
        logger.exception("Unexpected upload error")
        return jsonify({
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        }), 500


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