from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

imports_anchor = "from flask_wtf.csrf import CSRFProtect\n"
imports_patch = (
    "from flask_wtf.csrf import CSRFProtect\n"
    "from authlib.integrations.flask_client import OAuth\n"
    "from authlib.integrations.base_client.errors import OAuthError\n"
)
if "from authlib.integrations.flask_client import OAuth" not in text:
    if imports_anchor not in text:
        raise SystemExit("Could not find Flask-WTF import anchor")
    text = text.replace(imports_anchor, imports_patch, 1)

csrf_anchor = "csrf = CSRFProtect(app)\n\n"
oauth_block = '''csrf = CSRFProtect(app)\n\nGOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()\nGOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()\nPUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")\n\noauth = OAuth(app)\ngoogle_oauth = None\nif GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:\n    google_oauth = oauth.register(\n        name="google",\n        client_id=GOOGLE_CLIENT_ID,\n        client_secret=GOOGLE_CLIENT_SECRET,\n        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",\n        client_kwargs={"scope": "openid email profile"},\n    )\n\n\ndef google_callback_uri():\n    configured = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()\n    if configured:\n        return configured\n    if PUBLIC_BASE_URL:\n        return f"{PUBLIC_BASE_URL}/auth/google/callback"\n    return url_for("google_callback", _external=True)\n\n\n@app.context_processor\ndef inject_oauth_flags():\n    return {"google_oauth_enabled": google_oauth is not None}\n\n'''
if "GOOGLE_CLIENT_ID = os.environ.get" not in text:
    if csrf_anchor not in text:
        raise SystemExit("Could not find CSRF anchor")
    text = text.replace(csrf_anchor, oauth_block, 1)

login_anchor = '@app.route("/login", methods=["GET", "POST"])\ndef login():\n'
oauth_routes = '''@app.route("/auth/google")\ndef google_login():\n    if google_oauth is None:\n        flash("Google sign-in is not configured yet.", "warning")\n        return redirect(url_for("login"))\n    redirect_uri = google_callback_uri()\n    return google_oauth.authorize_redirect(redirect_uri, prompt="select_account")\n\n\n@app.route("/auth/google/callback")\ndef google_callback():\n    if google_oauth is None:\n        flash("Google sign-in is not configured yet.", "warning")\n        return redirect(url_for("login"))\n    try:\n        token = google_oauth.authorize_access_token()\n        userinfo = token.get("userinfo")\n        if not userinfo:\n            userinfo = google_oauth.userinfo(token=token)\n    except OAuthError as exc:\n        print("Google OAuth error:", exc)\n        flash("Google sign-in could not be completed. Please try again.", "danger")\n        return redirect(url_for("login"))\n    except Exception as exc:\n        print("Google OAuth callback warning:", exc)\n        flash("Google sign-in failed unexpectedly. Please try again.", "danger")\n        return redirect(url_for("login"))\n\n    email = str(userinfo.get("email", "")).strip().lower()\n    name = str(userinfo.get("name", "")).strip() or (email.split("@", 1)[0] if email else "Google User")\n    if not email:\n        flash("Google did not provide an email address for this account.", "danger")\n        return redirect(url_for("login"))\n    if "email_verified" in userinfo and not userinfo.get("email_verified"):\n        flash("Please verify your Google email address before signing in.", "danger")\n        return redirect(url_for("login"))\n\n    users = load_users()\n    user_match = next((u for u in users if u.get("email", "").lower() == email), None)\n    if user_match and user_match.get("is_active") is False:\n        flash("This account has been disabled by an administrator.", "danger")\n        return redirect(url_for("login"))\n\n    if not user_match:\n        role = "Admin" if not users else "Student"\n        # Store an unusable random hash so OAuth-only accounts cannot log in with a guessed password.\n        password_hash = generate_password_hash(secrets.token_urlsafe(48))\n        save_user({"name": name, "email": email, "password": password_hash, "role": role})\n        if db_enabled():\n            increment_metric("registrations")\n        user_match = {"name": name, "email": email, "role": role, "is_active": True}\n\n    session.clear()\n    session.permanent = True\n    session["user"] = {\n        "name": user_match.get("name") or name,\n        "email": email,\n        "role": user_match.get("role", "Student"),\n    }\n    if db_enabled():\n        touch_login(email)\n        increment_metric("logins")\n    flash(f"Welcome, {session['user']['name']}! Signed in with Google.", "success")\n    return redirect(url_for("dashboard"))\n\n\n@app.route("/login", methods=["GET", "POST"])\ndef login():\n'''
if '@app.route("/auth/google")' not in text:
    if login_anchor not in text:
        raise SystemExit("Could not find login route anchor")
    text = text.replace(login_anchor, oauth_routes, 1)

path.write_text(text, encoding="utf-8")
print("Google OAuth patch applied")
