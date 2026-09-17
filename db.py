"""
MongoDB Atlas Database Layer for Smart Campus Complaint System
-------------------------------------------------------------
Manages:
- Connection pooling to MongoDB Atlas
- Index creation on users and complaints collections
- Default users and sample complaint seeding
"""

import os
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import generate_password_hash

import ai_classifier

# Load environment variables from .env
load_dotenv()

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://protechxlr_db_user:dXO75jOnsEpMJIcD@vsmart.vg39rfx.mongodb.net/?retryWrites=true&w=majority"
)
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "smart_campus")

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
            maxPoolSize=50,
            retryWrites=True,
        )
    return _client


def get_db():
    client = get_client()
    return client[MONGO_DB_NAME]


def init_db():
    """Initializes collections, sets up indexes, and populates initial records if empty."""
    db = get_db()

    # Verify connection to Atlas
    try:
        db.command("ping")
        print(f" Connected to MongoDB Atlas: Database '{MONGO_DB_NAME}'")
    except Exception as e:
        print(f" MongoDB Atlas Connection Warning: {e}")

    # Ensure Indexes
    try:
        db.users.create_index("username", unique=True)
        db.users.create_index("identifier")
        db.complaints.create_index("id", unique=True)
        db.complaints.create_index([("department", ASCENDING), ("status", ASCENDING)])
        db.complaints.create_index([("priority", ASCENDING), ("created_at", DESCENDING)])
        db.complaints.create_index("user_id")
        db.complaints.create_index("roll_no")
    except Exception as e:
        print(f" Index creation notice: {e}")

    # Seed Default Users if empty
    if db.users.count_documents({}) == 0:
        seed_default_users(db)

    # Seed Initial Complaints if empty
    if db.complaints.count_documents({}) == 0:
        seed_sample_complaints(db)


