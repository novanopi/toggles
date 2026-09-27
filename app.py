import os

from flask import Flask, render_template, request, jsonify, session
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash



app = Flask(__name__)

# Persistent Flask session signing key.
# Set this in Render environment variables.
app.secret_key = os.environ["FLASK_SECRET_KEY"]

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# Supabase configuration.
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)


def get_settings():
    response = (
        supabase
        .table("settings")
        .select("""
            enabled,
            password,
            gagged,
            lily_gagged,
            lily_password,
            wife_gagged,
            wife_password
        """)
        .eq("id", 1)
        .single()
        .execute()
    )

    row = response.data

    return {
        "enabled": bool(row["enabled"]),
        "password": row["password"],
        "gagged": bool(row["gagged"]),
        "lily_gagged": bool(row["lily_gagged"]),
        "lily_password": row["lily_password"],
        "wife_gagged": bool(row["wife_gagged"]),
        "wife_password": row["wife_password"]
    }


# ============================================================
# ORIGINAL WEBSITE
# ============================================================

def get_state():
    return get_settings()["enabled"]


def set_state(enabled):
    (
        supabase
        .table("settings")
        .update({"enabled": bool(enabled)})
        .eq("id", 1)
        .execute()
    )


def set_gagged(gagged):
    (
        supabase
        .table("settings")
        .update({"gagged": bool(gagged)})
        .eq("id", 1)
        .execute()
    )


def set_password(password):
    password_hash = generate_password_hash(password)
    (
        supabase
        .table("settings")
        .update({"password": password_hash})
        .eq("id", 1)
        .execute()
    )


def remove_password():
    (
        supabase
        .table("settings")
        .update({"password": None})
        .eq("id", 1)
        .execute()
    )


def is_authenticated():
    return session.get("toggle_authenticated", False)


@app.route("/")
def index():
    settings = get_settings()

    return render_template(
        "index.html",
        enabled=settings["enabled"],
        gagged=settings["gagged"],
        password_set=settings["password"] is not None,
        authenticated=is_authenticated()
    )


@app.route("/toggle", methods=["POST"])
def toggle():
    data = request.get_json() or {}

    settings = get_settings()

    if settings["password"] is not None and not is_authenticated():
        return jsonify({
            "error": "password_required"
        }), 403

    enabled = bool(data.get("enabled", False))
    set_state(enabled)

    return jsonify({
        "is_forced_ctrlem": get_state()
    })


@app.route("/gag", methods=["POST"])
def gag():
    data = request.get_json() or {}

    settings = get_settings()

    if settings["password"] is not None and not is_authenticated():
        return jsonify({
            "error": "password_required"
        }), 403

    gagged = bool(data.get("gagged", False))
    set_gagged(gagged)

    return jsonify({
        "is_gagged": get_gagged()
    })


@app.route("/api/status", methods=["GET"])
def api_status():
    settings = get_settings()

    return jsonify({
        "is_forced_ctrlem": settings["enabled"],
        "is_gagged": settings["gagged"],
        "password_set": settings["password"] is not None,
        "authenticated": is_authenticated()
    })


@app.route("/password/set", methods=["POST"])
def password_set():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password")

    if username != "main":
        return jsonify({
            "error": "Invalid username"
        }), 400

    if not password:
        return jsonify({
            "error": "Password cannot be empty"
        }), 400

    settings = get_settings()

    if settings["password"] is not None:
        return jsonify({
            "error": "A password is already set"
        }), 403

    set_password(password)

    session["toggle_authenticated"] = True

    return jsonify({
        "success": True,
        "username": "main",
        "password_set": True,
        "authenticated": True
    })


@app.route("/password/unlock", methods=["POST"])
def password_unlock():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password", "")
    settings = get_settings()

    if username != "main":
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    if settings["password"] is None:
        session["toggle_authenticated"] = True

        return jsonify({
            "success": True,
            "username": "main",
            "authenticated": True
        })

    if not check_password_hash(settings["password"], password):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    session["toggle_authenticated"] = True

    return jsonify({
        "success": True,
        "username": "main",
        "authenticated": True
    })



