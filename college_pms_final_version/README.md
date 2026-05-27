# 🎓 College Project Management System

A full-stack web application for managing minor and major college projects — built with Flask, SQLite, and a modern dark UI.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install flask flask-sqlalchemy flask-login flask-wtf werkzeug requests
```

### 2. Run the app
```bash
python run.py
```

### 3. Open in browser
Visit: **http://localhost:5000**

---

## 🔐 Demo Accounts

| Role    | Email                    | Password    |
|---------|--------------------------|-------------|
| Faculty | faculty@college.edu      | faculty123  |
| Student | student@college.edu      | student123  |
| Student | sneha@college.edu        | sneha123    |

---

## 📁 Project Structure

```
college_pms/
├── app.py                  # Flask app, all routes, models, APIs
├── run.py                  # Startup script with auto-seeding
├── README.md
├── college_pms.db          # SQLite database (auto-created)
├── templates/
│   ├── base.html           # Layout: sidebar, topbar, notifications
│   ├── login.html          # Split-screen login
│   ├── signup.html         # Role-based signup
│   ├── student_dashboard.html
│   ├── faculty_dashboard.html
│   ├── projects.html       # Card grid with filters
│   ├── new_project.html    # Idea submission form
│   ├── project_detail.html # Tabbed project hub
│   ├── analytics.html      # Faculty reports & charts
│   └── profile.html
└── static/
    └── uploads/            # Uploaded files stored here
```

---

## ✅ Features

### Authentication
- Student & Faculty signup/login
- Faculty must provide official College ID
- Role-based access control (RBAC)
- Session-based auth with Flask-Login

### Project Idea Submission
- Students submit title, description, domain, type (minor/major)
- **Plagiarism check**: flags duplicate titles or >75% description similarity
- Faculty approve/reject with feedback
- Faculty guide assignment on approval

### Presentation Module
- Upload PPT, PDF, ZIP files (up to 50MB)
- Faculty can view downloads and leave comments

### Code Submission
- GitHub repository link submission
- **Live GitHub API integration**: fetches stars, forks, language, last update

### Final Submission
- Upload final project files
- Submit deployment URL and demo video link
- Marks project as "completed"

### Evaluation System
- Faculty scores: Presentation, Frontend, Backend, Overall (each /100)
- Auto-calculated average total score
- Remarks/feedback displayed to student
- Student notified on evaluation

### Dashboard
- Stats cards: total, pending, approved, completed
- Recent activity and notifications
- Quick actions

### Timeline & Milestones
- Auto-generated milestones on approval
- Click to mark milestones complete
- Overdue detection with visual alerts

### Chat / Comment System
- Module-tagged comments (idea, presentation, code, evaluation)
- Chat-bubble style UI per project
- Notifications on new messages

### Notification System
- Notify faculty on new submissions
- Notify students on approval/feedback/evaluation
- Only assigned faculty receives submission notifications
- Notification panel in topbar with unread count

### Plagiarism Check
- Title exact-match detection
- Description similarity threshold (>75% = flagged)

### Analytics (Faculty Only)
- Status distribution donut chart
- Average marks breakdown by category
- Projects by domain bar chart
- Top projects leaderboard
- Full project table with CSV export

---

## 🛠 Tech Stack

| Layer       | Technology                |
|-------------|---------------------------|
| Backend     | Python 3, Flask           |
| Database    | SQLite (via SQLAlchemy)   |
| Auth        | Flask-Login + Werkzeug    |
| Frontend    | HTML5, CSS3, Vanilla JS   |
| Charts      | Chart.js                  |
| File Upload | Werkzeug secure_filename  |
| GitHub API  | requests (REST)           |

---

## 🔌 REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/github-info?url=` | Fetch GitHub repo details |
| GET | `/api/notifications` | Get user notifications (JSON) |
| GET | `/api/project-stats` | Project counts by month |
| POST | `/notifications/read/<id>` | Mark notification read |
| POST | `/notifications/read-all` | Mark all notifications read |

---

## 🔒 Security Notes

- Passwords hashed with Werkzeug PBKDF2
- File uploads validated by extension whitelist
- Role checks on every protected route
- CSRF protection via Flask-WTF secret key
- SQL injection prevented via SQLAlchemy ORM

---

## 📦 Switching to MySQL

Change this line in `app.py`:
```python
# SQLite (default)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///college_pms.db'

# MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://user:password@localhost/college_pms'
```
Install: `pip install pymysql`
