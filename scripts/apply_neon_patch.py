from pathlib import Path

app_path = Path('app.py')
app = app_path.read_text(encoding='utf-8')


def repl(old, new):
    global app
    if old not in app:
        raise SystemExit('Patch anchor not found: ' + old[:100])
    app = app.replace(old, new, 1)


repl('import json\n', 'import hashlib\nimport json\n')
repl(
    'from werkzeug.security import check_password_hash, generate_password_hash\n',
    'from werkzeug.middleware.proxy_fix import ProxyFix\nfrom werkzeug.security import check_password_hash, generate_password_hash\n',
)
repl(
    'from prediction.report_generator import ReportGenerator\n',
    '''from prediction.report_generator import ReportGenerator\nfrom db_store import (\n    admin_snapshot, create_user as db_create_user, db_enabled, ensure_admin, fetch_history,\n    fetch_users, increment_metric, record_request, save_history, set_user_active,\n    set_user_role, touch_login,\n)\n''',
)
repl(
    '    WTF_CSRF_TIME_LIMIT=None,\n)',
    '    WTF_CSRF_TIME_LIMIT=None,\n    WTF_CSRF_SSL_STRICT=False,\n)\napp.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)',
)

repl(
'''def init_runtime_state():
    if not USERS_FILE.exists():
        _atomic_json_write(USERS_FILE, [])
    if not HISTORY_FILE.exists():
        _atomic_json_write(HISTORY_FILE, [])
    admin_email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    admin_name = os.environ.get("INITIAL_ADMIN_NAME", "Project Admin").strip() or "Project Admin"
    if admin_email and admin_password:
        with _json_lock:
            users = _load_json(USERS_FILE, [])
            if not any(u.get("email", "").lower() == admin_email for u in users):
                users.append({"email": admin_email, "name": admin_name, "password": generate_password_hash(admin_password), "role": "Admin"})
                _atomic_json_write(USERS_FILE, users)
''',
'''def init_runtime_state():
    if not USERS_FILE.exists():
        _atomic_json_write(USERS_FILE, [])
    if not HISTORY_FILE.exists():
        _atomic_json_write(HISTORY_FILE, [])
    admin_email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    admin_name = os.environ.get("INITIAL_ADMIN_NAME", "Project Admin").strip() or "Project Admin"
    if db_enabled():
        if admin_email and admin_password:
            ensure_admin(admin_email, generate_password_hash(admin_password), admin_name)
        return
    if admin_email and admin_password:
        with _json_lock:
            users = _load_json(USERS_FILE, [])
            if not any(u.get("email", "").lower() == admin_email for u in users):
                users.append({"email": admin_email, "name": admin_name, "password": generate_password_hash(admin_password), "role": "Admin", "is_active": True})
                _atomic_json_write(USERS_FILE, users)
''')

repl(
'''def load_users():
    return _load_json(USERS_FILE, [])


def save_user(user_data):
    with _json_lock:
        users = load_users()
        users.append(user_data)
        _atomic_json_write(USERS_FILE, users)
''',
'''def load_users():
    if db_enabled():
        return fetch_users()
    return _load_json(USERS_FILE, [])


def save_user(user_data):
    if db_enabled():
        return db_create_user(user_data["name"], user_data["email"], user_data["password"], user_data.get("role", "Student"))
    with _json_lock:
        users = load_users()
        user_data.setdefault("is_active", True)
        users.append(user_data)
        _atomic_json_write(USERS_FILE, users)
''')

repl(
'''def load_history():
    return _load_json(HISTORY_FILE, [])
''',
'''def load_history():
    if db_enabled():
        user = session.get("user", {})
        return fetch_history(user.get("email"), user.get("role") == "Admin")
    return _load_json(HISTORY_FILE, [])
''')

repl(
'''    with _json_lock:
        history = load_history()
        next_id = max([int(item.get("id", 0)) for item in history] or [0]) + 1
        history.append({
            "id": next_id,
            "date": datetime.now().isoformat(timespec="seconds"),
            "student_name": student_data.get("Name") or student_data.get("Student_Name") or "Student",
            "student": student_data,
            "prediction": prediction,
            "prediction_label": label,
            "confidence": confidence,
            "report": report_name,
            "user_email": user.get("email", ""),
        })
        _atomic_json_write(HISTORY_FILE, history)
''',
'''    if db_enabled():
        save_history(student_data, prediction, label, confidence, report_name, user.get("email", ""))
        increment_metric("predictions")
        return
    with _json_lock:
        history = load_history()
        next_id = max([int(item.get("id", 0)) for item in history] or [0]) + 1
        history.append({
            "id": next_id,
            "date": datetime.now().isoformat(timespec="seconds"),
            "student_name": student_data.get("Name") or student_data.get("Student_Name") or "Student",
            "student": student_data,
            "prediction": prediction,
            "prediction_label": label,
            "confidence": confidence,
            "report": report_name,
            "user_email": user.get("email", ""),
        })
        _atomic_json_write(HISTORY_FILE, history)
''')

