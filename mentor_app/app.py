from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from collections import defaultdict
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mentor-mentee-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///mentor_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ────────────────────────────────a─────────
# MODELS
# ─────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'mentor' or 'mentee'
    bio = db.Column(db.Text, default='')
    expertise = db.Column(db.String(200), default='')
    avatar_initial = db.Column(db.String(2), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    issues_raised = db.relationship('Issue', foreign_keys='Issue.raised_by', backref='raiser', lazy=True)
    issues_assigned = db.relationship('Issue', foreign_keys='Issue.assigned_to', backref='assignee', lazy=True)
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)


class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved, closed
    category = db.Column(db.String(50), default='general')
    raised_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolution_notes = db.Column(db.Text, default='')
    comments = db.relationship('Comment', backref='issue', lazy=True, cascade='all, delete-orphan')


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', backref='comments')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='messages_received')


class SessionNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mentee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_date = db.Column(db.DateTime, default=datetime.utcnow)
    action_items = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    mentor = db.relationship('User', foreign_keys=[mentor_id], backref='notes_written')
    mentee = db.relationship('User', foreign_keys=[mentee_id], backref='notes_received')


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(200), default='')
    is_read = db.Column(db.Boolean, default=False)
    notif_type = db.Column(db.String(30), default='info')  # info, success, warning, issue
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='notifications')


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_pinned = db.Column(db.Boolean, default=False)
    author = db.relationship('User', backref='announcements')


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def mentor_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'mentor':
            flash('Access denied. Mentors only.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def create_notification(user_id, message, link='', notif_type='info'):
    n = Notification(user_id=user_id, message=message, link=link, notif_type=notif_type)
    db.session.add(n)

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def time_ago(dt):
    now = datetime.utcnow()
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60: return 'just now'
    elif seconds < 3600: return f"{int(seconds//60)}m ago"
    elif seconds < 86400: return f"{int(seconds//3600)}h ago"
    elif seconds < 604800: return f"{int(seconds//86400)}d ago"
    else: return dt.strftime('%b %d')

app.jinja_env.globals['time_ago'] = time_ago

@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        notifs = Notification.query.filter_by(
            user_id=session['user_id'], is_read=False
        ).order_by(Notification.created_at.desc()).limit(8).all()
        return {'g_notifs': notifs, 'g_notif_count': len(notifs)}
    return {'g_notifs': [], 'g_notif_count': 0}

# ─────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        user = User.query.filter_by(email=email, role=role).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials or role mismatch.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        expertise = request.form.get('expertise', '')
        bio = request.form.get('bio', '')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('register.html')

        initials = ''.join([w[0].upper() for w in name.split()[:2]])
        user = User(
            name=name, email=email,
            password=generate_password_hash(password),
            role=role, expertise=expertise, bio=bio,
            avatar_initial=initials
        )
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    if user.role == 'mentor':
        all_issues = Issue.query.order_by(Issue.created_at.desc()).all()
        mentees = User.query.filter_by(role='mentee', is_active=True).all()
        open_count = Issue.query.filter_by(status='open').count()
        in_progress_count = Issue.query.filter_by(status='in_progress').count()
        resolved_count = Issue.query.filter_by(status='resolved').count()
        urgent_count = Issue.query.filter_by(priority='urgent', status='open').count()
        announcements = Announcement.query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).limit(5).all()
        unread_msgs = Message.query.filter_by(receiver_id=user.id, is_read=False).count()
        return render_template('mentor_dashboard.html',
            user=user, issues=all_issues, mentees=mentees,
            open_count=open_count, in_progress_count=in_progress_count,
            resolved_count=resolved_count, urgent_count=urgent_count,
            announcements=announcements, unread_msgs=unread_msgs)
    else:
        my_issues = Issue.query.filter_by(raised_by=user.id).order_by(Issue.created_at.desc()).all()
        announcements = Announcement.query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).limit(5).all()
        mentors = User.query.filter_by(role='mentor', is_active=True).all()
        unread_msgs = Message.query.filter_by(receiver_id=user.id, is_read=False).count()
        return render_template('mentee_dashboard.html',
            user=user, issues=my_issues, announcements=announcements,
            mentors=mentors, unread_msgs=unread_msgs)

# ─────────────────────────────────────────
# ISSUES
# ─────────────────────────────────────────

