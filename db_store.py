import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def db_enabled():
    return bool(DATABASE_URL)


@contextmanager
def connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn


def ensure_admin(email, password_hash, name):
    if not db_enabled() or not email or not password_hash:
        return
    with connection() as conn:
        conn.execute(
            """INSERT INTO users (name,email,password_hash,role,is_active)
               VALUES (%s,%s,%s,'Admin',TRUE)
               ON CONFLICT (email) DO NOTHING""",
            (name, email.lower(), password_hash),
        )


def fetch_users():
    with connection() as conn:
        rows = conn.execute(
            "SELECT id,name,email,password_hash,role,is_active,created_at,last_login_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r, password=r["password_hash"]) for r in rows]


def create_user(name, email, password_hash, role="Student"):
    with connection() as conn:
        row = conn.execute(
            """INSERT INTO users (name,email,password_hash,role,is_active)
               VALUES (%s,%s,%s,%s,TRUE)
               RETURNING id,name,email,role,is_active,created_at,last_login_at""",
            (name, email.lower(), password_hash, role),
        ).fetchone()
    return dict(row)


def touch_login(email):
    with connection() as conn:
        conn.execute("UPDATE users SET last_login_at=NOW() WHERE email=%s", (email.lower(),))


def set_user_active(user_id, active):
    with connection() as conn:
        conn.execute("UPDATE users SET is_active=%s WHERE id=%s", (bool(active), int(user_id)))


def set_user_role(user_id, role):
    if role not in {"Admin", "Student"}:
        raise ValueError("Invalid role")
    with connection() as conn:
        conn.execute("UPDATE users SET role=%s WHERE id=%s", (role, int(user_id)))


def save_history(student_data, prediction, prediction_label, confidence, report_name, user_email):
    with connection() as conn:
        row = conn.execute(
            """INSERT INTO prediction_history
               (student_name,student_data,prediction,prediction_label,confidence,report_name,user_email)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                student_data.get("Name") or student_data.get("Student_Name") or "Student",
                Jsonb(student_data), prediction, prediction_label,
                confidence, report_name, user_email or None,
            ),
        ).fetchone()
    return row["id"]


def fetch_history(email=None, is_admin=False):
    with connection() as conn:
        if is_admin:
            rows = conn.execute(
                """SELECT id,created_at,student_name,student_data,prediction,prediction_label,
                          confidence,report_name,user_email
                   FROM prediction_history ORDER BY created_at ASC"""
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id,created_at,student_name,student_data,prediction,prediction_label,
                          confidence,report_name,user_email
                   FROM prediction_history WHERE user_email=%s ORDER BY created_at ASC""",
                (email or "",),
            ).fetchall()
    return [{
        "id": r["id"], "date": r["created_at"].isoformat(timespec="seconds"),
        "student_name": r["student_name"], "student": r["student_data"] or {},
        "prediction": r["prediction"], "prediction_label": r["prediction_label"],
        "confidence": r["confidence"], "report": r["report_name"],
        "user_email": r["user_email"] or "",
    } for r in rows]


def increment_metric(metric):
    allowed = {"predictions", "registrations", "logins"}
    if metric not in allowed:
        return
    with connection() as conn:
        conn.execute(
            f"""INSERT INTO traffic_daily (traffic_date,{metric}) VALUES (CURRENT_DATE,1)
                ON CONFLICT (traffic_date) DO UPDATE SET
                {metric}=traffic_daily.{metric}+1, updated_at=NOW()"""
        )


def record_request(path, visitor_hash, authenticated=False):
    clean_path = (path or "/")[:255]
    with connection() as conn:
        is_new = conn.execute(
            """INSERT INTO visitor_daily (traffic_date,visitor_hash) VALUES (CURRENT_DATE,%s)
               ON CONFLICT DO NOTHING RETURNING visitor_hash""", (visitor_hash,)
        ).fetchone() is not None
        conn.execute(
            """INSERT INTO traffic_daily (traffic_date,requests,unique_visitors,authenticated_requests)
               VALUES (CURRENT_DATE,1,%s,%s)
               ON CONFLICT (traffic_date) DO UPDATE SET
                 requests=traffic_daily.requests+1,
                 unique_visitors=traffic_daily.unique_visitors+EXCLUDED.unique_visitors,
                 authenticated_requests=traffic_daily.authenticated_requests+EXCLUDED.authenticated_requests,
                 updated_at=NOW()""",
            (1 if is_new else 0, 1 if authenticated else 0),
        )
        conn.execute(
            """INSERT INTO page_traffic (traffic_date,path,requests) VALUES (CURRENT_DATE,%s,1)
               ON CONFLICT (traffic_date,path) DO UPDATE SET requests=page_traffic.requests+1""",
            (clean_path,),
        )


def admin_snapshot(days=14):
    with connection() as conn:
        totals = conn.execute(
            """SELECT
               (SELECT COUNT(*) FROM users) AS total_users,
               (SELECT COUNT(*) FROM users WHERE is_active) AS active_users,
               (SELECT COUNT(*) FROM users WHERE role='Admin') AS admins,
               (SELECT COUNT(*) FROM prediction_history) AS total_predictions"""
        ).fetchone()
        today = conn.execute(
            """SELECT requests,unique_visitors,authenticated_requests,predictions,registrations,logins
               FROM traffic_daily WHERE traffic_date=CURRENT_DATE"""
        ).fetchone() or {"requests":0,"unique_visitors":0,"authenticated_requests":0,"predictions":0,"registrations":0,"logins":0}
        daily = conn.execute(
            """SELECT traffic_date,requests,unique_visitors,predictions,registrations,logins
               FROM traffic_daily WHERE traffic_date >= CURRENT_DATE - (%s::int - 1)
               ORDER BY traffic_date""", (days,)
        ).fetchall()
        top_pages = conn.execute(
            """SELECT path,SUM(requests)::bigint AS requests FROM page_traffic
               WHERE traffic_date >= CURRENT_DATE - 6 GROUP BY path ORDER BY requests DESC LIMIT 8"""
        ).fetchall()
    return {"totals": dict(totals), "today": dict(today), "daily": [dict(r) for r in daily], "top_pages": [dict(r) for r in top_pages]}
