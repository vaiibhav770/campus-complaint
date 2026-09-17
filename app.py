import os
import csv
import io
import uuid
from functools import wraps
from datetime import datetime, timedelta
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
    session,
    g,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

import ai_classifier
import db as db_module

load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "ADMIN123")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smart-campus-hackathon-multi-role-secret-key")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)  # Persistent login for 30 days

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Auto-initialize MongoDB Atlas collections and indexes on startup (for Gunicorn / Render)
try:
    db_module.init_db()
except Exception as _e:
    print(f"MongoDB Atlas startup init note: {_e}")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def save_complaint_photo(req) -> str | None:
    """Saves photo from either direct file upload or live camera snapshot data."""
    # 1. Standard file upload
    photo_file = req.files.get("photo")
    if photo_file and photo_file.filename and allowed_file(photo_file.filename):
        ext = photo_file.filename.rsplit(".", 1)[1].lower()
        safe_name = f"{uuid.uuid4().hex[:12]}.{ext}"
        photo_file.save(os.path.join(UPLOAD_FOLDER, safe_name))
        return safe_name

    # 2. Base64 live camera snapshot
    camera_data = req.form.get("camera_photo", "").strip()
    if camera_data and camera_data.startswith("data:image"):
        import base64
        try:
            header, encoded = camera_data.split(",", 1)
            ext = "jpg"
            if "png" in header:
                ext = "png"
            elif "webp" in header:
                ext = "webp"
            safe_name = f"cam_{uuid.uuid4().hex[:12]}.{ext}"
            file_bytes = base64.b64decode(encoded)
            with open(os.path.join(UPLOAD_FOLDER, safe_name), "wb") as f:
                f.write(file_bytes)
            return safe_name
        except Exception as e:
            print(f"Error decoding camera photo base64: {e}")
            return None

    return None


def get_db():
    return db_module.get_db()


# ---------------------------------------------------------------------------
# AUTHENTICATION & ACCESS CONTROL HELPERS
# ---------------------------------------------------------------------------

@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.users.find_one({"id": user_id})


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please sign in or register to access this section.", "error")
            return redirect(url_for("login", next=request.url))
        return view(**kwargs)
    return wrapped_view


