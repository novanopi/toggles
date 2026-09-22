from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
import secrets
import hashlib
import hmac

app = Flask(__name__)

DATABASE = "toggle.db"

# Set this in Render as an environment variable.
# Example:
# SESSION_SECRET=some-long-random-secret
app.secret_key = os.environ.get("SESSION_SECRET")

if not app.secret_key:
    raise RuntimeError("SESSION_SECRET environment variable is required")


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL,
                password_hash TEXT
            )
        """)

        # Handle databases created by your old version,
        # which don't have password_hash yet.
        columns = conn.execute(
            "PRAGMA table_info(settings)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "password_hash" not in column_names:
            conn.execute(
                "ALTER TABLE settings ADD COLUMN password_hash TEXT"
            )

        conn.execute("""
            INSERT OR IGNORE INTO settings
                (id, enabled, password_hash)
            VALUES
                (1, 0, NULL)
        """)

        conn.commit()


def get_settings():
    with sqlite3.connect(DATABASE) as conn:
        row = conn.execute("""
            SELECT enabled, password_hash
            FROM settings
            WHERE id = 1
        """).fetchone()

        return {
            "enabled": bool(row[0]),
            "password_hash": row[1]
        }


def set_state(enabled):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            UPDATE settings
            SET enabled = ?
            WHERE id = 1
        """, (1 if enabled else 0,))
        conn.commit()


def hash_password(password):
    """
    Hash the password using PBKDF2-HMAC-SHA256.
    A random salt is stored alongside the hash.
    """
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000
    )

    return (
        salt.hex()
        + ":"
        + password_hash.hex()
    )


def verify_password(password, stored_hash):
    try:
        salt_hex, hash_hex = stored_hash.split(":", 1)

        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            600_000
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    except (ValueError, TypeError):
        return False


def set_password(password):
    password_hash = hash_password(password)

    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            UPDATE settings
            SET password_hash = ?
            WHERE id = 1
        """, (password_hash,))
        conn.commit()


def remove_password():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            UPDATE settings
            SET password_hash = NULL
            WHERE id = 1
        """)
        conn.commit()


def password_is_set():
    return get_settings()["password_hash"] is not None


def is_authenticated():
    return session.get("authenticated", False)


init_db()


@app.route("/")
def index():
    settings = get_settings()

    return render_template(
        "index.html",
        enabled=settings["enabled"],
        password_set=settings["password_hash"] is not None,
        authenticated=is_authenticated()
    )


@app.route("/toggle", methods=["POST"])
def toggle():
    settings = get_settings()

    # If a password exists, authentication is required.
    if settings["password_hash"] is not None:
        if not is_authenticated():
            return jsonify({
                "error": "Password required",
                "requires_password": True
            }), 401

    data = request.get_json() or {}

    enabled = bool(data.get("enabled", False))
    set_state(enabled)

    return jsonify({
        "enabled": get_settings()["enabled"]
    })


@app.route("/api/status", methods=["GET"])
def api_status():
    settings = get_settings()

    return jsonify({
        "is_on": settings["enabled"],
        "password_set": settings["password_hash"] is not None,
        "authenticated": is_authenticated()
    })


@app.route("/password/set", methods=["POST"])
def password_set():
    settings = get_settings()

    # Anyone can set the first password.
    # Once a password exists, authentication is required
    # to replace it.
    if settings["password_hash"] is not None:
        if not is_authenticated():
            return jsonify({
                "error": "Authentication required"
            }), 401

    data = request.get_json() or {}
    password = data.get("password", "")

    if not isinstance(password, str) or len(password) < 1:
        return jsonify({
            "error": "Password cannot be empty"
        }), 400

    set_password(password)

    # The person who sets the password is automatically authenticated.
    session["authenticated"] = True

    return jsonify({
        "success": True,
        "password_set": True,
        "authenticated": True
    })


@app.route("/password/login", methods=["POST"])
def password_login():
    settings = get_settings()

    if settings["password_hash"] is None:
        return jsonify({
            "error": "No password is set"
        }), 400

    data = request.get_json() or {}
    password = data.get("password", "")

    if not verify_password(
        password,
        settings["password_hash"]
    ):
        return jsonify({
            "error": "Incorrect password"
        }), 401

    session["authenticated"] = True

    return jsonify({
        "success": True,
        "authenticated": True
    })


@app.route("/password/remove", methods=["POST"])
def password_remove():
    settings = get_settings()

    if settings["password_hash"] is None:
        return jsonify({
            "success": True,
            "password_set": False
        })

    if not is_authenticated():
        return jsonify({
            "error": "Authentication required"
        }), 401

    remove_password()

    session.pop("authenticated", None)

    return jsonify({
        "success": True,
        "password_set": False,
        "authenticated": False
    })


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("authenticated", None)

    return jsonify({
        "success": True,
        "authenticated": False
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
