from flask import Flask, render_template, request, jsonify, session
import sqlite3

app = Flask(__name__)

DATABASE = "toggle.db"

# Used to sign the Flask session cookie.
# Change this to any random string you want.
app.secret_key = "change-this-to-a-random-secret-key"


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL,
                password TEXT
            )
        """)

        # Handle an existing database created by the old version.
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(settings)").fetchall()
        ]

        if "password" not in columns:
            conn.execute(
                "ALTER TABLE settings ADD COLUMN password TEXT"
            )

        conn.execute("""
            INSERT OR IGNORE INTO settings (id, enabled, password)
            VALUES (1, 0, NULL)
        """)

        conn.commit()


def get_settings():
    with sqlite3.connect(DATABASE) as conn:
        row = conn.execute("""
            SELECT enabled, password
            FROM settings
            WHERE id = 1
        """).fetchone()

        return {
            "enabled": bool(row[0]),
            "password": row[1]
        }


def get_state():
    return get_settings()["enabled"]


def set_state(enabled):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "UPDATE settings SET enabled = ? WHERE id = 1",
            (1 if enabled else 0,)
        )
        conn.commit()


def set_password(password):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "UPDATE settings SET password = ? WHERE id = 1",
            (password,)
        )
        conn.commit()


def remove_password():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "UPDATE settings SET password = NULL WHERE id = 1"
        )
        conn.commit()


def password_required():
    return get_settings()["password"] is not None


def is_authenticated():
    return session.get("toggle_authenticated", False)


init_db()


@app.route("/")
def index():
    settings = get_settings()

    return render_template(
        "index.html",
        enabled=settings["enabled"],
        password_set=settings["password"] is not None,
        authenticated=is_authenticated()
    )


@app.route("/toggle", methods=["POST"])
def toggle():
    data = request.get_json() or {}

    settings = get_settings()

    # If a password exists, authentication is required.
    if settings["password"] is not None and not is_authenticated():
        return jsonify({
            "error": "password_required"
        }), 403

    enabled = bool(data.get("enabled", False))
    set_state(enabled)

    return jsonify({
        "enabled": get_state()
    })


@app.route("/api/status", methods=["GET"])
def api_status():
    settings = get_settings()

    return jsonify({
        "is_on": settings["enabled"],
        "password_set": settings["password"] is not None,
        "authenticated": is_authenticated()
    })


@app.route("/password/set", methods=["POST"])
def password_set():
    data = request.get_json() or {}

    password = data.get("password")

    if not password:
        return jsonify({
            "error": "Password cannot be empty"
        }), 400

    settings = get_settings()

    # You can only set a password if one isn't already set.
    if settings["password"] is not None:
        return jsonify({
            "error": "A password is already set"
        }), 403

    set_password(password)

    # Whoever sets the password is automatically authenticated.
    session["toggle_authenticated"] = True

    return jsonify({
        "success": True,
        "password_set": True,
        "authenticated": True
    })


@app.route("/password/unlock", methods=["POST"])
def password_unlock():
    data = request.get_json() or {}

    password = data.get("password", "")
    settings = get_settings()

    if settings["password"] is None:
        return jsonify({
            "success": True,
            "authenticated": True
        })

    if password != settings["password"]:
        return jsonify({
            "success": False,
            "error": "Incorrect password"
        }), 401

    session["toggle_authenticated"] = True

    return jsonify({
        "success": True,
        "authenticated": True
    })


@app.route("/password/remove", methods=["POST"])
def password_remove():
    data = request.get_json() or {}

    settings = get_settings()

    if settings["password"] is None:
        return jsonify({
            "success": True
        })

    # Removing the password requires authentication.
    if not is_authenticated():
        return jsonify({
            "error": "password_required"
        }), 403

    password = data.get("password", "")

    if password != settings["password"]:
        return jsonify({
            "success": False,
            "error": "Incorrect password"
        }), 401

    remove_password()

    session["toggle_authenticated"] = False

    return jsonify({
        "success": True,
        "password_set": False,
        "authenticated": False
    })


@app.route("/password/logout", methods=["POST"])
def password_logout():
    session["toggle_authenticated"] = False

    return jsonify({
        "success": True
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