def role_required(allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                flash("Please sign in or register to access this section.", "error")
                return redirect(url_for("login", next=request.url))
            if g.user["role"] not in allowed_roles:
                flash(f"Access denied: Restricted to {', '.join(allowed_roles)} accounts.", "error")
                if g.user["role"] == "student":
                    return redirect(url_for("student_portal"))
                elif g.user["role"] == "faculty":
                    return redirect(url_for("faculty_portal"))
                else:
                    return redirect(url_for("admin_dashboard"))
            return view(**kwargs)
        return wrapped_view
    return decorator


# ---------------------------------------------------------------------------
# ENTRY ROUTE & SUBMISSION REDIRECT
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Directs logged-in users to their portal; prompts new visitors to register first."""
    if g.user:
        if g.user["role"] == "student":
            return redirect(url_for("student_portal"))
        elif g.user["role"] == "faculty":
            return redirect(url_for("faculty_portal"))
        elif g.user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
    # If not logged in, ask for registration first
    return redirect(url_for("register"))


@app.route("/submit", methods=["GET", "POST"])
def submit_complaint():
    """Compatibility route for submitting complaints."""
    if g.user:
        if g.user["role"] == "faculty":
            return redirect(url_for("faculty_portal"))
        elif g.user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_portal"))
    return redirect(url_for("register"))


# ---------------------------------------------------------------------------
# REGISTRATION & AUTHENTICATION (MONGODB ATLAS)
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    """Registration endpoint: saves user credentials in MongoDB Atlas and auto-signs them in."""
    if g.user:
        return redirect(url_for("index"))

    if request.method == "POST":
        role = request.form.get("role", "student").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        identifier = request.form.get("identifier", "").strip()
        department = request.form.get("department", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        remember_me = request.form.get("remember_me")

        # Admin passcode verification
        if role == "admin":
            admin_code = request.form.get("admin_passcode", "").strip()
            if admin_code != ADMIN_SECRET_KEY:
                flash(f"Invalid Administrator Access Code. (Use '{ADMIN_SECRET_KEY}')", "error")
                return render_template("register.html", role=role)

        if not username or not password or not full_name or not identifier:
            flash("Please fill in all required fields.", "error")
            return render_template("register.html", role=role)

        db = get_db()
        existing = db.users.find_one({"username": username})
        if existing:
            flash(f"Username '{username}' is already taken. Please choose another or sign in.", "error")
            return render_template("register.html", role=role)

        user_id = f"usr_{uuid.uuid4().hex[:10]}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        user_doc = {
            "id": user_id,
            "username": username,
            "password_hash": generate_password_hash(password),
            "role": role,
            "full_name": full_name,
            "identifier": identifier,
            "department": department,
            "email": email,
            "phone": phone,
            "created_at": now_str
        }

        db.users.insert_one(user_doc)

        # Persistent login session
        session.clear()
        if remember_me:
            session.permanent = True
        session["user_id"] = user_id
        session["username"] = username
        session["role"] = role
        session["full_name"] = full_name

        flash(f"Account registered in MongoDB Atlas! Welcome, {full_name}.", "success")

        if role == "student":
            return redirect(url_for("student_portal"))
        elif role == "faculty":
            return redirect(url_for("faculty_portal"))
        else:
            return redirect(url_for("admin_dashboard"))

    selected_role = request.args.get("role", "student")
    return render_template("register.html", role=selected_role)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login endpoint: authenticates against MongoDB Atlas stored credentials."""
    if g.user:
        if g.user["role"] == "student":
            return redirect(url_for("student_portal"))
        elif g.user["role"] == "faculty":
            return redirect(url_for("faculty_portal"))
        else:
            return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember_me = request.form.get("remember_me")

        db = get_db()
        # Find by username OR identifier
        user = db.users.find_one({"$or": [{"username": username}, {"identifier": username}]})

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            if remember_me:
                session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]

            flash(f"Welcome back, {user['full_name']}! Signed in as {user['role'].title()}.", "success")

            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)

            if user["role"] == "student":
                return redirect(url_for("student_portal"))
            elif user["role"] == "faculty":
                return redirect(url_for("faculty_portal"))
            else:
                return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials. Please verify your username and password or register a new account.", "error")

    prefill = request.args.get("user", "")
    return render_template("login.html", prefill_username=prefill)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out successfully.", "success")
    return redirect(url_for("login"))


# Helper for test suites
@app.route("/demo-login/<role>")
def demo_login(role):
    role = role.lower()
    if role not in ["student", "faculty", "admin"]:
        flash("Invalid role.", "error")
        return redirect(url_for("login"))

    db = get_db()
    user = db.users.find_one({"username": role})

    if user:
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]

        flash(f"Signed in as {user['full_name']} ({role.title()}).", "success")
        if role == "student":
            return redirect(url_for("student_portal"))
        elif role == "faculty":
            return redirect(url_for("faculty_portal"))
        else:
            return redirect(url_for("admin_dashboard"))
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# STUDENT & FACULTY PORTALS (MONGODB ATLAS)
# ---------------------------------------------------------------------------

@app.route("/student", methods=["GET", "POST"])
@login_required
@role_required(["student"])
def student_portal():
    """Dedicated Student Portal: submit issues with pre-filled details & view My Complaints."""
    db = get_db()

    if request.method == "POST":
        location = request.form.get("location", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not description:
            flash("Please enter a detailed description of the complaint.", "error")
            return redirect(url_for("student_portal"))

        combined_text = f"{title} {description}".strip()
        ai_result = ai_classifier.route_complaint(combined_text, location)

        # Photo handling (uploaded file or live camera snapshot)
        photo_filename = save_complaint_photo(request)

        complaint_id = f"CMP-{uuid.uuid4().hex[:6].upper()}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        doc = {
            "id": complaint_id,
            "user_id": g.user["id"],
            "user_role": "student",
            "student_name": g.user["full_name"],
            "roll_no": g.user["identifier"],
            "contact_email": g.user["email"],
            "contact_phone": g.user["phone"],
            "location": location,
            "title": title or description[:40],
            "description": description,
            "category": ai_result["category"],
            "confidence": ai_result["confidence"],
            "priority": ai_result["priority"],
            "priority_reason": ai_result["priority_reason"],
            "department": ai_result["department"],
            "assigned_officer": ai_result["assigned_officer"],
            "status": "Submitted",
            "photo": photo_filename,
            "resolution_notes": "",
            "resolution_photo": None,
            "resolved_at": "",
            "sla_hours": ai_result["sla_hours"],
            "sla_target": ai_result["sla_target_iso"],
            "student_rating": None,
            "student_feedback": "",
            "created_at": now_str,
            "updated_at": now_str
        }

        db.complaints.insert_one(doc)

        flash(f"Complaint {complaint_id} logged and routed to {ai_result['department']} successfully!", "success")
        return redirect(url_for("confirmation", complaint_id=complaint_id))

    # Retrieve student's complaints
    my_complaints = list(db.complaints.find({
        "$or": [{"user_id": g.user["id"]}, {"roll_no": g.user["identifier"]}]
    }).sort("created_at", -1))

    student_stats = {
        "total": len(my_complaints),
        "open": sum(1 for c in my_complaints if c.get("status") in ("Submitted", "In Progress")),
        "resolved": sum(1 for c in my_complaints if c.get("status") in ("Resolved", "Closed")),
    }

    active_tab = request.args.get("tab", "submit")
    return render_template("student_portal.html", my_complaints=my_complaints, stats=student_stats, active_tab=active_tab)


