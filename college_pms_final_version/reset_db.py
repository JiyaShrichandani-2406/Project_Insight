from app import app, db, User, Project, Submission, Evaluation, Comment, Notification, Milestone

with app.app_context():
    print("Starting database reset...")
    # Delete all project-related data
    Project.query.delete()
    Submission.query.delete()
    Evaluation.query.delete()
    Comment.query.delete()
    Notification.query.delete()
    Milestone.query.delete()
    
    # Delete all student and faculty users
    User.query.filter(User.role != 'admin').delete()
    
    # Commit changes
    db.session.commit()
    print("Database has been reset successfully. All non-admin accounts and projects have been deleted.")