@app.route('/issues/new', methods=['GET', 'POST'])
@login_required
def new_issue():
    user = get_current_user()
    if request.method == 'POST':
        issue = Issue(
            title=request.form.get('title'),
            description=request.form.get('description'),
            priority=request.form.get('priority', 'medium'),
            category=request.form.get('category', 'general'),
            raised_by=user.id
        )
        assigned_id = request.form.get('assigned_to')
        if assigned_id:
            issue.assigned_to = int(assigned_id)
        db.session.add(issue)
        db.session.flush()
        # Notify all mentors about new issue
        mentors_all = User.query.filter_by(role='mentor', is_active=True).all()
        for m in mentors_all:
            create_notification(m.id,
                f'New issue raised by {user.name}: "{issue.title[:50]}"',
                url_for('view_issue', issue_id=issue.id), 'issue')
        db.session.commit()
        flash('Issue raised successfully!', 'success')
        return redirect(url_for('dashboard'))
    mentors = User.query.filter_by(role='mentor', is_active=True).all()
    return render_template('new_issue.html', user=user, mentors=mentors)

@app.route('/issues/<int:issue_id>')
@login_required
def view_issue(issue_id):
    user = get_current_user()
    issue = Issue.query.get_or_404(issue_id)
    comments = Comment.query.filter_by(issue_id=issue_id).order_by(Comment.created_at).all()
    mentors = User.query.filter_by(role='mentor').all()
    return render_template('view_issue.html', user=user, issue=issue, comments=comments, mentors=mentors)

@app.route('/issues/<int:issue_id>/comment', methods=['POST'])
@login_required
def add_comment(issue_id):
    user = get_current_user()
    content = request.form.get('content', '').strip()
    if content:
        comment = Comment(content=content, issue_id=issue_id, author_id=user.id)
        db.session.add(comment)
        db.session.commit()
        flash('Comment added.', 'success')
    return redirect(url_for('view_issue', issue_id=issue_id))

@app.route('/issues/<int:issue_id>/update', methods=['POST'])
@login_required
def update_issue(issue_id):
    user = get_current_user()
    issue = Issue.query.get_or_404(issue_id)
    if user.role == 'mentor':
        old_status = issue.status
        issue.status = request.form.get('status', issue.status)
        issue.assigned_to = request.form.get('assigned_to') or issue.assigned_to
        issue.resolution_notes = request.form.get('resolution_notes', issue.resolution_notes)
        issue.updated_at = datetime.utcnow()
        db.session.commit()
        if old_status != issue.status:
            create_notification(issue.raised_by,
                f'Your issue "{issue.title[:50]}" status changed to {issue.status.replace("_"," ")}',
                url_for('view_issue', issue_id=issue.id), 'success')
            db.session.commit()
        flash('Issue updated.', 'success')
    return redirect(url_for('view_issue', issue_id=issue_id))