@app.route("/faculty", methods=["GET", "POST"])
@login_required
@role_required(["faculty"])
def faculty_portal():
    """Dedicated Faculty Portal: high-priority classroom/lab maintenance & department overview."""
    db = get_db()

    if request.method == "POST":
        location = request.form.get("location", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        urgency_override = request.form.get("urgency_override", "Normal")

        if not description:
            flash("Please enter a detailed description of the academic issue.", "error")
            return redirect(url_for("faculty_portal"))

        combined_text = f"{title} {description}".strip()
        ai_result = ai_classifier.route_complaint(combined_text, location)

        # Faculty academic priority boost
        if urgency_override == "High" and ai_result["priority"] not in ("Critical", "High"):
            ai_result["priority"] = "High"
            ai_result["priority_reason"] += " (Faculty Escalated: Class/Lab In Session)"
            ai_result["sla_hours"] = 8
            iso, readable = ai_classifier.calculate_sla_target(8)
            ai_result["sla_target_iso"] = iso

        # Photo handling (uploaded file or live camera snapshot)
        photo_filename = save_complaint_photo(request)

        complaint_id = f"CMP-{uuid.uuid4().hex[:6].upper()}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        doc = {
            "id": complaint_id,
            "user_id": g.user["id"],
            "user_role": "faculty",
            "student_name": g.user["full_name"],
            "roll_no": g.user["identifier"],
            "contact_email": g.user["email"],
            "contact_phone": g.user["phone"],
            "location": location,
            "title": title or description[:40],
            "description": description,
            "category": ai_result["category"],
            "confidence": ai_result["confidence"],
            "priority": ai_result["priority"],
            "priority_reason": ai_result["priority_reason"],
            "department": ai_result["department"],
            "assigned_officer": ai_result["assigned_officer"],
            "status": "Submitted",
            "photo": photo_filename,
            "resolution_notes": "",
            "resolution_photo": None,
            "resolved_at": "",
            "sla_hours": ai_result["sla_hours"],
            "sla_target": ai_result["sla_target_iso"],
            "student_rating": None,
            "student_feedback": "",
            "created_at": now_str,
            "updated_at": now_str
        }

        db.complaints.insert_one(doc)

        flash(f"Academic Ticket {complaint_id} dispatched to {ai_result['department']} with Faculty Priority!", "success")
        return redirect(url_for("confirmation", complaint_id=complaint_id))

    faculty_complaints = list(db.complaints.find({
        "$or": [{"user_id": g.user["id"]}, {"roll_no": g.user["identifier"]}]
    }).sort("created_at", -1))

    faculty_stats = {
        "total": len(faculty_complaints),
        "open": sum(1 for c in faculty_complaints if c.get("status") in ("Submitted", "In Progress")),
        "resolved": sum(1 for c in faculty_complaints if c.get("status") in ("Resolved", "Closed")),
    }

    active_tab = request.args.get("tab", "submit")
    return render_template("faculty_portal.html", complaints=faculty_complaints, stats=faculty_stats, active_tab=active_tab)


# ---------------------------------------------------------------------------
# API & HELPER ENDPOINTS
# ---------------------------------------------------------------------------

