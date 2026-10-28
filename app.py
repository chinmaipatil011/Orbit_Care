import os
import sqlite3
import secrets
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ORBIT_DB_PATH", os.path.join(BASE_DIR, "orbit_care.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    with connect_db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            category TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open'
              CHECK(status IN ('Open', 'In Progress', 'Resolved')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        # Create a demo admin only if there are no administrator accounts yet.
        if con.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
            username = os.environ.get("ADMIN_USERNAME", "admin")
            password = os.environ.get("ADMIN_PASSWORD", "OrbitDemo2026!")
            con.execute(
                "INSERT INTO admins(username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), now_iso())
            )
        if con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
            examples = [
                ("OC-482193", "Aarav Mehta", "aarav@example.com", "Orders & delivery",
                 "Order delivery is delayed", "My order has not arrived and the estimated delivery date has passed.",
                 "In Progress"),
                ("OC-391725", "Priya Shah", "priya@example.com", "Payments & billing",
                 "Payment was charged twice", "I noticed two charges for the same order. Please verify the duplicate payment.",
                 "Open"),
                ("OC-275640", "Rohan Kulkarni", "rohan@example.com", "Refunds & returns",
                 "Refund status update", "I returned an item and would like to know when the refund will be processed.",
                 "Resolved")
            ]
            for row in examples:
                con.execute("""INSERT INTO tickets
                    (id,name,email,category,subject,description,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (*row, now_iso(), now_iso()))


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Admin login required."}), 401
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


def ticket_dict(row):
    return {
        "id": row["id"], "name": row["name"], "email": row["email"],
        "category": row["category"], "subject": row["subject"],
        "description": row["description"], "status": row["status"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"]
    }


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/customer")
def customer():
    return render_template("index.html")


@app.get("/chat")
def chat():
    return render_template("chat.html")


@app.get("/complaint")
def complaint():
    return render_template("complaint.html")


@app.get("/track")
def track():
    return render_template("track.html")


@app.get("/admin/login")
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin"))
    return render_template("admin_login.html")


@app.post("/admin/login")
def admin_login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    with connect_db() as con:
        row = con.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        session.clear()
        session["admin_id"] = row["id"]
        session["admin_username"] = row["username"]
        return redirect(url_for("admin"))
    return render_template("admin_login.html", error="Invalid username or password."), 401


@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/admin")
@admin_required
def admin():
    return render_template("admin.html", admin_username=session.get("admin_username", "Admin"))


@app.get("/api/tickets")
def api_list_tickets():
    # Public list endpoint returns only tickets for this demo dashboard; edit operations require admin.
    with connect_db() as con:
        rows = con.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
    return jsonify([ticket_dict(row) for row in rows])


@app.post("/api/tickets")
def api_create_ticket():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    category = str(data.get("category", "")).strip()
    subject = str(data.get("subject", "")).strip()
    description = str(data.get("description", "")).strip()
    allowed_categories = {"Orders & delivery", "Payments & billing", "Refunds & returns",
                          "Account access", "Technical issue", "Other"}
    if not name or len(name) > 80:
        return jsonify({"error": "Enter a name (maximum 80 characters)."}), 400
    if len(email) > 120 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return jsonify({"error": "Enter a valid email address."}), 400
    if category not in allowed_categories:
        return jsonify({"error": "Choose a valid complaint category."}), 400
    if not subject or len(subject) > 120:
        return jsonify({"error": "Enter a subject (maximum 120 characters)."}), 400
    if len(description) < 10 or len(description) > 2000:
        return jsonify({"error": "Description must be between 10 and 2000 characters."}), 400
    ticket_id = "OC-" + secrets.token_hex(3).upper()
    created = now_iso()
    with connect_db() as con:
        while con.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone():
            ticket_id = "OC-" + secrets.token_hex(3).upper()
        con.execute("""INSERT INTO tickets
            (id,name,email,category,subject,description,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?, 'Open', ?, ?)""",
            (ticket_id, name, email, category, subject, description, created, created))
        row = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return jsonify(ticket_dict(row)), 201


@app.get("/api/tickets/<ticket_id>")
def api_get_ticket(ticket_id):
    with connect_db() as con:
        row = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id.upper(),)).fetchone()
    if not row:
        return jsonify({"error": "Ticket not found."}), 404
    return jsonify(ticket_dict(row))


@app.patch("/api/tickets/<ticket_id>")
@admin_required
def api_update_ticket(ticket_id):
    data = request.get_json(silent=True) or {}
    fields = {
        "name": (str(data.get("name", "")).strip(), 80),
        "email": (str(data.get("email", "")).strip(), 120),
        "category": (str(data.get("category", "")).strip(), 50),
        "subject": (str(data.get("subject", "")).strip(), 120),
        "description": (str(data.get("description", "")).strip(), 2000),
        "status": (str(data.get("status", "")).strip(), 20)
    }
    allowed_categories = {"Orders & delivery", "Payments & billing", "Refunds & returns",
                          "Account access", "Technical issue", "Other"}
    if any(not value or len(value) > maxlen for value, maxlen in fields.values()):
        return jsonify({"error": "All fields are required and must be within the allowed length."}), 400
    if len(fields["description"][0]) < 10:
        return jsonify({"error": "Description must be at least 10 characters."}), 400
    if "@" not in fields["email"][0] or "." not in fields["email"][0].rsplit("@", 1)[-1]:
        return jsonify({"error": "Enter a valid email address."}), 400
    if fields["category"][0] not in allowed_categories:
        return jsonify({"error": "Invalid category."}), 400
    if fields["status"][0] not in {"Open", "In Progress", "Resolved"}:
        return jsonify({"error": "Invalid status."}), 400
    with connect_db() as con:
        cur = con.execute("""UPDATE tickets SET name=?, email=?, category=?, subject=?,
            description=?, status=?, updated_at=? WHERE id=?""",
            (fields["name"][0], fields["email"][0], fields["category"][0],
             fields["subject"][0], fields["description"][0], fields["status"][0],
             now_iso(), ticket_id.upper()))
        if cur.rowcount == 0:
            return jsonify({"error": "Ticket not found."}), 404
        row = con.execute("SELECT * FROM tickets WHERE id=?", (ticket_id.upper(),)).fetchone()
    return jsonify(ticket_dict(row))


@app.delete("/api/tickets/<ticket_id>")
@admin_required
def api_delete_ticket(ticket_id):
    with connect_db() as con:
        cur = con.execute("DELETE FROM tickets WHERE id=?", (ticket_id.upper(),))
    if cur.rowcount == 0:
        return jsonify({"error": "Ticket not found."}), 404
    return jsonify({"ok": True, "id": ticket_id.upper()})


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "Orbit Care"})


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "5000")))
