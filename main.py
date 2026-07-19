import os
import psycopg2
from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "digital_identity"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "Ansh@9911"),
    )


def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
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
            conn.commit()
    finally:
        conn.close()


app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
init_db()

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()

    return render_template('index.html',user=user)

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
            conn.close()

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
            conn.close()

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
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id = %s",
        (session["user_id"],)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

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
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()
    
    return render_template("profile.html",user=user)

@app.route('/upload')
def upload():
    if 'user_id' not in session:
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()

    return render_template("upload.html",user=user)

@app.route('/graph')
def graph():
    if 'user_id' not in session:
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()

    return render_template("graph.html",user=user)

@app.route('/search')
def ai_search():
    if 'user_id' not in session:
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()

    return render_template("search.html",user=user)

@app.route('/timeline')
def timeline():
    if 'user_id' not in session:
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()

    return render_template("timeline.html",user=user)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()

    return render_template("settings.html",user=user)

@app.route('/404')
def error():
    if 'user_id' not in session:
        return redirect('home')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cursor.fetchone()
    conn.close()   

    return render_template("404.html",user=user)

if __name__ == '__main__':
    app.run(debug=True)