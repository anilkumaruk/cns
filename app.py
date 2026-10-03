"""
app.py - Flask web interface for the Secure Password Storage System.

Run:  python app.py      then open  http://127.0.0.1:5000
Host: gunicorn app:app   with the SECRET_KEY environment variable set
"""

import hmac
import os

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)

from secure_store import UserStore

app = Flask(__name__)
# When hosted, SECRET_KEY is set as an environment variable so the session
# cookie stays valid across restarts; locally a random key is generated.
DEPLOYED = bool(os.environ.get("SECRET_KEY"))
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=DEPLOYED)   # HTTPS-only cookie when hosted
app.jinja_env.globals["public_demo"] = DEPLOYED
store = UserStore(os.environ.get("USERS_DB") or
                  os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db"))


# ------------------------------------------------------- CSRF protection --

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = os.urandom(16).hex()
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf", "")
        if not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Invalid form token.")


# ----------------------------------------------------------------- routes --

@app.route("/")
def home():
    return render_template("home.html", count=len(store.list_users()))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if password != request.form.get("confirm", ""):
            flash("Passwords do not match.", "error")
        else:
            ok, message = store.register(username, password)
            flash(message, "success" if ok else "error")
            if ok:
                return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if store.verify(username, request.form.get("password", "")):
            session.clear()                  # new session after login
            session["user"] = username
            return redirect(url_for("dashboard"))
        # same message for unknown user and wrong password
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))
    record = next(u for u in store.list_users() if u["username"] == session["user"])
    return render_template("dashboard.html", record=record)


@app.route("/records")
def records():
    """Shows exactly what an attacker would get from a stolen database."""
    return render_template("records.html", users=store.list_users())


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