@app.route("/api/predict", methods=["POST"])
def api_predict():
    """Real-time AI prediction endpoint for live typing feedback."""
    data = request.get_json() or {}
    text = (data.get("description") or "").strip()
    title = (data.get("title") or "").strip()
    location = (data.get("location") or "").strip()

    combined_text = f"{title} {text}".strip()
    if not combined_text:
        return jsonify({
            "category": "Pending Input",
            "confidence": 0,
            "priority": "Low",
            "priority_reason": "Waiting for issue description...",
            "department": "Pending Assignment",
            "assigned_officer": "-",
            "sla_hours": 24,
            "sla_target_readable": "-",
            "matched_keywords": [],
            "top_probabilities": {},
        })

    prediction = ai_classifier.route_complaint(combined_text, location)
    return jsonify(prediction)


@app.route("/api/seed", methods=["POST"])
def api_seed():
    """Seed demo complaints on demand into MongoDB Atlas."""
    db = get_db()
    db_module.seed_sample_complaints(db)
    flash("Successfully synchronized sample complaints into MongoDB Atlas!", "success")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# TRACKING & CONFIRMATION (MONGODB ATLAS)
# ---------------------------------------------------------------------------

@app.route("/confirmation/<complaint_id>")
def confirmation(complaint_id):
    db = get_db()
    complaint = db.complaints.find_one({"id": complaint_id})

    if not complaint:
        flash("Complaint not found.", "error")
        return redirect(url_for("index"))

    return render_template("confirmation.html", complaint=complaint)


@app.route("/track", methods=["GET", "POST"])
def track():
    if request.method == "POST":
        searched_id = request.form.get("complaint_id", "").strip().upper()
        if searched_id:
            return redirect(url_for("track_ticket", complaint_id=searched_id))

    db = get_db()
    recent_tickets = list(db.complaints.find().sort("created_at", -1).limit(5))

    return render_template("track.html", complaint=None, searched=False, recent_tickets=recent_tickets)


@app.route("/track/<complaint_id>")
def track_ticket(complaint_id):
    complaint_id = complaint_id.strip().upper()
    db = get_db()
    complaint = db.complaints.find_one({"id": complaint_id})
    recent_tickets = list(db.complaints.find().sort("created_at", -1).limit(5))

    return render_template("track.html", complaint=complaint, searched=True, searched_id=complaint_id, recent_tickets=recent_tickets)


@app.route("/track/feedback/<complaint_id>", methods=["POST"])
def submit_feedback(complaint_id):
    rating = request.form.get("rating", type=int)
    feedback = request.form.get("feedback", "").strip()

    db = get_db()
    db.complaints.update_one(
        {"id": complaint_id},
        {"$set": {
            "student_rating": rating,
            "student_feedback": feedback,
            "status": "Closed",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }}
    )

    flash("Thank you! Your feedback has been recorded in MongoDB Atlas and ticket is officially closed.", "success")
    return redirect(url_for("track_ticket", complaint_id=complaint_id))