@app.route("/password/remove", methods=["POST"])
def password_remove():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password", "")

    settings = get_settings()

    if settings["password"] is None:
        return jsonify({
            "success": True
        })

    if not is_authenticated():
        return jsonify({
            "error": "password_required"
        }), 403

    if username != "main":
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    if not check_password_hash(settings["password"], password):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
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


# ============================================================
# LILY WEBSITE
# ============================================================

def get_lily_gagged():
    return get_settings()["lily_gagged"]


def set_lily_gagged(gagged):
    (
        supabase
        .table("settings")
        .update({"lily_gagged": bool(gagged)})
        .eq("id", 1)
        .execute()
    )


def set_lily_password(password):
    password_hash = generate_password_hash(password)
    (
        supabase
        .table("settings")
        .update({"lily_password": password_hash})
        .eq("id", 1)
        .execute()
    )


def remove_lily_password():
    (
        supabase
        .table("settings")
        .update({"lily_password": None})
        .eq("id", 1)
        .execute()
    )


def is_lily_authenticated():
    return session.get("lily_authenticated", False)


@app.route("/lily")
def lily():
    settings = get_settings()

    return render_template(
        "lily.html",
        gagged=settings["lily_gagged"],
        password_set=settings["lily_password"] is not None,
        authenticated=is_lily_authenticated()
    )


@app.route("/lily/gag", methods=["POST"])
def lily_gag():
    data = request.get_json() or {}

    settings = get_settings()

    if (
        settings["lily_password"] is not None
        and not is_lily_authenticated()
    ):
        return jsonify({
            "error": "password_required"
        }), 403

    gagged = bool(data.get("gagged", False))

    set_lily_gagged(gagged)

    return jsonify({
        "success": True,
        "is_gagged": get_lily_gagged()
    })


@app.route("/api/lily/status", methods=["GET"])
def lily_api_status():
    settings = get_settings()

    return jsonify({
        "is_gagged": settings["lily_gagged"],
        "password_set": settings["lily_password"] is not None,
        "authenticated": is_lily_authenticated()
    })


@app.route("/lily/password/set", methods=["POST"])
def lily_password_set():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password")

    if username != "lily":
        return jsonify({
            "success": False,
            "error": "Invalid username"
        }), 400

    if not password:
        return jsonify({
            "success": False,
            "error": "Password cannot be empty"
        }), 400

    settings = get_settings()

    if settings["lily_password"] is not None:
        return jsonify({
            "success": False,
            "error": "A password is already set"
        }), 403

    set_lily_password(password)

    session["lily_authenticated"] = True

    return jsonify({
        "success": True,
        "username": "lily",
        "password_set": True,
        "authenticated": True
    })


@app.route("/lily/password/unlock", methods=["POST"])
@app.route("/lily/password/unlock", methods=["POST"])
def lily_password_unlock():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password", "")
    settings = get_settings()

    if username != "lily":
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    if settings["lily_password"] is None:
        session["lily_authenticated"] = True

        return jsonify({
            "success": True,
            "username": "lily",
            "password_set": False,
            "authenticated": True
        })

    if not check_password_hash(
        settings["lily_password"],
        password
    ):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    session["lily_authenticated"] = True

    return jsonify({
        "success": True,
        "username": "lily",
        "password_set": True,
        "authenticated": True
    })



@app.route("/lily/password/remove", methods=["POST"])
def lily_password_remove():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password", "")

    settings = get_settings()

    if settings["lily_password"] is None:
        return jsonify({
            "success": True,
            "password_set": False,
            "authenticated": False
        })

    if not is_lily_authenticated():
        return jsonify({
            "success": False,
            "error": "password_required"
        }), 403

    if username != "lily":
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    if not check_password_hash(settings["lily_password"], password):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    remove_lily_password()

    session["lily_authenticated"] = False

    return jsonify({
        "success": True,
        "password_set": False,
        "authenticated": False
    })


