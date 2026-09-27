import os
import re

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    abort,
)
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = os.environ["FLASK_SECRET_KEY"]

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)


USERNAME_RE = re.compile(r"^[a-z0-9_-]{2,50}$")

RESERVED_USERNAMES = {
    "api",
    "static",
    "password",
    "toggle",
    "gag",
    "favicon.ico",
}


def normalize_username(username):
    return (username or "").strip().lower()


def valid_username(username):
    username = normalize_username(username)

    if username in RESERVED_USERNAMES:
        return False

    return bool(USERNAME_RE.fullmatch(username))


def get_account(username):
    username = normalize_username(username)

    if not valid_username(username):
        return None

    response = (
        supabase
        .table("accounts")
        .select("*")
        .eq("username", username)
        .maybe_single()
        .execute()
    )

    return response.data


def update_account(username, values):
    username = normalize_username(username)

    if not valid_username(username):
        return

    (
        supabase
        .table("accounts")
        .update(values)
        .eq("username", username)
        .execute()
    )


def auth_key(username):
    return f"authenticated_{normalize_username(username)}"


def is_authenticated(username):
    return bool(session.get(auth_key(username), False))


def account_payload(username, account=None):
    account = account or get_account(username)

    if not account:
        return None

    return {
        "username": account["username"],
        "title": account.get("title") or account["username"].capitalize(),
        "enabled": bool(account.get("enabled", False)),
        "gagged": bool(account.get("gagged", False)),
        "show_toggle": bool(account.get("show_toggle", False)),
        "password_set": account.get("password") is not None,
        "authenticated": is_authenticated(username),
    }


def check_unlocked(account):
    if account.get("password") is None:
        return True

    return is_authenticated(account["username"])


def payload_username_matches(payload, username):
    requested_username = normalize_username(payload.get("username", ""))

    if not requested_username:
        return True

    return requested_username == normalize_username(username)


@app.route("/")
def home():
    return redirect(url_for("account_page", username="main"))


@app.route("/<username>")
def account_page(username):
    account = get_account(username)

    if not account:
        abort(404)

    data = account_payload(username, account)

    return render_template(
        "account.html",
        account=data,
    )


@app.route("/api/<username>/status")
def api_status(username):
    data = account_payload(username)

    if data is None:
        return jsonify({"error": "not_found"}), 404

    return jsonify(data)


@app.route("/api/<username>/toggle", methods=["POST"])
def api_toggle(username):
    account = get_account(username)

    if not account:
        return jsonify({"error": "not_found"}), 404

    if not check_unlocked(account):
        return jsonify({"error": "password_required"}), 403

    payload = request.get_json(silent=True) or {}

    enabled = bool(
        payload.get(
            "enabled",
            not bool(account.get("enabled", False)),
        )
    )

    update_account(username, {"enabled": enabled})

    return jsonify({
        "success": True,
        "username": normalize_username(username),
        "enabled": enabled,
    })


@app.route("/api/<username>/gag", methods=["POST"])
def api_gag(username):
    account = get_account(username)

    if not account:
        return jsonify({"error": "not_found"}), 404

    if not check_unlocked(account):
        return jsonify({"error": "password_required"}), 403

    payload = request.get_json(silent=True) or {}

    gagged = bool(
        payload.get(
            "gagged",
            not bool(account.get("gagged", False)),
        )
    )

    update_account(username, {"gagged": gagged})

    return jsonify({
        "success": True,
        "username": normalize_username(username),
        "gagged": gagged,
    })


@app.route("/api/<username>/password/set", methods=["POST"])
def api_password_set(username):
    account = get_account(username)

    if not account:
        return jsonify({"error": "not_found"}), 404

    payload = request.get_json(silent=True) or {}

    if not payload_username_matches(payload, username):
        return jsonify({
            "success": False,
            "error": "Invalid username",
        }), 400

    password = payload.get("password")

    if not password:
        return jsonify({
            "success": False,
            "error": "Password cannot be empty",
        }), 400

    if account.get("password") is not None:
        return jsonify({
            "success": False,
            "error": "A password is already set",
        }), 403

    update_account(username, {
        "password": generate_password_hash(password),
    })

    session[auth_key(username)] = True

    return jsonify({
        "success": True,
        "username": normalize_username(username),
        "password_set": True,
        "authenticated": True,
    })


@app.route("/api/<username>/password/unlock", methods=["POST"])
def api_password_unlock(username):
    account = get_account(username)

    if not account:
        return jsonify({"error": "not_found"}), 404

    payload = request.get_json(silent=True) or {}

    if not payload_username_matches(payload, username):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password",
        }), 401

    password = payload.get("password", "")

    if account.get("password") is None:
        session[auth_key(username)] = True

        return jsonify({
            "success": True,
            "username": normalize_username(username),
            "password_set": False,
            "authenticated": True,
        })

    if not check_password_hash(account["password"], password):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password",
        }), 401

    session[auth_key(username)] = True

    return jsonify({
        "success": True,
        "username": normalize_username(username),
        "password_set": True,
        "authenticated": True,
    })


@app.route("/api/<username>/password/remove", methods=["POST"])
def api_password_remove(username):
    account = get_account(username)

    if not account:
        return jsonify({"error": "not_found"}), 404

    if account.get("password") is None:
        session[auth_key(username)] = False

        return jsonify({
            "success": True,
            "username": normalize_username(username),
            "password_set": False,
            "authenticated": False,
        })

    if not is_authenticated(username):
        return jsonify({
            "success": False,
            "error": "password_required",
        }), 403

    payload = request.get_json(silent=True) or {}

    if not payload_username_matches(payload, username):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password",
        }), 401

    password = payload.get("password", "")

    if password and not check_password_hash(account["password"], password):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password",
        }), 401

    update_account(username, {"password": None})

    session[auth_key(username)] = False

    return jsonify({
        "success": True,
        "username": normalize_username(username),
        "password_set": False,
        "authenticated": False,
    })


@app.route("/api/<username>/password/logout", methods=["POST"])
def api_password_logout(username):
    account = get_account(username)

    if not account:
        return jsonify({"error": "not_found"}), 404

    session[auth_key(username)] = False

    return jsonify({
        "success": True,
        "username": normalize_username(username),
        "authenticated": False,
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