@app.route('/issues/<int:issue_id>/delete', methods=['POST'])
@mentor_required
def delete_issue(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    db.session.delete(issue)
    db.session.commit()
    flash('Issue deleted.', 'success')
    return redirect(url_for('dashboard'))

# ─────────────────────────────────────────
# MESSAGES
# ─────────────────────────────────────────

@app.route('/messages')
@login_required
def messages():
    user = get_current_user()
    if user.role == 'mentor':
        contacts = User.query.filter_by(role='mentee', is_active=True).all()
    else:
        contacts = User.query.filter_by(role='mentor', is_active=True).all()
    Message.query.filter_by(receiver_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('messages.html', user=user, contacts=contacts)

@app.route('/messages/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def conversation(contact_id):
    user = get_current_user()
    contact = User.query.get_or_404(contact_id)
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            msg = Message(content=content, sender_id=user.id, receiver_id=contact_id)
            db.session.add(msg)
            db.session.commit()
        return redirect(url_for('conversation', contact_id=contact_id))
    msgs = Message.query.filter(
        ((Message.sender_id == user.id) & (Message.receiver_id == contact_id)) |
        ((Message.sender_id == contact_id) & (Message.receiver_id == user.id))
    ).order_by(Message.created_at).all()
    Message.query.filter_by(sender_id=contact_id, receiver_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    if user.role == 'mentor':
        contacts = User.query.filter_by(role='mentee', is_active=True).all()
    else:
        contacts = User.query.filter_by(role='mentor', is_active=True).all()
    return render_template('messages.html', user=user, contacts=contacts, contact=contact, msgs=msgs)

# ─────────────────────────────────────────
# ANNOUNCEMENTS (Mentor only)
# ─────────────────────────────────────────

@app.route('/announcements/new', methods=['GET', 'POST'])
@mentor_required
def new_announcement():
    user = get_current_user()
    if request.method == 'POST':
        ann = Announcement(
            title=request.form.get('title'),
            content=request.form.get('content'),
            author_id=user.id,
            is_pinned=bool(request.form.get('is_pinned'))
        )
        db.session.add(ann)
        db.session.commit()
        flash('Announcement posted!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('new_announcement.html', user=user)

@app.route('/announcements/<int:ann_id>/delete', methods=['POST'])
@mentor_required
def delete_announcement(ann_id):
    ann = Announcement.query.get_or_404(ann_id)
    db.session.delete(ann)
    db.session.commit()
    flash('Announcement deleted.', 'success')
    return redirect(url_for('dashboard'))

# ─────────────────────────────────────────
# USERS / PROFILES
# ─────────────────────────────────────────

@app.route('/profile')
@login_required
def profile():
    user = get_current_user()
    return render_template('profile.html', user=user)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    user = get_current_user()
    user.name = request.form.get('name', user.name)
    user.bio = request.form.get('bio', user.bio)
    user.expertise = request.form.get('expertise', user.expertise)
    user.avatar_initial = ''.join([w[0].upper() for w in user.name.split()[:2]])
    db.session.commit()
    flash('Profile updated.', 'success')
    return redirect(url_for('profile'))

@app.route('/users')
@mentor_required
def manage_users():
    user = get_current_user()
    mentees = User.query.filter_by(role='mentee').all()
    mentors = User.query.filter_by(role='mentor').all()
    return render_template('manage_users.html', user=user, mentees=mentees, mentors=mentors)

@app.route('/users/<int:uid>/toggle', methods=['POST'])
@mentor_required
def toggle_user(uid):
    u = User.query.get_or_404(uid)
    u.is_active = not u.is_active
    db.session.commit()
    flash(f"{'Activated' if u.is_active else 'Deactivated'} {u.name}.", 'success')
    return redirect(url_for('manage_users'))

# ─────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────

@app.route('/notifications/read/<int:nid>', methods=['POST'])
@login_required
def read_notification(nid):
    n = Notification.query.get_or_404(nid)
    if n.user_id == session['user_id']:
        n.is_read = True
        db.session.commit()
    return redirect(n.link or url_for('dashboard'))

@app.route('/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    Notification.query.filter_by(user_id=session['user_id'], is_read=False).update({'is_read': True})
    db.session.commit()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/notifications')
@login_required
def all_notifications():
    user = get_current_user()
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(50).all()
    Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('notifications.html', user=user, notifs=notifs)


# ─────────────────────────────────────────
# SESSION NOTES
# ─────────────────────────────────────────

@app.route('/session-notes')
@login_required
def session_notes():
    user = get_current_user()
    if user.role == 'mentor':
        notes = SessionNote.query.filter_by(mentor_id=user.id).order_by(SessionNote.session_date.desc()).all()
        mentees = User.query.filter_by(role='mentee', is_active=True).all()
        return render_template('session_notes.html', user=user, notes=notes, mentees=mentees, now=datetime.utcnow())
    else:
        notes = SessionNote.query.filter_by(mentee_id=user.id).order_by(SessionNote.session_date.desc()).all()
        return render_template('session_notes.html', user=user, notes=notes, mentees=[])

@app.route('/session-notes/new', methods=['POST'])
@mentor_required
def new_session_note():
    user = get_current_user()
    mentee_id = request.form.get('mentee_id')
    date_str = request.form.get('session_date')
    session_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
    note = SessionNote(
        title=request.form.get('title'),
        content=request.form.get('content'),
        action_items=request.form.get('action_items', ''),
        mentor_id=user.id,
        mentee_id=int(mentee_id),
        session_date=session_date
    )
    db.session.add(note)
    db.session.flush()
    create_notification(int(mentee_id),
        f'Your mentor added session notes: "{note.title}"',
        url_for('session_notes'), 'info')
    db.session.commit()
    flash('Session note saved!', 'success')
    return redirect(url_for('session_notes'))

@app.route('/session-notes/<int:note_id>/delete', methods=['POST'])
@mentor_required
def delete_session_note(note_id):
    note = SessionNote.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted.', 'success')
    return redirect(url_for('session_notes'))


# ─────────────────────────────────────────
# ANALYTICS (Mentor only)
# ─────────────────────────────────────────

@app.route('/analytics')
@mentor_required
def analytics():
    user = get_current_user()
    # Issues over last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    issues_recent = Issue.query.filter(Issue.created_at >= thirty_days_ago).all()

    # Group by day
    by_day = defaultdict(int)
    for issue in issues_recent:
        day = issue.created_at.strftime('%b %d')
        by_day[day] += 1

    # Last 14 days labels
    days_labels = []
    days_data = []
    for i in range(13, -1, -1):
        d = datetime.utcnow() - timedelta(days=i)
        label = d.strftime('%b %d')
        days_labels.append(label)
        days_data.append(by_day.get(label, 0))

    # By status
    status_data = {
        'open': Issue.query.filter_by(status='open').count(),
        'in_progress': Issue.query.filter_by(status='in_progress').count(),
        'resolved': Issue.query.filter_by(status='resolved').count(),
        'closed': Issue.query.filter_by(status='closed').count(),
    }

    # By priority
    priority_data = {
        'low': Issue.query.filter_by(priority='low').count(),
        'medium': Issue.query.filter_by(priority='medium').count(),
        'high': Issue.query.filter_by(priority='high').count(),
        'urgent': Issue.query.filter_by(priority='urgent').count(),
    }

    # By category
    categories = db.session.query(Issue.category, db.func.count(Issue.id)).group_by(Issue.category).all()

    # Top mentees by issues
    mentees = User.query.filter_by(role='mentee').all()
    mentee_stats = []
    for m in mentees:
        total = len(m.issues_raised)
        resolved = sum(1 for i in m.issues_raised if i.status == 'resolved')
        mentee_stats.append({
            'name': m.name,
            'total': total,
            'resolved': resolved,
            'open': sum(1 for i in m.issues_raised if i.status == 'open'),
        })
    mentee_stats.sort(key=lambda x: x['total'], reverse=True)

    total_issues = Issue.query.count()
    avg_resolve_days = 0
    resolved_issues = Issue.query.filter_by(status='resolved').all()
    if resolved_issues:
        total_days = sum((i.updated_at - i.created_at).days for i in resolved_issues)
        avg_resolve_days = round(total_days / len(resolved_issues), 1)

    return render_template('analytics.html',
        user=user,
        days_labels=days_labels, days_data=days_data,
        status_data=status_data, priority_data=priority_data,
        categories=categories, mentee_stats=mentee_stats,
        total_issues=total_issues, avg_resolve_days=avg_resolve_days,
        total_mentees=len(mentees)
    )


# ─────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────

@app.route('/search')
@login_required
def search():
    user = get_current_user()
    q = request.args.get('q', '').strip()
    issue_results = []
    user_results = []
    if q:
        like = f'%{q}%'
        if user.role == 'mentor':
            issue_results = Issue.query.filter(
                (Issue.title.ilike(like)) | (Issue.description.ilike(like))
            ).order_by(Issue.created_at.desc()).limit(20).all()
            user_results = User.query.filter(
                (User.name.ilike(like)) | (User.email.ilike(like)) | (User.expertise.ilike(like))
            ).limit(10).all()
        else:
            issue_results = Issue.query.filter(
                Issue.raised_by == user.id,
            ).filter(
                (Issue.title.ilike(like)) | (Issue.description.ilike(like))
            ).order_by(Issue.created_at.desc()).limit(20).all()
    return render_template('search.html', user=user, q=q,
                           issue_results=issue_results, user_results=user_results)


# ─────────────────────────────────────────
# PASSWORD CHANGE
# ─────────────────────────────────────────

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = get_current_user()
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not check_password_hash(user.password, current):
            flash('Current password is incorrect.', 'error')
        elif len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
        elif new_pw != confirm:
            flash('Passwords do not match.', 'error')
        else:
            user.password = generate_password_hash(new_pw)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('profile'))
    return render_template('change_password.html', user=user)


# ─────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, message='Page not found'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403, message='Access denied'), 403

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500, message='Something went wrong on our end'), 500


# ─────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────

@app.route('/api/issues/stats')
@login_required
def issue_stats():
    stats = {
        'open': Issue.query.filter_by(status='open').count(),
        'in_progress': Issue.query.filter_by(status='in_progress').count(),
        'resolved': Issue.query.filter_by(status='resolved').count(),
        'urgent': Issue.query.filter_by(priority='urgent', status='open').count(),
    }
    return jsonify(stats)

# ─────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────

def seed_data():
    if User.query.count() == 0:
        mentor = User(
            name='Dr. Sarah Mitchell', email='mentor@demo.com',
            password=generate_password_hash('mentor123'),
            role='mentor', bio='Senior software engineer with 10+ years experience.',
            expertise='Python, Machine Learning, System Design', avatar_initial='SM'
        )
        mentee = User(
            name='Alex Johnson', email='mentee@demo.com',
            password=generate_password_hash('mentee123'),
            role='mentee', bio='Aspiring developer, eager to learn.',
            expertise='Python basics, Web Development', avatar_initial='AJ'
        )
        db.session.add_all([mentor, mentee])
        db.session.commit()

        ann = Announcement(
            title='Welcome to MentorBridge!',
            content='This is your collaborative mentorship platform. Raise issues, send messages, and grow together.',
            author_id=mentor.id, is_pinned=True
        )
        db.session.add(ann)
        db.session.commit()

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)