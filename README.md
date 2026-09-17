# 🏫 Smart Campus Complaint & Resolution Management System

An intelligent, multi-role campus complaint dispatch and resolution platform built with Python (Flask) featuring hybrid AI ticket classification, multi-factor severity prediction, automated department routing, SLA tracking, and dedicated interfaces for **Students**, **Faculty**, and **Administrators**.

---

## 👥 User Roles & Access

| Role | Interface | Capabilities |
| :--- | :--- | :--- |
| 🎓 **Student** | `/student` | Log hostel/campus issues, real-time AI triage preview, view "My Complaints" history, confirm resolution with 5-star ratings. |
| 👨‍🏫 **Faculty** | `/faculty` | Report classroom/lab equipment failures with expedited academic SLA priority (8h), access campus maintenance emergency hotlines. |
| 🛡️ **Administrator** | `/admin` | Central dispatch desk, KPI stats, Chart.js graphs, technician assignment, resolution proof photos, CSV audit export. |

---

## 🔐 Registration & Login Flow

- **Registration First Entry**: New visitors arriving at `http://127.0.0.1:5000/` are guided to the **Registration Screen** (`/register`) to set up their account.
- **Persistent Storage**: All registered user credentials, profile information, roll numbers, and contact details are stored permanently in the SQLite database (`complaints.db`).
- **Persistent Session ("Remember Me")**: Check the "Remember my login" option to keep your login active across browser sessions (30-day session lifetime).
- **Clean Login Interface**: The login screen (`/login`) is clean and professional with no demo account shortcuts or clutter.
- **Admin Registration**: Authorized staff can register an administrative account by entering the campus admin security code (`ADMIN123`).

---

## 🌟 Key Features

1. **Intelligent Registration & Role-Based Access Control**
   - Secure password hashing via `werkzeug.security`.
   - Dedicated role views: `/student`, `/faculty`, `/admin`.
   - Access guards (`@role_required`) preventing cross-role access.

2. **Real-Time AI Auto-Classification Engine**
   - Pure Python TF-IDF + Multinomial Naive Bayes classifier trained across 8 campus categories:
     *Wi-Fi & Networking, Electrical Maintenance, Plumbing & Water Supply, Housekeeping & Sanitation, HVAC & Air Conditioning, Furniture & Classroom, Computing & Lab Hardware, Campus Infrastructure & Safety*.
   - Multi-factor severity scoring detecting hazards (*fire, spark, shock, gas leak*) &rarr; **Critical** (4h SLA).
   - High-impact location multipliers (*Exam Hall, Server Room, Central Library*).
   - Explainable AI reasoning tags and domain keywords.

3. **Dedicated Student Portal** (`/student`)
   - Pre-filled student info (Roll No, Department, Email).
   - Dropzone for photo attachments (JPG, PNG, WEBP) with instant preview.
   - Live AI prediction sidebar with category confidence bar and estimated SLA.
   - "My Complaints" tab tracking submitted issues, technician updates, and rating links.

4. **Dedicated Faculty Portal** (`/faculty`)
   - Specialized academic issue logger (Lecture Theaters, Research Labs, Seminar Halls).
   - Urgency escalation toggle (automatically bumps to High priority with 8h SLA).
   - Direct maintenance officer phone and intercom hotline directory.

5. **Central Admin Operations Portal** (`/admin`)
   - KPI cards: Total Registered, Triaged, In Progress, Resolved / Closed, Critical Safety.
   - Visual Chart.js charts: Category breakdown and Severity distribution.
   - Multi-filtering by Role (Student vs. Faculty submitted), Department, Status, Priority, and Search.
   - Resolution modal for updating status, technician remarks, and attaching resolution proof photos.
   - 1-click CSV audit export.

6. **Public Complaint Tracking & Interactive Stepper** (`/track`)
   - 5-step visual stepper:
     `Submitted` &rarr; `AI Triaged` &rarr; `In Progress` &rarr; `Resolved` &rarr; `Closed`.
   - Before/after evidence photo display and technician resolution notes.
   - Interactive 5-star rating and student confirmation widget.

---

## 🚀 Quickstart Guide

### 1. Installation
```bash
cd c:\Users\ranuc\OneDrive\Desktop\hack\campus-complaint-system\campus-complaint
pip install -r requirements.txt
```

### 2. Run Application
```bash
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## 🧪 Automated Testing

Run the test suite verifying registration, persistent storage, clean login page, AI classification, and role guards:
```bash
python test_system.py
```
```text
Ran 6 tests in 0.412s
OK
```
