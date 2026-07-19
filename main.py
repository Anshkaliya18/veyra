import os
import sqlite3
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
db_pool = None

# Database wrapper to allow running with PostgreSQL (via DATABASE_URL)
# or falling back to a local SQLite DB for easy local development.
DB_TYPE = None


class CursorWrapper:
    def __init__(self, cursor, db_type):
        self._cursor = cursor
        self._db_type = db_type

    def execute(self, query, params=()):
        if self._db_type == 'sqlite':
            query = query.replace('%s', '?')
        return self._cursor.execute(query, params)

    def executemany(self, query, seq_of_params):
        if self._db_type == 'sqlite':
            query = query.replace('%s', '?')
        return self._cursor.executemany(query, seq_of_params)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class ConnectionWrapper:
    def __init__(self, conn, db_type):
        self._conn = conn
        self._db_type = db_type

    def cursor(self):
        return CursorWrapper(self._conn.cursor(), self._db_type)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db_connection():
    global DB_TYPE, db_pool

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        DB_TYPE = "postgres"

        if db_pool is None:
            db_pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=database_url
            )

        return db_pool.getconn()

    DB_TYPE = "sqlite"

    sqlite_path = os.path.join(
        os.path.dirname(__file__),
        "veyra.db"
    )

    conn = sqlite3.connect(
        sqlite_path,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return ConnectionWrapper(conn, DB_TYPE)

def release_db_connection(conn):
    global DB_TYPE

    if DB_TYPE == "postgres":
        db_pool.putconn(conn)
    else:
        conn.close()

def get_logged_in_user():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT * FROM users WHERE id=%s",
            (session["user_id"],)
        )
        return cursor.fetchone()

    finally:
        cursor.close()
        release_db_connection(conn)

def init_db():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if DB_TYPE == 'postgres':
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    firstName TEXT NOT NULL,
                    lastName TEXT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            # sqlite
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    firstName TEXT NOT NULL,
                    lastName TEXT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()
    finally:
        release_db_connection(conn)


app = Flask(__name__, static_folder='.', static_url_path='')
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
init_db()

@app.route('/')
def home():
    # If logged in, send to dashboard; otherwise show public index page
    if 'user_id' in session:
        return redirect('/dashboard')

    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form.get('name', '').strip()
        first_name = request.form.get('firstName', '').strip()
        last_name = request.form.get('lastName', '').strip()

        if full_name and not first_name:
            name_parts = full_name.split(maxsplit=1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmPassword', password)

        if not first_name or not email or not password:
            return jsonify({'error': 'Please fill in all fields'}), 400

        if password != confirm_password:
            return jsonify({'error': "Passwords don't match"}), 400

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cursor.fetchone():
                return jsonify({'error': 'Email already registered'}), 400

            cursor.execute(
                """
                INSERT INTO users (firstName, lastName, email, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (first_name, last_name, email, hashed_password),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            return jsonify({'error': str(exc)}), 500
        finally:
            cursor.close()
            release_db_connection(conn)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect': '/login'}), 200

        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            return jsonify({'error': 'Please enter email and password'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT id,
                       firstName,
                       lastName,
                       email,
                       password_hash
                FROM users
                WHERE email = %s
            """, (email,))

            user = cursor.fetchone()

            if not user:
                return jsonify({'error': 'Invalid email or password'}), 401

            user_id = user[0]
            first_name = user[1]
            last_name = user[2]
            user_email = user[3]
            password_hash = user[4]

            if not check_password_hash(password_hash, password):
                return jsonify({'error': 'Invalid email or password'}), 401

            # Login successful
            session['user_id'] = user_id
            session['firstName'] = first_name
            session['lastName'] = last_name
            session['email'] = user_email

        except Exception as e:

            return jsonify({'error': str(e)}), 500

        finally:

            cursor.close()
            release_db_connection(conn)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'redirect': '/dashboard'
            }), 200

        return redirect('/dashboard')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()

    today = datetime.now()
    hour = today.hour

    if 5 <= hour < 12:
        greeting = "Good Morning"

    elif 12 <= hour < 17:
        greeting = "Good Afternoon"

    elif 17 <= hour < 21:
        greeting = "Good Evening"

    else:
        greeting = "Good Night"

    return render_template(
        "dashboard.html",
        user=user,
        greeting=greeting,
        current_day=today.strftime("%A"),
        current_date=today.strftime("%d %B %Y"),
        current_time=today.strftime("%I:%M %p")
    )

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()
    
    return render_template("profile.html",user=user)

@app.route('/upload')
def upload():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()

    return render_template("upload.html",user=user)

@app.route('/graph')
def graph():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()

    return render_template("graph.html",user=user)

@app.route('/search')
def ai_search():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()

    return render_template("search.html",user=user)

@app.route('/timeline')
def timeline():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()

    return render_template("timeline.html",user=user)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()

    return render_template("settings.html",user=user)

@app.route('/404')
def error():
    if 'user_id' not in session:
        return redirect('/')

    user = get_logged_in_user()

    return render_template("404.html",user=user)

if __name__ == '__main__':
    app.run(debug=True)