def seed_default_users(db):
    default_users = [
        {
            "id": "usr_student_demo",
            "username": "student",
            "password_hash": generate_password_hash("password"),
            "role": "student",
            "full_name": "Vaibhav Sharma",
            "identifier": "21CS1023",
            "department": "Computer Science & Engineering",
            "email": "vaibhav.cs@campus.edu",
            "phone": "9876543210",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "id": "usr_faculty_demo",
            "username": "faculty",
            "password_hash": generate_password_hash("password"),
            "role": "faculty",
            "full_name": "Prof. R. K. Narayan",
            "identifier": "FAC-108",
            "department": "Electrical Engineering",
            "email": "rknarayan@campus.edu",
            "phone": "9812345678",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "id": "usr_admin_demo",
            "username": "admin",
            "password_hash": generate_password_hash("password"),
            "role": "admin",
            "full_name": "Campus Operations Lead",
            "identifier": "ADM-001",
            "department": "Estate & Campus Administration",
            "email": "admin@campus.edu",
            "phone": "9800000000",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
    ]

    for u in default_users:
        db.users.update_one(
            {"username": u["username"]},
            {"$setOnInsert": u},
            upsert=True
        )
    print(" Seeded default users in MongoDB Atlas.")


def seed_sample_complaints(db):
    samples = [
        {
            "user_id": "usr_student_demo",
            "user_role": "student",
            "student_name": "Vaibhav Sharma",
            "roll_no": "21CS1023",
            "contact_email": "vaibhav.cs@campus.edu",
            "contact_phone": "9876543210",
            "location": "Academic Block C, Computer Lab 3",
            "title": "High packet drop and Wi-Fi disconnect in Lab 3",
            "description": "The campus Wi-Fi access point in Lab 3 is dropping packets every few minutes, interrupting online coding practicals.",
            "status": "In Progress",
            "resolution_notes": "Technician dispatched to replace the PoE switch and re-terminate the Ethernet drop.",
            "created_hours_ago": 6,
        },
        {
            "user_id": "usr_student_demo",
            "user_role": "student",
            "student_name": "Priya Patel",
            "roll_no": "22EE2015",
            "contact_email": "priya.ee@campus.edu",
            "contact_phone": "9812345678",
            "location": "Girls Hostel 2, 2nd Floor Corridor",
            "title": "Sparking from switchboard and burning smell",
            "description": "Continuous sparking and a strong burning plastic smell from the electrical switchboard outside room 204. Extremely dangerous.",
            "status": "Submitted",
            "resolution_notes": "",
            "created_hours_ago": 1,
        },
        {
            "user_id": "usr_faculty_demo",
            "user_role": "faculty",
            "student_name": "Prof. R. K. Narayan",
            "roll_no": "FAC-108",
            "contact_email": "rknarayan@campus.edu",
            "contact_phone": "9812345678",
            "location": "Lecture Theater 102",
            "title": "Air conditioner compressor failure during lectures",
            "description": "AC unit in LT-102 is blowing hot air and remote display shows error E4. Unbearable heat for 80 students during scheduled thermodynamics classes.",
            "status": "In Progress",
            "resolution_notes": "HVAC team on-site inspecting the outdoor condensing coil and capacitor.",
            "created_hours_ago": 4,
        },
        {
            "user_id": "usr_student_demo",
            "user_role": "student",
            "student_name": "Rohan Gupta",
            "roll_no": "23ME3008",
            "contact_email": "rohan.me@campus.edu",
            "contact_phone": "9823456789",
            "location": "Central Library, 1st Floor Washroom",
            "title": "Severe water tap leakage and washroom flooding",
            "description": "Main water tap broken and water is gushing onto the floor, causing water flooding into the library hallway.",
            "status": "In Progress",
            "resolution_notes": "Main isolation valve shut off. Plumber replacing damaged ball valve and seal ring.",
            "created_hours_ago": 3,
        },
        {
            "user_id": "usr_faculty_demo",
            "user_role": "faculty",
            "student_name": "Prof. R. K. Narayan",
            "roll_no": "FAC-108",
            "contact_email": "rknarayan@campus.edu",
            "contact_phone": "9812345678",
            "location": "Seminar Hall 2",
            "title": "Projector HDMI interface flickering and bulb dim",
            "description": "Ceiling mounted projector in Seminar Hall 2 is showing purple tint and heavy screen flicker, urgent for guest lecture tomorrow.",
            "status": "Resolved",
            "resolution_notes": "Replaced HDMI splitter box and high-speed gold plated HDMI cable. Display tested and calibrated.",
            "created_hours_ago": 26,
            "resolved_hours_ago": 2,
            "student_rating": 5,
            "student_feedback": "Excellent immediate repair ahead of the conference. Thank you!",
        }
    ]

    for s in samples:
        cid = f"CMP-{uuid.uuid4().hex[:6].upper()}"
        ai_res = ai_classifier.route_complaint(s["description"], s["location"])
        created_dt = datetime.now() - timedelta(hours=s["created_hours_ago"])
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")

        resolved_str = ""
        if s.get("resolved_hours_ago"):
            res_dt = datetime.now() - timedelta(hours=s["resolved_hours_ago"])
            resolved_str = res_dt.strftime("%Y-%m-%d %H:%M:%S")

        sla_deadline = created_dt + timedelta(hours=ai_res["sla_hours"])
        sla_target_str = sla_deadline.strftime("%Y-%m-%d %H:%M:%S")

        doc = {
            "id": cid,
            "user_id": s.get("user_id"),
            "user_role": s.get("user_role", "student"),
            "student_name": s["student_name"],
            "roll_no": s["roll_no"],
            "contact_email": s["contact_email"],
            "contact_phone": s["contact_phone"],
            "location": s["location"],
            "title": s["title"],
            "description": s["description"],
            "category": ai_res["category"],
            "confidence": ai_res["confidence"],
            "priority": ai_res["priority"],
            "priority_reason": ai_res["priority_reason"],
            "department": ai_res["department"],
            "assigned_officer": ai_res["assigned_officer"],
            "status": s["status"],
            "photo": None,
            "resolution_notes": s.get("resolution_notes", ""),
            "resolution_photo": None,
            "resolved_at": resolved_str,
            "sla_hours": ai_res["sla_hours"],
            "sla_target": sla_target_str,
            "student_rating": s.get("student_rating"),
            "student_feedback": s.get("student_feedback"),
            "created_at": created_str,
            "updated_at": created_str
        }

        db.complaints.update_one(
            {"id": cid},
            {"$setOnInsert": doc},
            upsert=True
        )
    print(" Seeded sample complaints in MongoDB Atlas.")
