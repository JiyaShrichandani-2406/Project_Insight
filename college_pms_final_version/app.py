from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os, re, requests, json

from dotenv import load_dotenv
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY and genai:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'college_pms_secret_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/college_pms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'ppt', 'pptx', 'mp4', 'avi', 'mov', 'zip', 'rar'}
AVATAR_COLORS = ['#6366f1','#ec4899','#14b8a6','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#10b981']

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
os.makedirs('static/uploads', exist_ok=True)

# ─── MODELS ──────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password      = db.Column(db.String(200), nullable=False)
    # ROLES: 'student' | 'faculty' | 'admin'
    # admin  = HOD / Coordinator — approves ideas, assigns faculty guides
    # faculty = Guide — mentors and evaluates assigned projects only
    # student = submits ideas, works on projects
    role          = db.Column(db.String(20), nullable=False)
    college_id    = db.Column(db.String(50))
    department    = db.Column(db.String(100))
    semester      = db.Column(db.String(20))
    enrollment    = db.Column(db.String(50))
    avatar_color  = db.Column(db.String(10), default='#6366f1')
    is_approved   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Project(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    title           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text, nullable=False)
    domain          = db.Column(db.String(100))
    project_type    = db.Column(db.String(20), default='minor')
    # STATUS FLOW:
    # pending  → admin reviews → approved (with faculty assigned) or rejected
    # approved → student works → completed
    status          = db.Column(db.String(30), default='pending')
    student_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # faculty_id = the assigned GUIDE
    faculty_id      = db.Column(db.Integer, db.ForeignKey('user.id'))
    team_details    = db.Column(db.Text)
    feedback        = db.Column(db.Text)
    github_link     = db.Column(db.String(300))
    deployment_link = db.Column(db.String(300))
    similarity_score= db.Column(db.Float, default=0.0)
    similarity_reason= db.Column(db.Text)
    presentation_date = db.Column(db.DateTime)
    frontend_date     = db.Column(db.DateTime)
    backend_date      = db.Column(db.DateTime)
    report_date       = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)
    student         = db.relationship('User', foreign_keys=[student_id], backref='projects')
    faculty         = db.relationship('User', foreign_keys=[faculty_id], backref='guided_projects')