# ---------------------------------------------------------------------------
# ADMIN & OPERATIONS DASHBOARD (MONGODB ATLAS)
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
@role_required(["admin"])
def admin_dashboard():
    status_filter = request.args.get("status", "")
    dept_filter = request.args.get("department", "")
    priority_filter = request.args.get("priority", "")
    role_filter = request.args.get("role", "")
    search_query = request.args.get("q", "").strip()

    query = {}
    if status_filter:
        query["status"] = status_filter
    if dept_filter:
        query["department"] = dept_filter
    if priority_filter:
        query["priority"] = priority_filter
    if role_filter:
        query["user_role"] = role_filter
    if search_query:
        regex = {"$regex": search_query, "$options": "i"}
        query["$or"] = [
            {"id": regex},
            {"description": regex},
            {"location": regex},
            {"student_name": regex},
            {"title": regex}
        ]

    db = get_db()
    complaints = list(db.complaints.find(query))

    # Sort: Critical first, High second, Medium third, Low fourth; then by newest date first
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    complaints.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    complaints.sort(key=lambda c: priority_order.get(c.get("priority", "Low"), 3))

    all_depts = [d for d in db.complaints.distinct("department") if d]
    if not all_depts:
        all_depts = [d["department"] for d in ai_classifier.DEPARTMENT_DIRECTORY.values()]

    # KPI counts via MongoDB
    total_count = db.complaints.count_documents({})
    submitted_count = db.complaints.count_documents({"status": "Submitted"})
    in_progress_count = db.complaints.count_documents({"status": "In Progress"})
    resolved_count = db.complaints.count_documents({"status": {"$in": ["Resolved", "Closed"]}})
    critical_count = db.complaints.count_documents({"priority": "Critical", "status": {"$nin": ["Resolved", "Closed"]}})

    # Category Breakdown for Chart.js
    cat_pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    cat_rows = list(db.complaints.aggregate(cat_pipeline))
    chart_categories = [r["_id"] for r in cat_rows if r["_id"]]
    chart_counts = [r["count"] for r in cat_rows if r["_id"]]

    # Priority Breakdown for Chart.js
    prio_pipeline = [
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
    ]
    prio_rows = list(db.complaints.aggregate(prio_pipeline))
    prio_map = {r["_id"]: r["count"] for r in prio_rows if r["_id"]}
    chart_priorities = {
        "Critical": prio_map.get("Critical", 0),
        "High": prio_map.get("High", 0),
        "Medium": prio_map.get("Medium", 0),
        "Low": prio_map.get("Low", 0),
    }

    stats = {
        "total": total_count,
        "submitted": submitted_count,
        "in_progress": in_progress_count,
        "resolved": resolved_count,
        "critical": critical_count,
    }

    return render_template(
        "admin.html",
        complaints=complaints,
        departments=all_depts,
        stats=stats,
        status_filter=status_filter,
        dept_filter=dept_filter,
        priority_filter=priority_filter,
        role_filter=role_filter,
        search_query=search_query,
        chart_categories=chart_categories,
        chart_counts=chart_counts,
        chart_priorities=chart_priorities,
    )


@app.route("/admin/update/<complaint_id>", methods=["POST"])
@login_required
@role_required(["admin"])
def update_status(complaint_id):
    new_status = request.form.get("status")
    assigned_officer = request.form.get("assigned_officer", "").strip()
    resolution_notes = request.form.get("resolution_notes", "").strip()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_doc = {
        "status": new_status,
        "updated_at": now_str
    }

    if assigned_officer:
        update_doc["assigned_officer"] = assigned_officer
    if resolution_notes:
        update_doc["resolution_notes"] = resolution_notes
    if new_status in ("Resolved", "Closed"):
        update_doc["resolved_at"] = now_str

    res_file = request.files.get("resolution_photo")
    if res_file and res_file.filename and allowed_file(res_file.filename):
        ext = res_file.filename.rsplit(".", 1)[1].lower()
        res_name = f"resolved_{uuid.uuid4().hex[:10]}.{ext}"
        res_file.save(os.path.join(UPLOAD_FOLDER, res_name))
        update_doc["resolution_photo"] = res_name

    db = get_db()
    db.complaints.update_one(
        {"id": complaint_id},
        {"$set": update_doc}
    )

    flash(f"Complaint {complaint_id} updated to '{new_status}' in MongoDB Atlas!", "success")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/admin/export")
@login_required
@role_required(["admin"])
def export_csv():
    status_filter = request.args.get("status", "")
    dept_filter = request.args.get("department", "")

    query = {}
    if status_filter:
        query["status"] = status_filter
    if dept_filter:
        query["department"] = dept_filter

    db = get_db()
    rows = list(db.complaints.find(query).sort("created_at", -1))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Complaint ID", "User Role", "Student/Faculty Name", "Roll / ID No", "Contact Email", "Contact Phone",
        "Location", "Title", "Description", "Category", "Confidence (%)",
        "Priority", "Severity Reason", "Department", "Assigned Officer",
        "Status", "SLA Target", "Resolution Notes", "Created At", "Resolved At"
    ])

    for r in rows:
        writer.writerow([
            r.get("id"), r.get("user_role", "student"), r.get("student_name"), r.get("roll_no"),
            r.get("contact_email"), r.get("contact_phone"), r.get("location"), r.get("title"),
            r.get("description"), r.get("category"), r.get("confidence"), r.get("priority"),
            r.get("priority_reason"), r.get("department"), r.get("assigned_officer"),
            r.get("status"), r.get("sla_target"), r.get("resolution_notes"),
            r.get("created_at"), r.get("resolved_at")
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=campus_complaints_atlas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )


if __name__ == "__main__":
    db_module.init_db()
    print(" Smart Campus Complaint System (MongoDB Atlas) running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