repl(
'''        if not user_match or not verify_user_password(user_match.get("password"), password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))
''',
'''        if not user_match or not verify_user_password(user_match.get("password"), password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))
        if user_match.get("is_active") is False:
            flash("This account has been disabled by an administrator.", "danger")
            return redirect(url_for("login"))
''')

repl(
'''        session["user"] = {"name": user_match.get("name", "User"), "email": user_match.get("email", email), "role": user_match.get("role", "Student")}
        flash(f"Welcome back, {session['user']['name']}!", "success")
''',
'''        session["user"] = {"name": user_match.get("name", "User"), "email": user_match.get("email", email), "role": user_match.get("role", "Student")}
        if db_enabled():
            touch_login(email)
            increment_metric("logins")
        flash(f"Welcome back, {session['user']['name']}!", "success")
''')

repl(
'''        save_user({"name": name, "email": email, "password": generate_password_hash(password), "role": role})
        session.clear()
''',
'''        save_user({"name": name, "email": email, "password": generate_password_hash(password), "role": role})
        if db_enabled():
            increment_metric("registrations")
        session.clear()
''')

anchor = 'def allowed_dataset(filename):\n'
tracking = '''@app.before_request
def track_request():
    if not db_enabled() or request.path.startswith("/static/"):
        return
    try:
        visitor = session.get("_visitor_id")
        if not visitor:
            visitor = secrets.token_hex(16)
            session["_visitor_id"] = visitor
        digest = hashlib.sha256((visitor + app.config["SECRET_KEY"]).encode()).hexdigest()
        record_request(request.path, digest, "user" in session)
    except Exception as exc:
        print("Traffic tracking warning:", exc)


'''
repl(anchor, tracking + anchor)

admin_routes = '''

@app.route("/admin")
@admin_required
def admin_console():
    if not db_enabled():
        flash("Admin analytics requires Neon / DATABASE_URL.", "warning")
        return redirect(url_for("dashboard"))
    return render_template("admin.html", users=fetch_users(), stats=admin_snapshot())


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_user(user_id):
    users = fetch_users() if db_enabled() else []
    target = next((u for u in users if int(u.get("id", 0)) == user_id), None)
    if not target:
        flash("User not found.", "danger")
    elif target.get("email") == session.get("user", {}).get("email"):
        flash("You cannot disable your own administrator account.", "warning")
    else:
        set_user_active(user_id, not bool(target.get("is_active")))
        flash("User status updated.", "success")
    return redirect(url_for("admin_console"))


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@admin_required
def admin_change_role(user_id):
    role = request.form.get("role", "Student")
    users = fetch_users() if db_enabled() else []
    target = next((u for u in users if int(u.get("id", 0)) == user_id), None)
    if not target:
        flash("User not found.", "danger")
    elif target.get("email") == session.get("user", {}).get("email"):
        flash("You cannot change your own administrator role here.", "warning")
    elif role not in {"Admin", "Student"}:
        flash("Invalid role.", "danger")
    else:
        set_user_role(user_id, role)
        flash(f"{target.get('name','User')} is now {role}.", "success")
    return redirect(url_for("admin_console"))
'''
repl('\n\n@app.errorhandler(413)\n', admin_routes + '\n\n@app.errorhandler(413)\n')

app_path.write_text(app, encoding='utf-8')

base_path = Path('templates/base.html')
base = base_path.read_text(encoding='utf-8')
old = '''      <a href="{{ url_for('report') }}" class="{% if request.endpoint in ['report','download_saved_report'] %}active{% endif %}"><i class="fa-solid fa-file-pdf"></i><span>Reports</span></a>\n'''
new = old + '''      {% if session.get('user', {}).get('role') == 'Admin' %}<div class="nav-heading">Administration</div><a href="{{ url_for('admin_console') }}" class="{% if request.endpoint and request.endpoint.startswith('admin_') %}active{% endif %}"><i class="fa-solid fa-shield-halved"></i><span>Admin Console</span></a>{% endif %}\n'''
if old not in base:
    raise SystemExit('Base nav anchor missing')
base_path.write_text(base.replace(old, new, 1), encoding='utf-8')

req_path = Path('requirements.txt')
req = req_path.read_text(encoding='utf-8')
if 'psycopg[' not in req:
    req = req.rstrip() + '\npsycopg[binary]==3.2.3\n'
req_path.write_text(req, encoding='utf-8')
