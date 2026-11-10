from pathlib import Path
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets
import hmac
import time
from collections import defaultdict, deque
from functools import wraps

app = Flask(__name__)
app.secret_key = Path(".secret_key").read_text().strip()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 1800
DB = "database/boost.db"



@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Login required"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

LOGIN_ATTEMPTS = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300
LOCKOUT_TIME = 300


def login_is_limited(key):
    now = time.time()
    record = LOGIN_ATTEMPTS.get(
        key, {"times": deque(), "blocked_until": 0}
    )

    if now < record["blocked_until"]:
        return True

    while record["times"] and now - record["times"][0] >= LOGIN_WINDOW:
        record["times"].popleft()

    LOGIN_ATTEMPTS[key] = record
    return len(record["times"]) >= MAX_LOGIN_ATTEMPTS


def record_login_failure(key):
    now = time.time()
    record = LOGIN_ATTEMPTS.setdefault(
        key, {"times": deque(), "blocked_until": 0}
    )

    record["times"].append(now)

    if len(record["times"]) >= MAX_LOGIN_ATTEMPTS:
        record["blocked_until"] = now + LOCKOUT_TIME


def init_db():
    conn = sqlite3.connect(DB)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            platform TEXT PRIMARY KEY,
            followers INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS analytics (
            platform TEXT PRIMARY KEY,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0
        )
    """)

    for platform in ["facebook", "tiktok"]:
        conn.execute(
            "INSERT OR IGNORE INTO stats VALUES (?, 0)",
            (platform,)
        )
        conn.execute(
            "INSERT OR IGNORE INTO analytics VALUES (?, 0, 0, 0)",
            (platform,)
        )

    conn.commit()
    conn.close()


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token}


@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        expected = session.get("csrf_token")
        supplied = (
            request.form.get("csrf_token")
            or request.headers.get("X-CSRF-Token")
        )
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            if request.path.startswith("/api/"):
                return jsonify({"error": "CSRF validation failed"}), 400
            return "CSRF validation failed", 400


@app.route("/")
@login_required
def home():
    return render_template("index.html")



@app.route("/api/stats")
@login_required
def get_stats():
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT platform, followers FROM user_stats WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return jsonify({
        p: {"followers": f, "growth": 0}
        for p, f in rows
    })


@app.route("/api/update", methods=["POST"])
@login_required
def update_stats():
    data = request.get_json(silent=True) or {}
    platform = data.get("platform")
    followers = data.get("followers")

    if platform not in ["facebook", "tiktok"]:
        return jsonify({"error": "Invalid platform"}), 400

    if type(followers) is not int or not 0 <= followers <= 1000000000:
        return jsonify({"error": "Invalid followers"}), 400

    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE user_stats SET followers=? WHERE platform=? AND user_id=?",
        (followers, platform, session["user_id"])
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})


@app.route("/api/analytics")
@login_required
def get_analytics():
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """SELECT platform, views, likes, comments
           FROM user_analytics WHERE user_id=?""",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return jsonify({
        p: {"views": v, "likes": l, "comments": c}
        for p, v, l, c in rows
    })


@app.route("/api/analytics/update", methods=["POST"])
@login_required
def update_analytics():
    data = request.get_json(silent=True) or {}
    platform = data.get("platform")

    if platform not in ["facebook", "tiktok"]:
        return jsonify({"error": "Invalid platform"}), 400

    values = []
    for key in ["views", "likes", "comments"]:
        value = data.get(key)
        if type(value) is not int or not 0 <= value <= 1000000000:
            return jsonify({"error": "Invalid " + key}), 400
        values.append(value)

    conn = sqlite3.connect(DB)
    conn.execute("""
        UPDATE user_analytics
        SET views=?, likes=?, comments=?
        WHERE platform=? AND user_id=?
    """, (*values, platform, session["user_id"]))
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})


@app.route("/api/links", methods=["GET", "POST"])
@login_required
def profile_links():
    conn = sqlite3.connect(DB)

    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        for platform in ["facebook", "tiktok"]:
            url = data.get(platform, "")
            if not isinstance(url, str) or len(url) > 500:
                conn.close()
                return jsonify({"error": "Invalid URL"}), 400

            if url and not url.startswith("https://"):
                conn.close()
                return jsonify({"error": "Use HTTPS"}), 400

            conn.execute(
                """INSERT OR REPLACE INTO user_profile_links
                   (user_id, platform, url) VALUES (?, ?, ?)""",
                (session["user_id"], platform, url)
            )

        conn.commit()

    rows = conn.execute(
        """SELECT platform, url FROM user_profile_links
           WHERE user_id=?""",
        (session["user_id"],)
    ).fetchall()

    conn.close()
    return jsonify(dict(rows))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not (3 <= len(username) <= 20 and
                all(c.isalnum() or c == "_" for c in username)):
            return "Username must be 3-20 letters, numbers or underscores", 400

        if len(password) < 10:
            return "Password must be at least 10 characters", 400

        conn = sqlite3.connect(DB)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            user_id = cur.lastrowid

            for platform in ["facebook", "tiktok"]:
                if count == 0:
                    old_stats = conn.execute(
                        "SELECT followers FROM stats WHERE platform=?",
                        (platform,)
                    ).fetchone()
                    old_analytics = conn.execute(
                        "SELECT views, likes, comments FROM analytics WHERE platform=?",
                        (platform,)
                    ).fetchone()
                    old_link = conn.execute(
                        "SELECT url FROM profile_links WHERE platform=?",
                        (platform,)
                    ).fetchone()

                    followers = old_stats[0] if old_stats else 0
                    analytics = old_analytics or (0, 0, 0)
                    url = old_link[0] if old_link else ""
                else:
                    followers = 0
                    analytics = (0, 0, 0)
                    url = ""

                conn.execute(
                    "INSERT INTO user_stats VALUES (?, ?, ?)",
                    (user_id, platform, followers)
                )
                conn.execute(
                    "INSERT INTO user_analytics VALUES (?, ?, ?, ?, ?)",
                    (user_id, platform, *analytics)
                )
                conn.execute(
                    "INSERT INTO user_profile_links VALUES (?, ?, ?)",
                    (user_id, platform, url)
                )

            conn.commit()
            session.clear()
            session["user_id"] = user_id
            session["username"] = username
            return redirect(url_for("home"))

        except sqlite3.IntegrityError:
            conn.rollback()
            return "Username already exists", 409
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        key = (request.remote_addr or "unknown", username.lower())

        if login_is_limited(key):
            return "Too many login attempts. Try again in 5 minutes.", 429

        conn = sqlite3.connect(DB)
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            LOGIN_ATTEMPTS.pop(key, None)
            session.clear()
            session.permanent = True
            session["user_id"] = user[0]
            session["username"] = username
            return redirect(url_for("home"))

        record_login_failure(key)
        return "Invalid username or password", 401

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    print("BOOSTER PRO ONLINE")
    app.run(host="0.0.0.0", port=5000)
