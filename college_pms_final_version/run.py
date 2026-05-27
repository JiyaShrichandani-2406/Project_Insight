#!/usr/bin/env python3
"""
College Project Management System
===================================
Run this file to start the application: python run.py

ROLES:
  Admin   (HOD/Coordinator) — reviews ideas, assigns faculty guides
  Faculty (Guide)           — mentors and evaluates assigned projects only
  Student                   — submits ideas, uploads work, tracks progress

DEMO ACCOUNTS:
  Admin   : admin@college.edu    / admin123
  Faculty : faculty@college.edu  / faculty123
  Faculty : amit@college.edu     / amit123
  Student : student@college.edu  / student123
  Student : sneha@college.edu    / sneha123
  Student : rahul@college.edu    / rahul123

ADMIN REGISTRATION CODE (for new admin signups): ADMIN2024
"""

import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Run: pip install flask flask-sqlalchemy flask-login flask-wtf werkzeug requests")
    sys.exit(1)

with app.app_context():
    from app import (User, Project, Milestone, Comment,
                     Notification, Evaluation, Submission)
    from werkzeug.security import generate_password_hash
    from datetime import datetime, timedelta

    db.create_all()

    if not User.query.first():
        print("Seeding demo data...")
        now = datetime.utcnow()

        admin = User(name='Prof. Rajesh Kumar', email='admin@college.edu',
            password=generate_password_hash('admin123'), role='admin',
            college_id='HOD-CS-001', department='Computer Science', avatar_color='#f59e0b', is_approved=True)
        db.session.add(admin)
        db.session.commit()
        print("Fresh admin data seeded!")
        print("Demo data seeded!")
        
print("\n" + "="*52)
print("  🎓 College Project Management System")
print("="*52)
print("  URL     : http://localhost:5000")
print()
print("  ADMIN   : admin@college.edu    / admin123")
print()
print("  Admin registration code : ADMIN2024")
print("="*52 + "\n")

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