class Submission(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    project_id      = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    submission_type = db.Column(db.String(30))
    file_path       = db.Column(db.String(300))
    github_link     = db.Column(db.String(300))
    deployment_link = db.Column(db.String(300))
    demo_video      = db.Column(db.String(300))
    notes           = db.Column(db.Text)
    submitted_at    = db.Column(db.DateTime, default=datetime.utcnow)
    project         = db.relationship('Project', backref='submissions')

class Evaluation(db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    project_id          = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    faculty_id          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    presentation_marks  = db.Column(db.Float, default=0)
    frontend_marks      = db.Column(db.Float, default=0)
    backend_marks       = db.Column(db.Float, default=0)
    report_marks        = db.Column(db.Float, default=0)
    overall_marks       = db.Column(db.Float, default=0)
    total_marks         = db.Column(db.Float, default=0)
    remarks             = db.Column(db.Text)
    evaluated_at        = db.Column(db.DateTime, default=datetime.utcnow)
    project             = db.relationship('Project', backref='evaluations')
    faculty             = db.relationship('User', backref='evaluations')

class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    module     = db.Column(db.String(30), default='general')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user       = db.relationship('User', backref='comments')
    project    = db.relationship('Project', backref='comments')

class Notification(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    link       = db.Column(db.String(200))
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user       = db.relationship('User', backref='notifications')

class Milestone(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    title      = db.Column(db.String(200), nullable=False)
    description= db.Column(db.Text)
    due_date   = db.Column(db.DateTime)
    status     = db.Column(db.String(20), default='pending')
    project    = db.relationship('Project', backref='milestones')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_notification(user_id, message, link=None):
    db.session.add(Notification(user_id=user_id, message=message, link=link))
    db.session.commit()

def check_plagiarism(title, description, exclude_id=None):
    q = Project.query
    if exclude_id:
        q = q.filter(Project.id != exclude_id)
    
    other_projects_data = []
    for p in q.all():
        other_projects_data.append(f"Title: {p.title}\nDesc: {p.description}")
        
    if ai_client and other_projects_data:
        try:
            prompt = f"Analyze if the following proposed project is similar to any existing projects based on title and description semantics.\n\nProposed Project:\nTitle: {title}\nDescription: {description}\n\nExisting Projects:\n"
            prompt += "\n\n".join(other_projects_data)
            prompt += "\n\nCompare the proposed project against the existing projects. Calculate a similarity percentage from 0 to 100 based on core idea overlap. Respond strictly in JSON format: {\"similarity_percentage\": 45, \"reason\": \"<p><strong>Overlap:</strong>...</p><ul><li>...</li></ul><p><strong>Conclusion:</strong>...</p>\"}. Use simple HTML tags like <p>, <strong>, <ul>, <li> to structure the reason nicely."
            
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            result = json.loads(response.text)
            
            # Extract percentage safely
            score = float(result.get('similarity_percentage', 0.0))
            reason = result.get('reason', 'AI analyzed the similarity.')
            return score, reason
        except Exception as e:
            print("AI Similarity check failed:", e)
            return 0.0, "AI check failed or unavailable."

    return 0.0, "No existing projects to compare against."

def is_admin():
    return current_user.is_authenticated and current_user.role == 'admin'

def is_faculty():
    return current_user.is_authenticated and current_user.role in ('faculty', 'admin')

# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email','').strip()).first()
        if user and check_password_hash(user.password, request.form.get('password','')):
            if not user.is_approved:
                flash('Your account is pending admin approval. You cannot log in yet.', 'error')
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name       = request.form.get('name','').strip()
        email      = request.form.get('email','').strip()
        password   = request.form.get('password','')
        role       = request.form.get('role','student')
        college_id = request.form.get('college_id','').strip()
        department = request.form.get('department','').strip()
        semester   = request.form.get('semester','').strip()
        enrollment = request.form.get('enrollment','').strip()
        admin_code = request.form.get('admin_code','').strip()

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('signup.html')

        # Admin registration is disabled
        if role == 'admin':
            flash('Admin registration is disabled. Please contact the system administrator.', 'error')
            return render_template('signup.html')

        # Faculty registration requires college ID
        if role == 'faculty' and not college_id:
            flash('Faculty must provide official college ID', 'error')
            return render_template('signup.html')

        color = AVATAR_COLORS[User.query.count() % len(AVATAR_COLORS)]
        # Admins are automatically approved.
        is_approved = True if role == 'admin' else False
        user = User(name=name, email=email,
                    password=generate_password_hash(password),
                    role=role, college_id=college_id,
                    department=department, semester=semester, enrollment=enrollment,
                    avatar_color=color, is_approved=is_approved)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Please wait for admin approval before logging in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/review_user/<int:user_id>', methods=['POST'])
@login_required
def review_user(user_id):
    if not is_admin():
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
    
    action = request.form.get('action')
    user = User.query.get_or_404(user_id)
    
    if action == 'approve':
        user.is_approved = True
        db.session.commit()
        send_notification(user.id, "🎉 Your account has been approved by the Admin!")
        flash(f'User {user.name} approved successfully!', 'success')
    elif action == 'reject':
        db.session.delete(user)
        db.session.commit()
        flash(f'User account registration rejected.', 'success')
        
    return redirect(url_for('dashboard'))

# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False)\
                               .order_by(Notification.created_at.desc()).limit(5).all()

    if current_user.role == 'student':
        projects = Project.query.filter_by(student_id=current_user.id).all()
        stats = {
            'total':     len(projects),
            'pending':   sum(1 for p in projects if p.status == 'pending'),
            'approved':  sum(1 for p in projects if p.status == 'approved'),
            'completed': sum(1 for p in projects if p.status == 'completed'),
            'rejected':  sum(1 for p in projects if p.status == 'rejected'),
        }
        return render_template('student_dashboard.html', projects=projects,
                               stats=stats, notifications=notifs)

    elif current_user.role == 'faculty':
        # Faculty only sees projects assigned to them
        my_projects = Project.query.filter_by(faculty_id=current_user.id).all()
        stats = {
            'guided':    len(my_projects),
            'approved':  sum(1 for p in my_projects if p.status == 'approved'),
            'completed': sum(1 for p in my_projects if p.status == 'completed'),
            'evaluated': sum(1 for p in my_projects if p.evaluations),
        }
        return render_template('faculty_dashboard.html', projects=my_projects,
                               stats=stats, notifications=notifs)

    else:  # admin
        # Admin sees everything
        all_projects = Project.query.order_by(Project.created_at.desc()).all()
        pending      = Project.query.filter_by(status='pending').all()
        faculty_list = User.query.filter_by(role='faculty').order_by(User.name).all()
        unapproved_users = User.query.filter_by(is_approved=False).all()
        stats = {
            'total':     Project.query.count(),
            'pending':   len(pending),
            'approved':  Project.query.filter_by(status='approved').count(),
            'completed': Project.query.filter_by(status='completed').count(),
            'students':  User.query.filter_by(role='student').count(),
            'faculty':   User.query.filter_by(role='faculty').count(),
        }
        return render_template('admin_dashboard.html', all_projects=all_projects,
                               pending=pending, faculty_list=faculty_list,
                               unapproved_users=unapproved_users, stats=stats, notifications=notifs)

# ─── PROJECTS ────────────────────────────────────────────────────────────────

@app.route('/projects')
@login_required
def projects():
    if current_user.role == 'student':
        all_projects = Project.query.filter_by(student_id=current_user.id)\
                                    .order_by(Project.created_at.desc()).all()
    elif current_user.role == 'faculty':
        all_projects = Project.query.filter_by(faculty_id=current_user.id)\
                                    .order_by(Project.created_at.desc()).all()
    else:  # admin sees all
        all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('projects.html', projects=all_projects)

@app.route('/projects/new', methods=['GET','POST'])
@login_required
def new_project():
    if current_user.role != 'student':
        flash('Only students can submit project ideas', 'error')
        return redirect(url_for('dashboard'))
    if not getattr(current_user, 'is_approved', True):
        flash('Your account is pending admin approval.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title        = request.form.get('title','').strip()
        description  = request.form.get('description','').strip()
        domain       = request.form.get('domain','').strip()
        project_type = request.form.get('project_type','minor')
        score, reason = check_plagiarism(title, description)

        project = Project(title=title, description=description,
                          domain=domain, project_type=project_type,
                          student_id=current_user.id,
                          similarity_score=score, similarity_reason=reason)
        db.session.add(project)
        db.session.commit()

        # Notify all admins
        for admin in User.query.filter_by(role='admin').all():
            send_notification(admin.id,
                f"💡 New project idea submitted for review: '{title}' by {current_user.name}",
                url_for('project_detail', project_id=project.id))

        # Auto milestones
        for m_title, days in [('Idea Submission',0),('Team Details',7),('Presentation',21),
                               ('Code Submission',35),('Final Submission',49)]:
            db.session.add(Milestone(project_id=project.id, title=m_title,
                status='completed' if days==0 else 'pending',
                due_date=datetime.utcnow()+timedelta(days=days)))
        db.session.commit()

        flash('Project idea submitted! Waiting for faculty review.', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    
    faculty_list = User.query.filter_by(role='faculty', is_approved=True).all()
    return render_template('new_project.html', faculty_list=faculty_list)

@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Enforce Privacy: Only admin, the owning student, or assigned faculty can view
    if current_user.role == 'student' and project.student_id != current_user.id:
        flash('You do not have permission to view this project.', 'error')
        return redirect(url_for('dashboard'))
    if current_user.role == 'faculty' and project.faculty_id != current_user.id:
        flash('You can only view projects assigned to you.', 'error')
        return redirect(url_for('dashboard'))

    comments    = Comment.query.filter_by(project_id=project_id)\
                               .order_by(Comment.created_at.asc()).all()
    submissions = Submission.query.filter_by(project_id=project_id)\
                                  .order_by(Submission.submitted_at.desc()).all()
    evaluation  = Evaluation.query.filter_by(project_id=project_id).first()
    milestones  = Milestone.query.filter_by(project_id=project_id)\
                                 .order_by(Milestone.due_date.asc()).all()
    faculty_list= User.query.filter_by(role='faculty').order_by(User.name).all()
    
    team_data = None
    if project.team_details:
        import json
        try:
            team_data = json.loads(project.team_details)
        except:
            pass

    return render_template('project_detail.html', project=project,
                           comments=comments, submissions=submissions,
                           evaluation=evaluation, milestones=milestones,
                           faculty_list=faculty_list, team_data=team_data)

# ─── FACULTY: APPROVE / REJECT ────────────────────────────────

@app.route('/projects/<int:project_id>/review', methods=['POST'])
@login_required
def review_project(project_id):
    project = Project.query.get_or_404(project_id)
    if not is_admin():
        flash('Only admin can approve or reject project ideas.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    action   = request.form.get('action')
    feedback = request.form.get('feedback','').strip()

    if action == 'approve':
        project.status     = 'approved'
        project.feedback   = feedback
        project.updated_at = datetime.utcnow()
        db.session.commit()
        send_notification(project.student_id,
            f"✅ Your project '{project.title}' was approved by {current_user.name}!",
            url_for('project_detail', project_id=project_id))
        flash("Project approved!", 'success')

    elif action == 'reject':
        project.status     = 'rejected'
        project.feedback   = feedback
        project.updated_at = datetime.utcnow()
        db.session.commit()
        send_notification(project.student_id,
            f"❌ Your project '{project.title}' was rejected. Feedback: {feedback}",
            url_for('project_detail', project_id=project_id))
        flash('Project rejected.', 'success')

    if request.form.get('source') == 'dashboard':
        return redirect(url_for('dashboard'))
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/projects/<int:project_id>/team', methods=['POST'])
@login_required
def submit_team(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.id != project.student_id:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
    
    # Store team details as JSON
    import json
    team_data = {
        'project_name': request.form.get('project_name',''),
        'description': request.form.get('description',''),
        'leader_name': request.form.get('leader_name',''),
        'leader_roll': request.form.get('leader_roll',''),
        'members': [],
        'approved': False
    }
    for i in range(1, 5):
        m_name = request.form.get(f'member_{i}_name')
        m_roll = request.form.get(f'member_{i}_roll')
        if m_name and m_roll:
            team_data['members'].append({'name': m_name, 'roll': m_roll})
            
    project.team_details = json.dumps(team_data)
    db.session.commit()
    
    # Notify all admins to assign a faculty guide
    for admin in User.query.filter_by(role='admin').all():
        send_notification(admin.id,
            f"👥 Team details submitted for '{project.title}'. Please assign a faculty guide.",
            url_for('project_detail', project_id=project.id))

    flash('Team details submitted! Waiting for Admin to assign a faculty guide.', 'success')
    
    # Mark Team Details milestone as completed if exists
    ms = Milestone.query.filter_by(project_id=project.id, title='Team Details').first()
    if ms:
        ms.status = 'completed'
        db.session.commit()
        
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/projects/<int:project_id>/approve_team', methods=['POST'])
@login_required
def approve_team(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.role not in ['admin', 'faculty']:
        flash('Unauthorized', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
        
    if project.team_details:
        import json
        team_data = json.loads(project.team_details)
        team_data['approved'] = True
        project.team_details = json.dumps(team_data)
        db.session.commit()
        send_notification(project.student_id, f"✅ Your team details for '{project.title}' have been approved!", url_for('project_detail', project_id=project.id))
        flash('Team details approved!', 'success')
        
    return redirect(url_for('project_detail', project_id=project_id))

# ─── ADMIN: REASSIGN FACULTY ─────────────────────────────────────────────────

@app.route('/projects/<int:project_id>/reassign', methods=['POST'])
@login_required
def reassign_faculty(project_id):
    if not is_admin():
        flash('Only admin can reassign faculty', 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    project    = Project.query.get_or_404(project_id)
    faculty_id = request.form.get('faculty_id','')
    if not faculty_id:
        flash('Please select a faculty member', 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    old_faculty        = project.faculty
    new_faculty        = User.query.get(int(faculty_id))
    project.faculty_id = int(faculty_id)
    project.updated_at = datetime.utcnow()
    db.session.commit()

    # Notify student
    send_notification(project.student_id,
        f"🔄 Your project guide has been changed to {new_faculty.name}",
        url_for('project_detail', project_id=project_id))

    # Notify new faculty
    send_notification(int(faculty_id),
        f"📋 You have been assigned as guide for '{project.title}' "
        f"by {project.student.name}",
        url_for('project_detail', project_id=project_id))

    flash(f"Faculty guide reassigned to {new_faculty.name}!", 'success')
    return redirect(url_for('project_detail', project_id=project_id))

# ─── ADMIN: MARK COMPLETED ───────────────────────────────────────────────────

@app.route('/projects/<int:project_id>/complete', methods=['POST'])
@login_required
def complete_project(project_id):
    if not is_admin():
        flash('Only admin can mark projects complete', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    project = Project.query.get_or_404(project_id)
    project.status     = 'completed'
    project.updated_at = datetime.utcnow()
    db.session.commit()
    send_notification(project.student_id,
        f"🎉 Your project '{project.title}' has been marked as completed!",
        url_for('project_detail', project_id=project_id))
    flash('Project marked as completed!', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

# ─── SUBMISSIONS ─────────────────────────────────────────────────────────────

@app.route('/projects/<int:project_id>/submit', methods=['POST'])
@login_required
def submit_work(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.role == 'student' and project.student_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))

    sub_type        = request.form.get('submission_type')
    notes           = request.form.get('notes','')
    github_link     = request.form.get('github_link','').strip()
    deployment_link = request.form.get('deployment_link','').strip()
    demo_video      = request.form.get('demo_video','').strip()

    submission = Submission(project_id=project_id, submission_type=sub_type,
                            notes=notes, github_link=github_link,
                            deployment_link=deployment_link, demo_video=demo_video)

    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{project_id}_{sub_type}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            submission.file_path = filename

    db.session.add(submission)

    if sub_type == 'final':
        project.deployment_link = deployment_link
    if github_link:
        project.github_link = github_link
    project.updated_at = datetime.utcnow()
    db.session.commit()

    # Notify assigned faculty guide
    if project.faculty_id:
        send_notification(project.faculty_id,
            f"📤 {current_user.name} submitted {sub_type} for '{project.title}'",
            url_for('project_detail', project_id=project_id))

    # Also notify admin
    for admin in User.query.filter_by(role='admin').all():
        send_notification(admin.id,
            f"📤 {current_user.name} submitted {sub_type} for '{project.title}'",
            url_for('project_detail', project_id=project_id))

    flash(f'{sub_type.capitalize()} submitted successfully!', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

# ─── EVALUATION (faculty guide only) ─────────────────────────────────────────

@app.route('/project/<int:project_id>/deadlines', methods=['POST'])
@login_required
def set_deadlines(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.role not in ['faculty', 'admin'] or (current_user.role == 'faculty' and project.faculty_id != current_user.id):
        flash('Unauthorized to set deadlines for this project', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    
    try:
        if request.form.get('presentation_date'):
            project.presentation_date = datetime.strptime(request.form.get('presentation_date'), '%Y-%m-%dT%H:%M')
        if request.form.get('frontend_date'):
            project.frontend_date = datetime.strptime(request.form.get('frontend_date'), '%Y-%m-%dT%H:%M')
        if request.form.get('backend_date'):
            project.backend_date = datetime.strptime(request.form.get('backend_date'), '%Y-%m-%dT%H:%M')
        if request.form.get('report_date'):
            project.report_date = datetime.strptime(request.form.get('report_date'), '%Y-%m-%dT%H:%M')
        
        db.session.commit()
        send_notification(project.student_id, f"📅 Deadlines updated for '{project.title}' by {current_user.name}", url_for('project_detail', project_id=project.id))
        flash('Deadlines successfully updated', 'success')
    except Exception as e:
        flash(f'Error updating deadlines: {str(e)}', 'error')
    
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/project/<int:project_id>/evaluate', methods=['POST'])
@login_required
def evaluate_project(project_id):
    if not is_faculty():
        flash('Only faculty can evaluate projects', 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    project = Project.query.get_or_404(project_id)

    # Regular faculty can only evaluate their own assigned projects
    if current_user.role == 'faculty' and project.faculty_id != current_user.id:
        flash('You can only evaluate projects assigned to you', 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    def safe_float(val):
        try:
            return float(val) if val else 0.0
        except ValueError:
            return 0.0

    pres    = safe_float(request.form.get('presentation_marks'))
    front   = safe_float(request.form.get('frontend_marks'))
    back    = safe_float(request.form.get('backend_marks'))
    report  = safe_float(request.form.get('report_marks'))
    overall = safe_float(request.form.get('overall_marks'))
    remarks = request.form.get('remarks','')
    total   = round((pres + front + back + report + overall), 2)

    existing = Evaluation.query.filter_by(project_id=project_id).first()
    if existing:
        existing.presentation_marks = pres
        existing.frontend_marks     = front
        existing.backend_marks      = back
        existing.report_marks       = report
        existing.overall_marks      = overall
        existing.total_marks        = total
        existing.remarks            = remarks
        existing.evaluated_at       = datetime.utcnow()
    else:
        db.session.add(Evaluation(
            project_id=project_id, faculty_id=current_user.id,
            presentation_marks=pres, frontend_marks=front,
            backend_marks=back, report_marks=report, overall_marks=overall,
            total_marks=total, remarks=remarks))

    db.session.commit()

    send_notification(project.student_id,
        f"⭐ Your project '{project.title}' has been evaluated! Score: {total}/10",
        url_for('project_detail', project_id=project_id))

    flash('Evaluation saved successfully!', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

# ─── COMMENTS ────────────────────────────────────────────────────────────────

@app.route('/projects/<int:project_id>/comment', methods=['POST'])
@login_required
def add_comment(project_id):
    content = request.form.get('content','').strip()
    module  = request.form.get('module','general')
    if not content:
        flash('Comment cannot be empty', 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    db.session.add(Comment(project_id=project_id, user_id=current_user.id,
                           content=content, module=module))
    db.session.commit()

    project = Project.query.get(project_id)
    # Notify relevant people
    notify_ids = set()
    if current_user.role == 'student':
        if project.faculty_id: notify_ids.add(project.faculty_id)
        for admin in User.query.filter_by(role='admin').all():
            notify_ids.add(admin.id)
    else:
        notify_ids.add(project.student_id)

    for uid in notify_ids:
        if uid != current_user.id:
            send_notification(uid,
                f"💬 {current_user.name} commented on '{project.title}'",
                url_for('project_detail', project_id=project_id))

    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id and current_user.role not in ('admin','faculty'):
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'status': 'ok'})

# ─── PROJECT EDIT / DELETE ───────────────────────────────────────────────────

@app.route('/projects/<int:project_id>/edit', methods=['GET','POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.role == 'student' and project.student_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
    if project.status not in ('pending','rejected'):
        flash('Only pending or rejected projects can be edited', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    if request.method == 'POST':
        title        = request.form.get('title','').strip()
        description  = request.form.get('description','').strip()
        domain       = request.form.get('domain','').strip()
        project_type = request.form.get('project_type','minor')

        plagiarized, reason = check_plagiarism(title, description, exclude_id=project_id)
        if plagiarized:
            flash(f'Plagiarism detected: {reason}', 'error')
            return render_template('edit_project.html', project=project)

        project.title        = title
        project.description  = description
        project.domain       = domain
        project.project_type = project_type
        project.status       = 'pending'
        project.feedback     = None
        project.updated_at   = datetime.utcnow()
        db.session.commit()

        for admin in User.query.filter_by(role='admin').all():
            send_notification(admin.id,
                f"🔄 Project resubmitted: '{title}' by {current_user.name}",
                url_for('project_detail', project_id=project_id))

        flash('Project updated and resubmitted for admin review!', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    return render_template('edit_project.html', project=project)

@app.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.role == 'student' and project.student_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
    if project.status not in ('pending','rejected'):
        flash('Only pending or rejected projects can be deleted', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    title = project.title
    for model in [Comment, Submission, Milestone, Evaluation]:
        model.query.filter_by(project_id=project_id).delete()
    db.session.delete(project)
    db.session.commit()
    flash(f"Project '{title}' deleted.", 'success')
    return redirect(url_for('projects'))

# ─── MILESTONES ──────────────────────────────────────────────────────────────

@app.route('/projects/<int:project_id>/milestone/add', methods=['POST'])
@login_required
def add_milestone(project_id):
    title   = request.form.get('title','').strip()
    due_str = request.form.get('due_date','')
    if not title:
        flash('Milestone title required', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    due = None
    if due_str:
        try: due = datetime.strptime(due_str, '%Y-%m-%d')
        except: pass
    db.session.add(Milestone(project_id=project_id, title=title, due_date=due))
    db.session.commit()
    flash('Milestone added!', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/projects/<int:project_id>/milestone/<int:ms_id>/done', methods=['POST'])
@login_required
def complete_milestone(project_id, ms_id):
    ms = Milestone.query.get_or_404(ms_id)
    ms.status = 'completed'
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/projects/<int:project_id>/milestone/<int:ms_id>/delete', methods=['POST'])
@login_required
def delete_milestone(project_id, ms_id):
    if not is_faculty():
        return jsonify({'error': 'Unauthorized'}), 403
    ms = Milestone.query.get_or_404(ms_id)
    db.session.delete(ms)
    db.session.commit()
    return jsonify({'status': 'ok'})

# ─── SUBMISSIONS DELETE ───────────────────────────────────────────────────────

@app.route('/submission/<int:sub_id>/delete', methods=['POST'])
@login_required
def delete_submission(sub_id):
    sub     = Submission.query.get_or_404(sub_id)
    project = Project.query.get(sub.project_id)
    if current_user.role == 'student' and project.student_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if sub.file_path:
        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], sub.file_path))
        except: pass
    db.session.delete(sub)
    db.session.commit()
    flash('Submission deleted.', 'success')
    return redirect(url_for('project_detail', project_id=project.id))

# ─── SECURE DOWNLOAD ─────────────────────────────────────────────────────────

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    from flask import send_from_directory, abort
    sub = Submission.query.filter_by(file_path=filename).first()
    if not sub: abort(404)
    project = Project.query.get(sub.project_id)
    if current_user.role == 'student' and project.student_id != current_user.id:
        abort(403)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# ─── NOTIFICATIONS ───────────────────────────────────────────────────────────

@app.route('/api/notifications')
@login_required
def get_notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
                               .order_by(Notification.created_at.desc()).limit(20).all()
    return jsonify([{'id':n.id,'message':n.message,'link':n.link,
                     'is_read':n.is_read,'time':n.created_at.strftime('%b %d, %H:%M')}
                    for n in notifs])

@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    n = Notification.query.get_or_404(notif_id)
    if n.user_id == current_user.id:
        n.is_read = True
        db.session.commit()
    return jsonify({'status':'ok'})

@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False)\
                      .update({'is_read': True})
    db.session.commit()
    return jsonify({'status':'ok'})

# ─── PROFILE ─────────────────────────────────────────────────────────────────

@app.route('/profile')
@login_required
def profile():
    if current_user.role == 'student':
        my_projects = Project.query.filter_by(student_id=current_user.id).all()
    elif current_user.role == 'faculty':
        my_projects = Project.query.filter_by(faculty_id=current_user.id).all()
    else:
        my_projects = Project.query.all()
    return render_template('profile.html', projects=my_projects)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    current_user.name       = request.form.get('name', current_user.name).strip()
    current_user.department = request.form.get('department','').strip()
    db.session.commit()
    flash('Profile updated!', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    if not check_password_hash(current_user.password, request.form.get('current_password','')):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('profile'))
    new_pw = request.form.get('new_password','')
    if len(new_pw) < 8:
        flash('New password must be at least 8 characters', 'error')
        return redirect(url_for('profile'))
    if new_pw != request.form.get('confirm_password',''):
        flash('Passwords do not match', 'error')
        return redirect(url_for('profile'))
    current_user.password = generate_password_hash(new_pw)
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile'))

# ─── SEARCH ──────────────────────────────────────────────────────────────────

@app.route('/search')
@login_required
def search():
    q       = request.args.get('q','').strip()
    results = []
    if len(q) >= 2:
        like = f'%{q}%'
        base = Project.query
        if current_user.role == 'student':
            base = base.filter_by(student_id=current_user.id)
        elif current_user.role == 'faculty':
            base = base.filter_by(faculty_id=current_user.id)
        results = base.filter(
            (Project.title.ilike(like)) |
            (Project.description.ilike(like)) |
            (Project.domain.ilike(like))
        ).order_by(Project.created_at.desc()).all()
    return render_template('search.html', results=results, q=q)

# ─── STUDENTS DIRECTORY (admin + faculty) ────────────────────────────────────

@app.route('/students')
@login_required
def students():
    if current_user.role == 'student':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    all_students = User.query.filter_by(role='student').order_by(User.name).all()
    data = []
    for s in all_students:
        projs  = Project.query.filter_by(student_id=s.id).all()
        if current_user.role == 'faculty':
            projs = [p for p in projs if p.status in ('approved', 'completed')]
            
        scores = [p.evaluations[0].total_marks for p in projs if p.evaluations]
        data.append({'user':s,'projects':projs,'total':len(projs),
                     'completed':sum(1 for p in projs if p.status=='completed'),
                     'avg_score':round(sum(scores)/len(scores),1) if scores else None})
    return render_template('students.html', student_data=data)



# ─── GITHUB API ──────────────────────────────────────────────────────────────

@app.route('/api/github-info')
@login_required
def github_info():
    url   = request.args.get('url','')
    match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', url)
    if not match:
        return jsonify({'error': 'Invalid GitHub URL'})
    owner, repo = match.group(1), match.group(2).rstrip('.git')
    try:
        r = requests.get(f'https://api.github.com/repos/{owner}/{repo}', timeout=5)
        if r.status_code == 200:
            d = r.json()
            return jsonify({'name':d.get('name'),'description':d.get('description'),
                            'stars':d.get('stargazers_count',0),'forks':d.get('forks_count',0),
                            'language':d.get('language'),'updated_at':d.get('updated_at'),
                            'open_issues':d.get('open_issues_count',0)})
        return jsonify({'error': 'Repository not found or private'})
    except:
        return jsonify({'error': 'Could not fetch repo info'})

@app.route('/api/project-stats')
@login_required
def project_stats():
    if current_user.role == 'student':
        projs = Project.query.filter_by(student_id=current_user.id).all()
    elif current_user.role == 'faculty':
        projs = Project.query.filter_by(faculty_id=current_user.id).all()
    else:
        projs = Project.query.all()
    by_month = {}
    for p in projs:
        key = p.created_at.strftime('%b %Y')
        by_month[key] = by_month.get(key,0)+1
    return jsonify({'by_month':by_month,'total':len(projs)})

# ─── AI FEATURES ─────────────────────────────────────────────────────────────

@app.route('/api/ai/evaluate_idea', methods=['POST'])
@login_required
def ai_evaluate_idea():
    title = request.json.get('title', '')
    description = request.json.get('description', '')
    if not title or not description:
        return jsonify({'error': 'Title and description required'})
    
    if not ai_client:
        return jsonify({'error': 'AI not configured'})

    prompt = f"Evaluate the following college project idea based on viability, complexity, and uniqueness. Provide constructive feedback on whether it's a 'Good Idea', 'Needs Improvement', or 'Too Simple/Complex'.\nTitle: {title}\nDescription: {description}\n\nRespond strictly in JSON format: {{\"status\": \"Good Idea\"|\"Needs Improvement\", \"feedback\": \"detailed feedback\"}}"
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return jsonify(json.loads(response.text))
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/ai/generate_docs/<int:project_id>', methods=['POST'])
@login_required
def ai_generate_docs(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user.role == 'student' and project.student_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    if not ai_client:
        return jsonify({'error': 'AI not configured'})
        
    import json
    team_info = "Solo Project"
    if project.team_details:
        try:
            team_data = json.loads(project.team_details)
            team_info = f"Leader: {team_data.get('leader_name')} ({team_data.get('leader_roll')})\n"
            members = team_data.get('members', [])
            if members:
                team_info += "Members:\n" + "\n".join([f"- {m['name']} ({m['roll']})" for m in members])
        except:
            pass

    prompt = f"Generate a comprehensive markdown documentation (README style) for the following college project:\nTitle: {project.title}\nDescription: {project.description}\nDomain: {project.domain}\nTeam Info:\n{team_info}\n\nInclude sections like: Project Overview, Features, Architecture, Technologies Used, Setup Instructions, and Future Scope. Keep it professional."
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return jsonify({'markdown': response.text})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/ai/similarity', methods=['POST'])
@login_required
def ai_similarity():
    title = request.json.get('title', '')
    description = request.json.get('description', '')
    if not title or not description:
        return jsonify({'error': 'Title and description required'})
    is_sim, reason = check_plagiarism(title, description)
    return jsonify({'is_similar': is_sim, 'reason': reason})

@app.route('/api/ai/feedback', methods=['POST'])
@login_required
def ai_feedback():
    if not is_faculty() and not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    if not ai_client:
        return jsonify({'error': 'Gemini API Key not configured in .env'})
    
    data = request.json
    project_id = data.get('project_id')
    pres = data.get('presentation', 0)
    front = data.get('frontend', 0)
    back = data.get('backend', 0)
    overall = data.get('overall', 0)
    
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'})
    
    prompt = f"Generate constructive, encouraging, and detailed academic feedback (around 3-4 sentences) for a college project titled '{project.title}'. Domain: {project.domain}. Student scored: Presentation {pres}/10, Frontend {front}/10, Backend {back}/10, Overall {overall}/10. Highlight strengths and suggest 1-2 areas of improvement. Keep it professional and direct, without introductory fluff."
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return jsonify({'feedback': response.text.strip()})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/ai/suggest_marks/<int:project_id>', methods=['POST'])
@login_required
def ai_suggest_marks(project_id):
    if not is_faculty() and not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    if not ai_client:
        return jsonify({'error': 'Gemini API Key not configured in .env'})

    project = Project.query.get_or_404(project_id)
    
    # Collect submission details to send to the AI
    submission_details = []
    for sub in project.submissions:
        details = f"- Type: {sub.submission_type}"
        if sub.github_link: details += f", GitHub: {sub.github_link}"
        if sub.deployment_link: details += f", Deployment: {sub.deployment_link}"
        if sub.demo_video: details += f", Demo Video: {sub.demo_video}"
        if sub.notes: details += f", Notes: {sub.notes}"
        submission_details.append(details)
        
    submission_text = "\n".join(submission_details) if submission_details else "No submissions yet."
    
    prompt = f"""You are an academic grading assistant. Review the following student submissions for a project and suggest a score out of 10 for each category.
    
Project Title: {project.title}
Domain: {project.domain}
Description: {project.description}

Submissions:
{submission_text}

Analyze the completeness, apparent effort, and links provided. If a category is clearly missing or has no relevant submissions, DO NOT include its key in the JSON response at all. Only suggest scores for the parts that were submitted.
Return a JSON object containing any of these keys ONLY IF they were submitted: "presentation", "frontend", "backend", "report". Each value should be a number from 0 to 10 (can use 0.5 steps)."""

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        marks = json.loads(response.text)
        return jsonify({'marks': marks})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/ai/viva', methods=['POST'])
@login_required
def ai_viva():
    if not is_faculty() and not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    if not ai_client:
        return jsonify({'error': 'Gemini API Key not configured in .env'})
    
    project_id = request.json.get('project_id')
    project = Project.query.get(project_id)
    
    prompt = f"Generate 5 challenging but fair Viva (oral exam) questions for a college student who built this project. Title: {project.title}. Domain: {project.domain}. Description: {project.description}. Focus on technical depth, architecture, and problem-solving. Format the output as a simple JSON array of strings."
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        questions = json.loads(response.text)
        return jsonify({'questions': questions})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/ai/docs', methods=['POST'])
@login_required
def ai_docs():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 403
    if not ai_client:
        return jsonify({'error': 'Gemini API Key not configured in .env'})
        
    project_id = request.json.get('project_id')
    project = Project.query.get(project_id)
    
    prompt = f"Generate a comprehensive and professional README.md structure for the following project. Include sections like Project Overview, Features, Tech Stack, and Setup Instructions. Title: {project.title}. Domain: {project.domain}. Description: {project.description}. Output only the raw markdown text."
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return jsonify({'docs': response.text})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/ai/delay_prediction', methods=['POST'])
@login_required
def ai_delay_prediction():
    if not ai_client:
        return jsonify({'error': 'Gemini API Key not configured in .env'})
    project_id = request.json.get('project_id')
    project = Project.query.get(project_id)
    milestones = Milestone.query.filter_by(project_id=project_id).all()
    
    ms_info = []
    for m in milestones:
        due = m.due_date.strftime('%Y-%m-%d') if m.due_date else 'No Date'
        ms_info.append(f"- {m.title}: {m.status} (Due: {due})")
        
    current_date = datetime.utcnow().strftime('%Y-%m-%d')
    prompt = f'''
Analyze the project timeline and predict if it is at risk of delay.
Project: {project.title}
Status: {project.status}
Current Date: {current_date}

Milestones:
{chr(10).join(ms_info)}

Respond strictly in JSON: {{"status": "On Track" | "At Risk" | "Delayed", "suggestion": "1-2 sentences of advice on how to improve or maintain progress"}}
'''
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return jsonify(json.loads(response.text))
    except Exception as e:
        return jsonify({'error': str(e)})

# ─── CONTEXT PROCESSOR ───────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    data = {'now': datetime.utcnow()}
    if current_user.is_authenticated:
        data['notif_count'] = Notification.query.filter_by(
            user_id=current_user.id, is_read=False).count()
    else:
        data['notif_count'] = 0
    return data

# ─── ERROR HANDLERS ──────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):    return render_template('errors/404.html'), 404
@app.errorhandler(403)
def forbidden(e):    return render_template('errors/403.html'), 403
@app.errorhandler(500)
def server_error(e): return render_template('errors/500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)


# ─── DATABASE VIEWER (admin only) ────────────────────────────────────────────

@app.route('/admin/database')
@login_required
def view_database():
    if not is_admin():
        flash('Only admin can view the database', 'error')
        return redirect(url_for('dashboard'))

    # Get all approved/completed projects
    projects = Project.query.filter(Project.status.in_(['approved', 'completed'])).order_by(Project.created_at.desc()).all()
    
    # Pre-parse team details JSON so template doesn't have to
    import json
    for p in projects:
        try:
            p.team_data_parsed = json.loads(p.team_details) if p.team_details else {}
        except:
            p.team_data_parsed = {}
        
        # Ensure we have a default evaluation object if it doesn't exist yet
        if not Evaluation.query.filter_by(project_id=p.id).first():
            p.dummy_eval = {'presentation_marks': '', 'frontend_marks': '', 'backend_marks': '', 'report_marks': '', 'overall_marks': '', 'total_marks': '', 'remarks': ''}
        else:
            p.dummy_eval = None

    return render_template('admin_database.html', projects=projects)

@app.route('/admin/database/update/<int:project_id>', methods=['POST'])
@login_required
def admin_update_evaluation(project_id):
    if not is_admin():
        flash('Only admin can update database marks', 'error')
        return redirect(url_for('dashboard'))

    project = Project.query.get_or_404(project_id)
    
    pres    = float(request.form.get('presentation_marks') or 0)
    front   = float(request.form.get('frontend_marks') or 0)
    back    = float(request.form.get('backend_marks') or 0)
    report  = float(request.form.get('report_marks') or 0)
    overall = float(request.form.get('overall_marks') or 0)
    remarks = request.form.get('remarks', '')
    
    # Total marks strictly out of 50
    total = round((pres + front + back + report + overall), 2)

    existing = Evaluation.query.filter_by(project_id=project_id).first()
    
    if existing:
        existing.presentation_marks = pres
        existing.frontend_marks     = front
        existing.backend_marks      = back
        existing.report_marks       = report
        existing.overall_marks      = overall
        existing.total_marks        = total
        existing.remarks            = remarks
        existing.evaluated_at       = datetime.utcnow()
    else:
        # If no faculty is assigned but admin forces evaluation, assign admin as faculty guide for this record
        faculty_id = project.faculty_id if project.faculty_id else current_user.id
        db.session.add(Evaluation(
            project_id=project_id, faculty_id=faculty_id,
            presentation_marks=pres, frontend_marks=front,
            backend_marks=back, report_marks=report, overall_marks=overall,
            total_marks=total, remarks=remarks))

    db.session.commit()
    flash('Evaluation updated successfully from Database!', 'success')
    return redirect(url_for('view_database'))

# ─── CSV DOWNLOAD ROUTES (admin only) ────────────────────────────────────────
import csv, io
from flask import Response

def make_csv_response(filename, headers, rows):
    """Helper to build a CSV download response."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )

@app.route('/admin/download/evaluations')
@login_required
def download_evaluations():
    if not is_admin():
        flash('Only admin can download data', 'error')
        return redirect(url_for('dashboard'))
    evals = Evaluation.query.order_by(Evaluation.evaluated_at.desc()).all()
    headers = [
        'Sr.No', 'Project Title', 'Project Type', 'Domain',
        'Student Name', 'Student Email', 'Student Department',
        'Faculty Guide', 'Faculty Email',
        'Presentation (1-10)', 'Frontend (1-10)',
        'Backend (1-10)', 'Overall (1-10)', 'Total Average (1-10)',
        'Grade', 'Remarks', 'Evaluated On'
    ]
    rows = []
    for i, e in enumerate(evals, 1):
        t = e.total_marks
        grade = 'Excellent (A+)' if t >= 9 else \
                'Excellent (A)'  if t >= 8 else \
                'Good (B+)'      if t >= 7 else \
                'Good (B)'       if t >= 6 else \
                'Average (C)'    if t >= 5 else \
                'Below Average (D)' if t >= 4 else 'Fail (F)'
        rows.append([
            i,
            e.project.title,
            e.project.project_type.capitalize(),
            e.project.domain or '—',
            e.project.student.name,
            e.project.student.email,
            e.project.student.department or '—',
            e.faculty.name,
            e.faculty.email,
            e.presentation_marks,
            e.frontend_marks,
            e.backend_marks,
            e.overall_marks,
            e.total_marks,
            grade,
            e.remarks or '—',
            e.evaluated_at.strftime('%d %b %Y %H:%M')
        ])
    return make_csv_response(
        f'evaluations_{datetime.utcnow().strftime("%Y%m%d")}.csv',
        headers, rows
    )

@app.route('/admin/download/projects')
@login_required
def download_projects():
    if not is_admin():
        flash('Only admin can download data', 'error')
        return redirect(url_for('dashboard'))
    projects = Project.query.order_by(Project.created_at.desc()).all()
    headers = [
        'Sr.No', 'Project Title', 'Type', 'Domain', 'Status',
        'Student Name', 'Student Email', 'Student Department',
        'Faculty Guide', 'Faculty Email',
        'GitHub Link', 'Deployment Link',
        'Submitted On', 'Last Updated'
    ]
    rows = []
    for i, p in enumerate(projects, 1):
        rows.append([
            i, p.title, p.project_type.capitalize(),
            p.domain or '—', p.status.capitalize(),
            p.student.name, p.student.email,
            p.student.department or '—',
            p.faculty.name  if p.faculty else '—',
            p.faculty.email if p.faculty else '—',
            p.github_link      or '—',
            p.deployment_link  or '—',
            p.created_at.strftime('%d %b %Y'),
            p.updated_at.strftime('%d %b %Y') if p.updated_at else '—'
        ])
    return make_csv_response(
        f'projects_{datetime.utcnow().strftime("%Y%m%d")}.csv',
        headers, rows
    )

@app.route('/admin/download/students')
@login_required
def download_students():
    if not is_admin():
        flash('Only admin can download data', 'error')
        return redirect(url_for('dashboard'))
    students = User.query.filter_by(role='student').order_by(User.name).all()
    headers = [
        'Sr.No', 'Name', 'Email', 'Department',
        'Total Projects', 'Approved', 'Completed', 'Rejected',
        'Avg Score (1-10)', 'Joined On'
    ]
    rows = []
    for i, s in enumerate(students, 1):
        projs   = Project.query.filter_by(student_id=s.id).all()
        scores  = [p.evaluations[0].total_marks for p in projs if p.evaluations]
        avg     = round(sum(scores)/len(scores), 2) if scores else '—'
        rows.append([
            i, s.name, s.email, s.department or '—',
            len(projs),
            sum(1 for p in projs if p.status == 'approved'),
            sum(1 for p in projs if p.status == 'completed'),
            sum(1 for p in projs if p.status == 'rejected'),
            avg,
            s.created_at.strftime('%d %b %Y')
        ])
    return make_csv_response(
        f'students_{datetime.utcnow().strftime("%Y%m%d")}.csv',
        headers, rows
    )

@app.route('/admin/download/submissions')
@login_required
def download_submissions():
    if not is_admin():
        flash('Only admin can download data', 'error')
        return redirect(url_for('dashboard'))
    subs = Submission.query.order_by(Submission.submitted_at.desc()).all()
    headers = [
        'Sr.No', 'Project Title', 'Student Name', 'Faculty Guide',
        'Submission Type', 'File', 'GitHub Link',
        'Deployment Link', 'Demo Video', 'Notes', 'Submitted On'
    ]
    rows = []
    for i, s in enumerate(subs, 1):
        rows.append([
            i, s.project.title,
            s.project.student.name,
            s.project.faculty.name if s.project.faculty else '—',
            s.submission_type.capitalize(),
            s.file_path or '—',
            s.github_link      or '—',
            s.deployment_link  or '—',
            s.demo_video       or '—',
            s.notes            or '—',
            s.submitted_at.strftime('%d %b %Y %H:%M')
        ])
    return make_csv_response(
        f'submissions_{datetime.utcnow().strftime("%Y%m%d")}.csv',
        headers, rows
    )

@app.route('/admin/download/full-report')
@login_required
def download_full_report():
    """One combined CSV with everything — for sharing with management."""
    if not is_admin():
        flash('Only admin can download data', 'error')
        return redirect(url_for('dashboard'))
    evals = Evaluation.query.order_by(Evaluation.evaluated_at.desc()).all()
    projects_no_eval = Project.query.filter(
        ~Project.id.in_([e.project_id for e in evals])
    ).order_by(Project.created_at.desc()).all()

    headers = [
        'Sr.No', 'Project Title', 'Type', 'Domain', 'Status',
        'Student Name', 'Student Email', 'Department',
        'Faculty Guide',
        'Presentation', 'Frontend', 'Backend', 'Overall',
        'Total (1-10)', 'Grade',
        'GitHub', 'Deployment',
        'Remarks', 'Evaluated On'
    ]
    rows = []
    sr = 1
    for e in evals:
        t = e.total_marks
        grade = 'A+' if t>=9 else 'A' if t>=8 else 'B+' if t>=7 \
                else 'B' if t>=6 else 'C' if t>=5 else 'D' if t>=4 else 'F'
        rows.append([
            sr, e.project.title,
            e.project.project_type.capitalize(),
            e.project.domain or '—',
            e.project.status.capitalize(),
            e.project.student.name,
            e.project.student.email,
            e.project.student.department or '—',
            e.faculty.name,
            e.presentation_marks, e.frontend_marks,
            e.backend_marks, e.overall_marks,
            e.total_marks, grade,
            e.project.github_link     or '—',
            e.project.deployment_link or '—',
            e.remarks or '—',
            e.evaluated_at.strftime('%d %b %Y')
        ])
        sr += 1
    for p in projects_no_eval:
        rows.append([
            sr, p.title,
            p.project_type.capitalize(),
            p.domain or '—',
            p.status.capitalize(),
            p.student.name, p.student.email,
            p.student.department or '—',
            p.faculty.name if p.faculty else '—',
            '—','—','—','—','—','Not Evaluated',
            p.github_link or '—',
            p.deployment_link or '—',
            '—', '—'
        ])
        sr += 1
    return make_csv_response(
        f'full_report_{datetime.utcnow().strftime("%Y%m%d")}.csv',
        headers, rows
    )
