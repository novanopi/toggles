from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

DATABASE = "toggle.db"


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL
            )
        """)

        conn.execute("""
            INSERT OR IGNORE INTO settings (id, enabled)
            VALUES (1, 0)
        """)

        conn.commit()


def get_state():
    with sqlite3.connect(DATABASE) as conn:
        row = conn.execute(
            "SELECT enabled FROM settings WHERE id = 1"
        ).fetchone()

        return bool(row[0])


def set_state(enabled):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "UPDATE settings SET enabled = ? WHERE id = 1",
            (1 if enabled else 0,)
        )
        conn.commit()


# Initialize the database when Flask/Gunicorn starts
init_db()


@app.route("/")
def index():
    return render_template(
        "index.html",
        enabled=get_state()
    )


@app.route("/toggle", methods=["POST"])
def toggle():
    data = request.get_json() or {}

    enabled = bool(data.get("enabled", False))
    set_state(enabled)

    return jsonify({
        "enabled": get_state()
    })


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "is_on": get_state()
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