@app.route("/lily/password/logout", methods=["POST"])
def lily_password_logout():
    session["lily_authenticated"] = False

    return jsonify({
        "success": True,
        "authenticated": False
    })


# ============================================================
# WIFE WEBSITE
# ============================================================

def get_wife_gagged():
    return get_settings()["wife_gagged"]


def set_wife_gagged(gagged):
    (
        supabase
        .table("settings")
        .update({"wife_gagged": bool(gagged)})
        .eq("id", 1)
        .execute()
    )


def set_wife_password(password):
    password_hash = generate_password_hash(password)
    (
        supabase
        .table("settings")
        .update({"wife_password": password_hash})
        .eq("id", 1)
        .execute()
    )



def remove_wife_password():
    (
        supabase
        .table("settings")
        .update({"wife_password": None})
        .eq("id", 1)
        .execute()
    )


def is_wife_authenticated():
    return session.get("wife_authenticated", False)


@app.route("/wife")
def wife():
    settings = get_settings()

    return render_template(
        "wife.html",
        gagged=settings["wife_gagged"],
        password_set=settings["wife_password"] is not None,
        authenticated=is_wife_authenticated()
    )


@app.route("/wife/gag", methods=["POST"])
def wife_gag():
    data = request.get_json() or {}

    settings = get_settings()

    if (
        settings["wife_password"] is not None
        and not is_wife_authenticated()
    ):
        return jsonify({
            "error": "password_required"
        }), 403

    gagged = bool(data.get("gagged", False))

    set_wife_gagged(gagged)

    return jsonify({
        "success": True,
        "is_gagged": get_wife_gagged()
    })


@app.route("/api/wife/status", methods=["GET"])
def wife_api_status():
    settings = get_settings()

    return jsonify({
        "is_gagged": settings["wife_gagged"],
        "password_set": settings["wife_password"] is not None,
        "authenticated": is_wife_authenticated()
    })


@app.route("/wife/password/set", methods=["POST"])
def wife_password_set():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password")

    if username != "wife":
        return jsonify({
            "success": False,
            "error": "Invalid username"
        }), 400

    if not password:
        return jsonify({
            "success": False,
            "error": "Password cannot be empty"
        }), 400

    settings = get_settings()

    if settings["wife_password"] is not None:
        return jsonify({
            "success": False,
            "error": "A password is already set"
        }), 403

    set_wife_password(password)

    session["wife_authenticated"] = True

    return jsonify({
        "success": True,
        "username": "wife",
        "password_set": True,
        "authenticated": True
    })


@app.route("/wife/password/unlock", methods=["POST"])
def wife_password_unlock():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password", "")
    settings = get_settings()

    if username != "wife":
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    if settings["wife_password"] is None:
        session["wife_authenticated"] = True

        return jsonify({
            "success": True,
            "username": "wife",
            "password_set": False,
            "authenticated": True
        })

    if not check_password_hash(
        settings["wife_password"],
        password
    ):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    session["wife_authenticated"] = True


    return jsonify({
        "success": True,
        "username": "wife",
        "password_set": True,
        "authenticated": True
    })


@app.route("/wife/password/remove", methods=["POST"])
def wife_password_remove():
    data = request.get_json() or {}

    username = data.get("username", "")
    password = data.get("password", "")

    settings = get_settings()

    if settings["wife_password"] is None:
        return jsonify({
            "success": True,
            "password_set": False,
            "authenticated": False
        })

    if not is_wife_authenticated():
        return jsonify({
            "success": False,
            "error": "password_required"
        }), 403

    if username != "wife":
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    if not check_password_hash(settings["wife_password"], password):
        return jsonify({
            "success": False,
            "error": "Incorrect username or password"
        }), 401

    remove_wife_password()

    session["wife_authenticated"] = False

    return jsonify({
        "success": True,
        "password_set": False,
        "authenticated": False
    })


@app.route("/wife/password/logout", methods=["POST"])
def wife_password_logout():
    session["wife_authenticated"] = False

    return jsonify({
        "success": True,
        "authenticated": False
    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
