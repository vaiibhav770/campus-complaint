"""
Comprehensive Verification Test Suite for Smart Campus Complaint System
Using MongoDB Atlas Cloud Database
"""
import unittest
import json
import uuid
from app import app, get_db
import db as db_module
import ai_classifier

class TestMongoDBAtlasCampusSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_module.init_db()
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess.clear()

    def test_01_mongodb_atlas_connection(self):
        db = get_db()
        # Verify Atlas connection ping
        result = db.command("ping")
        self.assertEqual(result.get("ok"), 1.0)
        # Check collections
        collections = db.list_collection_names()
        self.assertIn("users", collections)
        self.assertIn("complaints", collections)

    def test_02_registration_first_redirect(self):
        resp = self.client.get("/", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/register", resp.headers["Location"])

    def test_03_login_page_no_demo_cards(self):
        login_page = self.client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertNotIn(b"1-Click Demo Login", login_page.data)
        self.assertIn(b"Sign In to Campus Portal", login_page.data)

    def test_04_user_registration_in_atlas(self):
        db = get_db()
        unique_user = f"student_{uuid.uuid4().hex[:6]}"

        reg_data = {
            "role": "student",
            "username": unique_user,
            "password": "atlaspassword123",
            "full_name": "Atlas Test Student",
            "identifier": "23ATLAS100",
            "department": "Computer Science & Engineering",
            "email": "atlas@campus.edu",
            "phone": "9876543210",
            "remember_me": "1",
        }

        resp = self.client.post("/register", data=reg_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Student Portal", resp.data)

        # Verify record exists in MongoDB Atlas
        stored = db.users.find_one({"username": unique_user})
        self.assertIsNotNone(stored)
        self.assertEqual(stored["full_name"], "Atlas Test Student")

        # Verify login works with stored Atlas credentials
        with self.client.session_transaction() as sess:
            sess.clear()

        login_resp = self.client.post(
            "/login",
            data={"username": unique_user, "password": "atlaspassword123", "remember_me": "1"},
            follow_redirects=True
        )
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b"Atlas Test Student", login_resp.data)

    def test_05_complaint_lifecycle_in_atlas(self):
        db = get_db()
        self.client.get("/demo-login/student")

        # Submit complaint
        c_title = "Water leakage in Lab 4 washroom"
        c_desc = "Continuous tap water leakage and pipe overflow onto the corridor floor."
        c_loc = "Academic Block A, Lab 4"

        sub_resp = self.client.post("/student", data={
            "location": c_loc,
            "title": c_title,
            "description": c_desc,
        }, follow_redirects=True)

        self.assertEqual(sub_resp.status_code, 200)
        self.assertIn(b"Complaint Registered!", sub_resp.data)

        # Verify complaint stored in MongoDB Atlas
        c_doc = db.complaints.find_one({"title": c_title})
        self.assertIsNotNone(c_doc)
        self.assertEqual(c_doc["category"], "Plumbing & Water Supply")
        self.assertIn("Water Works", c_doc["department"])

        # Track ticket
        cid = c_doc["id"]
        track_resp = self.client.get(f"/track/{cid}")
        self.assertEqual(track_resp.status_code, 200)
        self.assertIn(cid.encode(), track_resp.data)

    def test_06_admin_dashboard_and_update_in_atlas(self):
        db = get_db()
        self.client.get("/demo-login/admin")

        admin_resp = self.client.get("/admin")
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b"Central Complaint Dispatch", admin_resp.data)

        # Find any active complaint to resolve
        ticket = db.complaints.find_one({"status": "Submitted"})
        if not ticket:
            ticket = db.complaints.find_one({})

        tid = ticket["id"]
        update_resp = self.client.post(
            f"/admin/update/{tid}",
            data={
                "status": "Resolved",
                "assigned_officer": "Er. MongoDB Lead",
                "resolution_notes": "Repaired and verified in MongoDB Atlas cluster.",
            },
            follow_redirects=True
        )
        self.assertEqual(update_resp.status_code, 200)

        # Check update in Atlas
        updated = db.complaints.find_one({"id": tid})
        self.assertEqual(updated["status"], "Resolved")
        self.assertEqual(updated["assigned_officer"], "Er. MongoDB Lead")

        # Check CSV export
        export_resp = self.client.get("/admin/export")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("text/csv", export_resp.headers["Content-Type"])

    def test_07_live_camera_snapshot_submission(self):
        import os
        db = get_db()
        self.client.get("/demo-login/student")

        # 1x1 transparent PNG as base64 data URL
        base64_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        resp = self.client.post("/student", data={
            "location": "Hostel 2, Room 101",
            "title": "Broken switchboard live camera evidence",
            "description": "Electric socket sparks when plugged in, danger of electric shock.",
            "camera_photo": base64_img
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Complaint Registered!", resp.data)

        # Verify saved in MongoDB Atlas
        c_doc = db.complaints.find_one({"title": "Broken switchboard live camera evidence"})
        self.assertIsNotNone(c_doc)
        self.assertTrue(c_doc.get("photo"))
        
        # Verify file exists on disk in static/uploads/
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], c_doc["photo"])
        self.assertTrue(os.path.isfile(filepath), f"File {filepath} was not saved on disk")

        # Verify image renders on tracking page
        track_resp = self.client.get(f"/track/{c_doc['id']}")
        self.assertEqual(track_resp.status_code, 200)
        self.assertIn(c_doc["photo"].encode(), track_resp.data)

    def test_08_faculty_live_camera_submission(self):
        import os
        db = get_db()
        self.client.get("/demo-login/faculty")

        base64_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        resp = self.client.post("/faculty", data={
            "location": "Seminar Hall A",
            "title": "Projector HDMI port damaged camera snapshot",
            "description": "HDMI port pins bent, cannot connect laptop during seminar.",
            "urgency_override": "High",
            "camera_photo": base64_img
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Complaint Registered!", resp.data)

        # Verify saved in MongoDB Atlas
        c_doc = db.complaints.find_one({"title": "Projector HDMI port damaged camera snapshot"})
        self.assertIsNotNone(c_doc)
        self.assertTrue(c_doc.get("photo"))

        # Verify file exists on disk in static/uploads/
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], c_doc["photo"])
        self.assertTrue(os.path.isfile(filepath), f"File {filepath} was not saved on disk")

if __name__ == "__main__":
    unittest.main()

