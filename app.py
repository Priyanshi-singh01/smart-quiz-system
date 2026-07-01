from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
import psycopg2, psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os, random, string, csv, io, json
from flask_mail import Mail, Message
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from functools import wraps

app = Flask(__name__)

# ─── SECURITY ──────────────────────────────────────────────────────────────────
app.secret_key = os.environ.get('SECRET_KEY', 'smartquiz_secret_key_bca_2024_secure')

# ─── SESSION: NEVER EXPIRE — stay active until explicit logout ─────────────────
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)  # 1 year — effectively never expires

# ─── UPLOADS ──────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── MAIL ─────────────────────────────────────────────────────────────────────
app.config['MAIL_SERVER']         = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT']           = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS']        = True
app.config['MAIL_USERNAME']       = os.environ.get('MAIL_USERNAME', 'onlinequiz.noreply@gmail.com')
app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', 'nuug fknd rcxj vrbz')
app.config['MAIL_DEFAULT_SENDER'] = ('SmartQuiz System', os.environ.get('MAIL_USERNAME', 'onlinequiz.noreply@gmail.com'))
mail = Mail(app)

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_CONFIG = {
    'dbname':   os.environ.get('DB_NAME',     'quiz_db'),
    'user':     os.environ.get('DB_USER',     'postgres'),
    'password': os.environ.get('DB_PASSWORD', '1234'),
    'host':     os.environ.get('DB_HOST',     'localhost'),
    'port':     os.environ.get('DB_PORT',     '5432'),
}

def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn

# ─── MAKE EVERY REQUEST KEEP SESSION ALIVE ────────────────────────────────────
@app.before_request
def keep_session_alive():
    """Refresh permanent session on every request so it never expires during use."""
    session.permanent = True
    session.modified  = True   # touch the session so cookie gets refreshed

# ─── TEMPLATE FILTERS ─────────────────────────────────────────────────────────
@app.template_filter('strftime')
def strftime_filter(value, fmt='%d %b %Y'):
    if value is None: return ''
    if isinstance(value, str):
        try: value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except: return value
    return value.strftime(fmt)

# ─── DB INIT ──────────────────────────────────────────────────────────────────
def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            roll_number VARCHAR(50) DEFAULT '',
            role VARCHAR(20) DEFAULT 'student',
            joined TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS quiz_schedules (
            id SERIAL PRIMARY KEY,
            subject_name VARCHAR(150) NOT NULL,
            paper_code VARCHAR(50) NOT NULL,
            exam_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            allow_reattempt BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            option1 VARCHAR(255) NOT NULL,
            option2 VARCHAR(255) NOT NULL,
            option3 VARCHAR(255) NOT NULL,
            option4 VARCHAR(255) NOT NULL,
            answer VARCHAR(255) NOT NULL,
            category VARCHAR(100) DEFAULT 'General',
            marks INTEGER DEFAULT 1,
            image_filename VARCHAR(255) DEFAULT NULL,
            schedule_id INTEGER DEFAULT NULL REFERENCES quiz_schedules(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            schedule_id INTEGER REFERENCES quiz_schedules(id) ON DELETE SET NULL,
            subject_name VARCHAR(150) DEFAULT '',
            paper_code VARCHAR(50) DEFAULT '',
            exam_date DATE DEFAULT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            total_marks INTEGER NOT NULL DEFAULT 0,
            obtained_marks INTEGER NOT NULL DEFAULT 0,
            question_order TEXT DEFAULT '[]',
            saved_answers TEXT DEFAULT '{}',
            submitted BOOLEAN DEFAULT FALSE,
            quiz_date TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS quiz_settings (
            id SERIAL PRIMARY KEY,
            timer_seconds INTEGER NOT NULL DEFAULT 3600,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS otp_store (
            id SERIAL PRIMARY KEY,
            email VARCHAR(150) NOT NULL,
            otp VARCHAR(10) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            used BOOLEAN DEFAULT FALSE
        );
    """)
    upgrades = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS roll_number VARCHAR(50) DEFAULT ''",
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS marks INTEGER DEFAULT 1",
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS image_filename VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS schedule_id INTEGER DEFAULT NULL",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS total_marks INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS obtained_marks INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS schedule_id INTEGER REFERENCES quiz_schedules(id) ON DELETE SET NULL",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS subject_name VARCHAR(150) DEFAULT ''",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS paper_code VARCHAR(50) DEFAULT ''",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS exam_date DATE DEFAULT NULL",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS question_order TEXT DEFAULT '[]'",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS saved_answers TEXT DEFAULT '{}'",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS submitted BOOLEAN DEFAULT FALSE",
    ]
    for sql in upgrades:
        try: cur.execute(sql)
        except: conn.rollback()

    cur.execute("SELECT id FROM users WHERE email='admin@quiz.com'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users (name,email,password,role,roll_number) VALUES (%s,%s,%s,%s,%s)",
            ('Admin','admin@quiz.com', generate_password_hash('admin123'), 'admin', 'ADMIN'))

    cur.execute("SELECT COUNT(*) FROM quiz_settings")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO quiz_settings (timer_seconds) VALUES (3600)")

    conn.commit(); cur.close(); conn.close()

def get_timer():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT timer_seconds FROM quiz_settings ORDER BY id DESC LIMIT 1")
        row = cur.fetchone(); cur.close(); conn.close()
        return row[0] if row else 3600
    except: return 3600

def generate_otp(): return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp, name="User"):
    try:
        msg = Message(subject="SmartQuiz — OTP for Password Reset", recipients=[email])
        msg.html = f"""<div style="font-family:Arial;max-width:500px;margin:0 auto;background:#0d1b2a;color:#e8f0f8;padding:2rem;border-radius:12px;">
            <h2 style="color:#c9a84c;text-align:center;">🎓 SmartQuiz</h2>
            <p>Hello <strong>{name}</strong>, your OTP:</p>
            <div style="background:#1a2d42;border:2px solid #c9a84c;border-radius:8px;padding:1.5rem;text-align:center;margin:1.5rem 0;">
                <span style="font-size:2.5rem;font-weight:bold;color:#c9a84c;letter-spacing:0.5rem;">{otp}</span>
            </div>
            <p style="color:#8ba3bc;">Valid for <strong>10 minutes</strong>.</p>
        </div>"""
        mail.send(msg); return True
    except Exception as e:
        print(f"Email error: {e}"); return False

# ─── SCHEDULE HELPERS ─────────────────────────────────────────────────────────
def get_schedule_by_id(schedule_id):
    """Fetch a specific schedule by ID."""
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM quiz_schedules WHERE id=%s", (schedule_id,))
        s = cur.fetchone(); cur.close(); conn.close(); return s
    except: return None

def get_active_schedule():
    """Return the schedule that is currently live (today + within time window)."""
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        now = datetime.now()
        cur.execute("""SELECT * FROM quiz_schedules
            WHERE exam_date = CURRENT_DATE
            AND start_time <= %s::time AND end_time >= %s::time
            ORDER BY start_time LIMIT 1""",
            (now.strftime('%H:%M:%S'), now.strftime('%H:%M:%S')))
        s = cur.fetchone(); cur.close(); conn.close(); return s
    except: return None

def get_upcoming_schedules():
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        now = datetime.now()
        cur.execute("""SELECT * FROM quiz_schedules
            WHERE (exam_date > CURRENT_DATE)
               OR (exam_date = CURRENT_DATE AND end_time > %s::time)
            ORDER BY exam_date, start_time LIMIT 10""", (now.strftime('%H:%M:%S'),))
        s = cur.fetchall(); cur.close(); conn.close(); return s
    except: return []

def get_student_attempt(user_id, schedule_id):
    try:
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM results WHERE user_id=%s AND schedule_id=%s ORDER BY quiz_date DESC LIMIT 1",
                    (user_id, schedule_id))
        a = cur.fetchone(); cur.close(); conn.close(); return a
    except: return None

# ─── SUBJECT SESSION HELPERS ──────────────────────────────────────────────────
def get_selected_schedule_id():
    """
    Returns the currently selected schedule_id from session.
    Admin sets this via the subject dropdown. All admin views respect it.
    """
    return session.get('selected_schedule_id')

def set_selected_schedule(schedule_id):
    """Store selected schedule in session."""
    session['selected_schedule_id'] = schedule_id
    session.modified = True

# ─── AUTH DECORATORS ──────────────────────────────────────────────────────────
def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'student':
            flash('Please login to continue.', 'error')
            return redirect(url_for('student_login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash('Admin login required.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def index(): return redirect(url_for('login_choice'))

@app.route('/login')
def login_choice(): return render_template('login_choice.html')

@app.route('/student/login', methods=['GET','POST'])
def student_login():
    if 'user_id' in session and session.get('user_role') == 'student':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('student_login.html')
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE email=%s AND role='student'", (email,))
        user = cur.fetchone(); cur.close(); conn.close()
        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session.update({'user_id': user['id'], 'user_name': user['name'], 'user_role': 'student'})
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('student_login.html')

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if 'user_id' in session and session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE email=%s AND role='admin'", (email,))
        user = cur.fetchone(); cur.close(); conn.close()
        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session.update({'user_id': user['id'], 'user_name': user['name'], 'user_role': 'admin'})
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name     = request.form.get('name','').strip()
        roll     = request.form.get('roll_number','').strip()
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        confirm  = request.form.get('confirm_password','')
        if not all([name, roll, email, password, confirm]):
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            flash('Email already registered.', 'error')
            cur.close(); conn.close()
            return render_template('register.html')
        cur.execute("INSERT INTO users (name,email,password,roll_number) VALUES (%s,%s,%s,%s)",
                    (name, email, generate_password_hash(password), roll))
        conn.commit(); cur.close(); conn.close()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('student_login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_choice'))

# ─── FORGOT PASSWORD ──────────────────────────────────────────────────────────
@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, name FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        if user:
            otp = generate_otp()
            cur2 = conn.cursor()
            cur2.execute("UPDATE otp_store SET used=TRUE WHERE email=%s", (email,))
            cur2.execute("INSERT INTO otp_store (email,otp) VALUES (%s,%s)", (email, otp))
            conn.commit(); cur2.close()
            if send_otp_email(email, otp, user['name']):
                session['otp_email'] = email
                flash('OTP sent!', 'success')
                return redirect(url_for('verify_otp'))
            flash('Failed to send OTP.', 'error')
        else:
            flash('No account found.', 'error')
        cur.close(); conn.close()
    return render_template('forgot_password.html')

@app.route('/verify-otp', methods=['GET','POST'])
def verify_otp():
    if 'otp_email' not in session: return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        entered = request.form.get('otp','').strip()
        email   = session['otp_email']
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT * FROM otp_store WHERE email=%s AND otp=%s AND used=FALSE
            AND created_at > NOW() - INTERVAL '10 minutes' ORDER BY created_at DESC LIMIT 1""",
            (email, entered))
        row = cur.fetchone()
        if row:
            cur2 = conn.cursor()
            cur2.execute("UPDATE otp_store SET used=TRUE WHERE id=%s", (row['id'],))
            conn.commit(); cur2.close()
            session['otp_verified'] = True
            cur.close(); conn.close()
            return redirect(url_for('reset_password_new'))
        flash('Invalid or expired OTP.', 'error')
        cur.close(); conn.close()
    return render_template('verify_otp.html')

@app.route('/reset-password-new', methods=['GET','POST'])
def reset_password_new():
    if 'otp_email' not in session or not session.get('otp_verified'):
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        new_pass = request.form.get('new_password','')
        confirm  = request.form.get('confirm_password','')
        if new_pass != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password_new.html')
        if len(new_pass) < 6:
            flash('Minimum 6 characters.', 'error')
            return render_template('reset_password_new.html')
        conn = get_db(); cur = conn.cursor()
        cur.execute("UPDATE users SET password=%s WHERE email=%s",
                    (generate_password_hash(new_pass), session['otp_email']))
        conn.commit(); cur.close(); conn.close()
        session.pop('otp_email', None); session.pop('otp_verified', None)
        flash('Password reset! Please login.', 'success')
        return redirect(url_for('student_login'))
    return render_template('reset_password_new.html')

@app.route('/resend-otp')
def resend_otp():
    if 'otp_email' not in session: return redirect(url_for('forgot_password'))
    email = session['otp_email']
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    if user:
        otp = generate_otp()
        cur2 = conn.cursor()
        cur2.execute("UPDATE otp_store SET used=TRUE WHERE email=%s", (email,))
        cur2.execute("INSERT INTO otp_store (email,otp) VALUES (%s,%s)", (email, otp))
        conn.commit(); cur2.close()
        send_otp_email(email, otp, user['name'])
        flash('New OTP sent!', 'success')
    cur.close(); conn.close()
    return redirect(url_for('verify_otp'))

# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/dashboard')
@student_required
def dashboard():
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT r.* FROM results r
        WHERE r.user_id=%s AND r.submitted=TRUE
        ORDER BY r.quiz_date DESC LIMIT 5""", (session['user_id'],))
    recent = cur.fetchall()
    cur.execute("SELECT COUNT(*) AS cnt FROM results WHERE user_id=%s AND submitted=TRUE", (session['user_id'],))
    total_attempts = cur.fetchone()['cnt']
    cur.execute("SELECT AVG(obtained_marks*100.0/NULLIF(total_marks,0)) AS avg FROM results WHERE user_id=%s AND submitted=TRUE",
                (session['user_id'],))
    row = cur.fetchone(); avg_score = round(row['avg'], 1) if row['avg'] else 0
    cur.execute("SELECT MAX(obtained_marks*100.0/NULLIF(total_marks,0)) AS best FROM results WHERE user_id=%s AND submitted=TRUE",
                (session['user_id'],))
    best_row = cur.fetchone(); best_score = round(best_row['best'], 1) if best_row and best_row['best'] else 0
    schedules = get_upcoming_schedules()
    active    = get_active_schedule()
    cur.close(); conn.close()
    return render_template('dashboard.html', recent=recent, total_attempts=total_attempts,
                           avg_score=avg_score, best_score=best_score,
                           schedules=schedules, active=active)

@app.route('/profile', methods=['GET','POST'])
@student_required
def profile():
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cur.fetchone()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            name = request.form.get('name','').strip()
            roll = request.form.get('roll_number','').strip()
            if name:
                cur2 = conn.cursor()
                cur2.execute("UPDATE users SET name=%s, roll_number=%s WHERE id=%s", (name, roll, session['user_id']))
                conn.commit(); cur2.close()
                session['user_name'] = name
                flash('Profile updated!', 'success')
                cur.close(); conn.close()
                return redirect(url_for('profile'))
            else:
                flash('Name is required.', 'error')
        elif action == 'change_password':
            current  = request.form.get('current_password','')
            new_pass = request.form.get('new_password','')
            confirm  = request.form.get('confirm_password','')
            if not check_password_hash(user['password'], current):
                flash('Current password is incorrect.', 'error')
            elif new_pass != confirm:
                flash('New passwords do not match.', 'error')
            elif len(new_pass) < 6:
                flash('Minimum 6 characters.', 'error')
            else:
                cur2 = conn.cursor()
                cur2.execute("UPDATE users SET password=%s WHERE id=%s", (generate_password_hash(new_pass), session['user_id']))
                conn.commit(); cur2.close()
                flash('Password changed!', 'success')
                cur.close(); conn.close()
                return redirect(url_for('profile'))
    cur.execute("SELECT COUNT(*) AS cnt FROM results WHERE user_id=%s AND submitted=TRUE", (session['user_id'],))
    attempts = cur.fetchone()['cnt']
    cur.close(); conn.close()
    return render_template('profile.html', user=user, attempts=attempts)

@app.route('/quiz')
@student_required
def quiz():
    schedule = get_active_schedule()
    if not schedule:
        flash('No active quiz right now. Please wait for a scheduled exam.', 'error')
        return redirect(url_for('dashboard'))
    attempt = get_student_attempt(session['user_id'], schedule['id'])
    if attempt and attempt['submitted'] and not schedule['allow_reattempt']:
        flash('You have already submitted this quiz.', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM questions WHERE schedule_id=%s ORDER BY id ASC", (schedule['id'],))
    all_questions = cur.fetchall()
    if not all_questions:
        flash('No questions assigned to this subject yet. Contact admin.', 'error')
        cur.close(); conn.close()
        return redirect(url_for('dashboard'))

    saved_answers  = {}
    question_order = [q['id'] for q in all_questions]

    if attempt and not attempt['submitted']:
        try:
            question_order = json.loads(attempt['question_order'])
            saved_answers  = json.loads(attempt['saved_answers'])
        except: pass
        result_id = attempt['id']
    else:
        random.shuffle(question_order)
        total_marks = sum(q['marks'] for q in all_questions)
        cur.execute("""INSERT INTO results
            (user_id,schedule_id,subject_name,paper_code,exam_date,
             score,total,total_marks,obtained_marks,question_order,saved_answers,submitted)
            VALUES (%s,%s,%s,%s,%s,0,%s,%s,0,%s,%s,FALSE) RETURNING id""",
            (session['user_id'], schedule['id'], schedule['subject_name'],
             schedule['paper_code'], schedule['exam_date'],
             len(all_questions), total_marks,
             json.dumps(question_order), json.dumps({})))
        result_id = cur.fetchone()['id']
        conn.commit()

    q_map     = {q['id']: q for q in all_questions}
    questions = [q_map[qid] for qid in question_order if qid in q_map]
    now       = datetime.now()
    end_dt    = datetime.combine(date.today(), schedule['end_time'])
    remaining = max(0, int((end_dt - now).total_seconds()))
    cur.close(); conn.close()
    return render_template('quiz.html', questions=questions, timer=remaining,
                           schedule=schedule, result_id=result_id, saved_answers=saved_answers)

@app.route('/save_answers', methods=['POST'])
@student_required
def save_answers():
    data      = request.get_json()
    result_id = data.get('result_id')
    answers   = data.get('answers', {})
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE results SET saved_answers=%s WHERE id=%s AND user_id=%s AND submitted=FALSE",
                (json.dumps(answers), result_id, session['user_id']))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'status': 'saved'})

@app.route('/submit_quiz', methods=['POST'])
@student_required
def submit_quiz():
    data      = request.get_json()
    answers   = data.get('answers', {})
    result_id = data.get('result_id')
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM results WHERE id=%s AND user_id=%s", (result_id, session['user_id']))
    result_row = cur.fetchone()
    if not result_row:
        cur.close(); conn.close()
        return jsonify({'error': 'Invalid result'}), 400
    cur.execute("SELECT * FROM questions WHERE schedule_id=%s", (result_row['schedule_id'],))
    questions   = cur.fetchall()
    score = obtained = 0
    total_marks = sum(q['marks'] for q in questions)
    for q in questions:
        if answers.get(str(q['id']),'') == q['answer']:
            score += 1; obtained += q['marks']
    cur2 = conn.cursor()
    cur2.execute("""UPDATE results SET score=%s,total=%s,total_marks=%s,obtained_marks=%s,
        saved_answers=%s,submitted=TRUE,quiz_date=NOW() WHERE id=%s""",
        (score, len(questions), total_marks, obtained, json.dumps(answers), result_id))
    conn.commit(); cur2.close(); cur.close(); conn.close()
    return jsonify({'result_id': result_id, 'score': score, 'total': len(questions),
                    'obtained': obtained, 'total_marks': total_marks})

@app.route('/result/<int:result_id>')
@student_required
def result(result_id):
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT r.*, u.name FROM results r JOIN users u ON r.user_id=u.id WHERE r.id=%s", (result_id,))
    res = cur.fetchone()
    if not res or (session.get('user_role') != 'admin' and res['user_id'] != session['user_id']):
        cur.close(); conn.close()
        flash('Result not found.', 'error')
        return redirect(url_for('dashboard'))
    rank_row = None
    if res and res['schedule_id']:
        cur.execute("""SELECT RANK() OVER (ORDER BY obtained_marks DESC) AS rank,
            COUNT(*) OVER () AS total_students FROM results
            WHERE schedule_id=%s AND submitted=TRUE LIMIT 1""", (res['schedule_id'],))
        rank_row = cur.fetchone()
    questions_detail = []
    if res and res['schedule_id']:
        try:
            saved = json.loads(res['saved_answers'] or '{}')
            order = json.loads(res['question_order'] or '[]')
            cur.execute("SELECT * FROM questions WHERE schedule_id=%s", (res['schedule_id'],))
            all_q = {q['id']: q for q in cur.fetchall()}
            for qid in order:
                if qid in all_q:
                    q = all_q[qid]
                    user_ans = saved.get(str(qid), None)
                    questions_detail.append({
                        'question': q['question'],
                        'options': [q['option1'],q['option2'],q['option3'],q['option4']],
                        'correct': q['answer'], 'user_answer': user_ans,
                        'is_correct': user_ans == q['answer'],
                        'marks': q['marks'], 'image_filename': q['image_filename'],
                    })
        except: pass
    cur.close(); conn.close()
    percentage = round(res['obtained_marks'] * 100.0 / res['total_marks'], 1) if res['total_marks'] else 0
    return render_template('result.html', res=res, percentage=percentage,
                           rank_row=rank_row, questions_detail=questions_detail)

@app.route('/leaderboard')
@student_required
def leaderboard():
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM quiz_schedules ORDER BY exam_date DESC")
    all_schedules = cur.fetchall()
    schedule_id = request.args.get('schedule_id', 'all')
    # Students always see their own results only
    cur.execute("""SELECT u.name, u.roll_number,
        MAX(r.obtained_marks) AS obtained_marks, MAX(r.total_marks) AS total_marks,
        ROUND(MAX(r.obtained_marks*100.0/NULLIF(r.total_marks,0)),1) AS percentage,
        COUNT(r.id) AS attempts, MAX(r.quiz_date) AS last_attempt,
        MAX(r.subject_name) AS subject_name, MAX(r.paper_code) AS paper_code
        FROM results r JOIN users u ON r.user_id=u.id
        WHERE r.user_id=%s AND r.submitted=TRUE
        GROUP BY u.id,u.name,u.roll_number""", (session['user_id'],))
    leaders = cur.fetchall()
    cur.close(); conn.close()
    return render_template('leaderboard.html', leaders=leaders, is_admin=False,
                           all_schedules=all_schedules, selected_schedule=schedule_id)

@app.route('/performance')
@student_required
def performance():
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT r.score,r.total,r.obtained_marks,r.total_marks,r.quiz_date,
        ROUND(r.obtained_marks*100.0/NULLIF(r.total_marks,0),1) AS percentage,
        r.subject_name,r.paper_code
        FROM results r WHERE r.user_id=%s AND r.submitted=TRUE ORDER BY r.quiz_date""",
        (session['user_id'],))
    history = cur.fetchall()
    cur.execute("""SELECT AVG(obtained_marks*100.0/NULLIF(total_marks,0)) AS avg,
        MAX(obtained_marks*100.0/NULLIF(total_marks,0)) AS best,
        MIN(obtained_marks*100.0/NULLIF(total_marks,0)) AS worst,
        COUNT(*) AS attempts FROM results WHERE user_id=%s AND submitted=TRUE""",
        (session['user_id'],))
    stats = cur.fetchone(); cur.close(); conn.close()
    history_fmt = [{'score':h['score'],'total':h['total'],
        'obtained_marks':h['obtained_marks'],'total_marks':h['total_marks'],
        'percentage':h['percentage'] or 0,
        'subject_name':h['subject_name'] or 'General',
        'paper_code':h['paper_code'] or '—',
        'date_str':h['quiz_date'].strftime('%d %b') if h['quiz_date'] else '',
        'datetime_str':h['quiz_date'].strftime('%d %b %Y, %I:%M %p') if h['quiz_date'] else '',
        'tooltip':f"{h['subject_name'] or 'General'} | {h['paper_code'] or ''} | {h['quiz_date'].strftime('%d %b %Y') if h['quiz_date'] else ''}",
    } for h in history]
    return render_template('performance.html', history=history_fmt, stats=stats)

# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — SUBJECT SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/select-subject', methods=['POST'])
@admin_required
def admin_select_subject():
    """
    Admin picks a subject/schedule from the dropdown.
    This stores it in session['selected_schedule_id'] and redirects back.
    Every admin view (dashboard, results, students, PDF) uses this value.
    """
    sid = request.form.get('selected_schedule_id', '')
    if sid and sid != 'all':
        try:
            set_selected_schedule(int(sid))
        except:
            set_selected_schedule(None)
    else:
        set_selected_schedule(None)   # None means "all subjects"
    next_url = request.form.get('next', url_for('admin_dashboard'))
    return redirect(next_url)

# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # All schedules for dropdown
    cur.execute("SELECT * FROM quiz_schedules ORDER BY exam_date DESC, start_time DESC")
    all_schedules = cur.fetchall()

    # Currently selected schedule from session
    sel_id = get_selected_schedule_id()
    selected_schedule = get_schedule_by_id(sel_id) if sel_id else None

    # ── STATS scoped to selected subject (or global if none selected) ──────────
    if sel_id:
        cur.execute("SELECT COUNT(DISTINCT r.user_id) AS cnt FROM results r WHERE r.schedule_id=%s AND r.submitted=TRUE", (sel_id,))
        students_count = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM results WHERE schedule_id=%s AND submitted=TRUE", (sel_id,))
        attempts = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM questions WHERE schedule_id=%s", (sel_id,))
        total_questions = cur.fetchone()['cnt']
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE role='student'")
        students_count = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM results WHERE submitted=TRUE")
        attempts = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM questions")
        total_questions = cur.fetchone()['cnt']

    # Question counts per schedule (for the schedule table)
    cur.execute("SELECT schedule_id, COUNT(*) AS cnt FROM questions WHERE schedule_id IS NOT NULL GROUP BY schedule_id")
    q_counts = {r['schedule_id']: r['cnt'] for r in cur.fetchall()}
    cur.execute("SELECT COUNT(*) AS cnt FROM questions WHERE schedule_id IS NULL")
    general_count = cur.fetchone()['cnt']

    active = get_active_schedule()

    # ── TOP STUDENTS scoped to selected subject ────────────────────────────────
    if sel_id:
        cur.execute("""SELECT u.name,u.roll_number,r.obtained_marks AS best_marks,r.total_marks,
            ROUND(r.obtained_marks*100.0/NULLIF(r.total_marks,0),1) AS pct, 1 AS attempts
            FROM results r JOIN users u ON r.user_id=u.id
            WHERE r.schedule_id=%s AND r.submitted=TRUE
            ORDER BY r.obtained_marks DESC LIMIT 5""", (sel_id,))
    else:
        cur.execute("""SELECT u.name,u.roll_number,MAX(r.obtained_marks) AS best_marks,MAX(r.total_marks) AS total_marks,
            ROUND(MAX(r.obtained_marks*100.0/NULLIF(r.total_marks,0)),1) AS pct, COUNT(r.id) AS attempts
            FROM results r JOIN users u ON r.user_id=u.id WHERE r.submitted=TRUE
            GROUP BY u.id,u.name,u.roll_number ORDER BY best_marks DESC LIMIT 5""")
    top_students = cur.fetchall()

    # ── RECENT SUBMISSIONS scoped ──────────────────────────────────────────────
    if sel_id:
        cur.execute("""SELECT u.name,u.roll_number,r.obtained_marks,r.total_marks,
            ROUND(r.obtained_marks*100.0/NULLIF(r.total_marks,0),1) AS pct,
            r.quiz_date,r.subject_name,r.paper_code
            FROM results r JOIN users u ON r.user_id=u.id
            WHERE r.schedule_id=%s AND r.submitted=TRUE
            ORDER BY r.quiz_date DESC LIMIT 10""", (sel_id,))
    else:
        cur.execute("""SELECT u.name,u.roll_number,r.obtained_marks,r.total_marks,
            ROUND(r.obtained_marks*100.0/NULLIF(r.total_marks,0),1) AS pct,
            r.quiz_date,r.subject_name,r.paper_code
            FROM results r JOIN users u ON r.user_id=u.id
            WHERE r.submitted=TRUE ORDER BY r.quiz_date DESC LIMIT 10""")
    recent = cur.fetchall()

    timer = get_timer(); cur.close(); conn.close()
    return render_template('admin/dashboard.html',
        students=students_count, attempts=attempts, total_questions=total_questions,
        recent=recent, timer=timer, top_students=top_students,
        schedules=all_schedules, active=active,
        q_counts=q_counts, general_count=general_count,
        selected_schedule=selected_schedule, selected_schedule_id=sel_id)

# ─── SCHEDULE MANAGEMENT ──────────────────────────────────────────────────────
@app.route('/admin/schedule/add', methods=['POST'])
@admin_required
def admin_add_schedule():
    f = request.form
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""INSERT INTO quiz_schedules
            (subject_name,paper_code,exam_date,start_time,end_time,allow_reattempt)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (f['subject_name'],f['paper_code'],f['exam_date'],
             f['start_time'],f['end_time'],'allow_reattempt' in f))
        new_id = cur.fetchone()['id']
        conn.commit(); cur.close(); conn.close()
        # Auto-select the newly created schedule
        set_selected_schedule(new_id)
        flash(f"Scheduled: {f['subject_name']} ({f['paper_code']})", 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/schedule/edit/<int:sid>', methods=['POST'])
@admin_required
def admin_edit_schedule(sid):
    f = request.form
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("""UPDATE quiz_schedules SET subject_name=%s,paper_code=%s,
            exam_date=%s,start_time=%s,end_time=%s,allow_reattempt=%s WHERE id=%s""",
            (f['subject_name'],f['paper_code'],f['exam_date'],
             f['start_time'],f['end_time'],'allow_reattempt' in f,sid))
        conn.commit(); cur.close(); conn.close()
        flash('Schedule updated!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/schedule/delete/<int:sid>', methods=['POST'])
@admin_required
def admin_delete_schedule(sid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE questions SET schedule_id=NULL WHERE schedule_id=%s", (sid,))
    cur.execute("DELETE FROM quiz_schedules WHERE id=%s", (sid,))
    conn.commit(); cur.close(); conn.close()
    # Clear session selection if that schedule was selected
    if get_selected_schedule_id() == sid:
        set_selected_schedule(None)
    flash('Schedule deleted. Student results preserved.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/schedule/reattempt/<int:sid>', methods=['POST'])
@admin_required
def admin_toggle_reattempt(sid):
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT allow_reattempt FROM quiz_schedules WHERE id=%s", (sid,))
    row = cur.fetchone()
    if row:
        cur2 = conn.cursor()
        cur2.execute("UPDATE quiz_schedules SET allow_reattempt=%s WHERE id=%s",
                     (not row['allow_reattempt'],sid))
        conn.commit(); cur2.close()
        flash('Reattempt setting updated!', 'success')
    cur.close(); conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['POST'])
@admin_required
def admin_settings():
    try: t = max(10, int(request.form.get('timer_seconds', 3600)))
    except: t = 3600
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE quiz_settings SET timer_seconds=%s, updated_at=NOW()", (t,))
    conn.commit(); cur.close(); conn.close()
    flash('Timer updated!', 'success')
    return redirect(url_for('admin_dashboard'))

# ─── QUESTIONS (subject-scoped) ───────────────────────────────────────────────
@app.route('/admin/questions')
@admin_required
def admin_questions():
    # Use session selection as default, allow URL override
    schedule_id = request.args.get('schedule_id', None)
    if schedule_id is None:
        sid = get_selected_schedule_id()
        schedule_id = str(sid) if sid else 'all'

    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM quiz_schedules ORDER BY exam_date DESC")
    all_schedules = cur.fetchall()
    current_schedule = None

    if schedule_id != 'all':
        try:
            sid = int(schedule_id)
            cur.execute("SELECT * FROM quiz_schedules WHERE id=%s", (sid,))
            current_schedule = cur.fetchone()
            cur.execute("""SELECT q.*,qs.subject_name,qs.paper_code
                FROM questions q LEFT JOIN quiz_schedules qs ON q.schedule_id=qs.id
                WHERE q.schedule_id=%s ORDER BY q.id ASC""", (sid,))
        except:
            cur.execute("""SELECT q.*,qs.subject_name,qs.paper_code
                FROM questions q LEFT JOIN quiz_schedules qs ON q.schedule_id=qs.id ORDER BY q.id""")
    else:
        cur.execute("""SELECT q.*,qs.subject_name,qs.paper_code
            FROM questions q LEFT JOIN quiz_schedules qs ON q.schedule_id=qs.id
            ORDER BY qs.subject_name NULLS LAST, q.id""")

    questions = cur.fetchall(); cur.close(); conn.close()
    return render_template('admin/questions.html', questions=questions,
                           all_schedules=all_schedules, selected_schedule=schedule_id,
                           current_schedule=current_schedule)

@app.route('/admin/questions/add', methods=['GET','POST'])
@admin_required
def admin_add_question():
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM quiz_schedules ORDER BY exam_date DESC")
    schedules = cur.fetchall()
    # Pre-select using session selection
    preselect = request.args.get('schedule_id', '') or (str(get_selected_schedule_id()) if get_selected_schedule_id() else '')
    if request.method == 'POST':
        f = request.form; image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"q_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        marks       = int(f.get('marks', 1))
        schedule_id = f.get('schedule_id') or None
        cur2 = conn.cursor()
        cur2.execute("""INSERT INTO questions
            (question,option1,option2,option3,option4,answer,category,marks,image_filename,schedule_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (f['question'],f['option1'],f['option2'],f['option3'],f['option4'],
             f['answer'],f.get('category','General'),marks,image_filename,schedule_id))
        conn.commit(); cur2.close(); cur.close(); conn.close()
        flash('Question added!', 'success')
        return redirect(url_for('admin_questions', schedule_id=schedule_id or 'all'))
    cur.close(); conn.close()
    return render_template('admin/add_question.html', schedules=schedules, preselect=preselect)

@app.route('/admin/questions/edit/<int:qid>', methods=['GET','POST'])
@admin_required
def admin_edit_question(qid):
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM quiz_schedules ORDER BY exam_date DESC")
    schedules = cur.fetchall()
    if request.method == 'POST':
        f = request.form
        cur.execute("SELECT image_filename FROM questions WHERE id=%s", (qid,))
        existing       = cur.fetchone()
        image_filename = existing['image_filename'] if existing else None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"q_{qid}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        marks       = int(f.get('marks', 1))
        schedule_id = f.get('schedule_id') or None
        cur2 = conn.cursor()
        cur2.execute("""UPDATE questions SET question=%s,option1=%s,option2=%s,option3=%s,
            option4=%s,answer=%s,category=%s,marks=%s,image_filename=%s,schedule_id=%s WHERE id=%s""",
            (f['question'],f['option1'],f['option2'],f['option3'],f['option4'],
             f['answer'],f.get('category','General'),marks,image_filename,schedule_id,qid))
        conn.commit(); cur2.close(); cur.close(); conn.close()
        flash('Question updated!', 'success')
        return redirect(url_for('admin_questions', schedule_id=schedule_id or 'all'))
    cur.execute("SELECT * FROM questions WHERE id=%s", (qid,))
    q = cur.fetchone(); cur.close(); conn.close()
    if not q:
        flash('Question not found.', 'error')
        return redirect(url_for('admin_questions'))
    return render_template('admin/edit_question.html', q=q, schedules=schedules)

@app.route('/admin/questions/delete/<int:qid>', methods=['POST'])
@admin_required
def admin_delete_question(qid):
    ref = request.referrer or ''
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM questions WHERE id=%s", (qid,))
    conn.commit(); cur.close(); conn.close()
    flash('Question deleted.', 'success')
    return redirect(ref or url_for('admin_questions'))

@app.route('/admin/questions/delete-all', methods=['POST'])
@admin_required
def admin_delete_all_questions():
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM questions")
    conn.commit(); cur.close(); conn.close()
    flash('All questions deleted!', 'success')
    return redirect(url_for('admin_questions'))

@app.route('/admin/questions/delete-schedule/<int:sid>', methods=['POST'])
@admin_required
def admin_delete_schedule_questions(sid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM questions WHERE schedule_id=%s", (sid,))
    conn.commit(); cur.close(); conn.close()
    flash('Questions for this subject deleted!', 'success')
    return redirect(url_for('admin_questions', schedule_id=sid))

@app.route('/admin/questions/upload-csv', methods=['GET','POST'])
@admin_required
def admin_upload_csv():
    conn2 = get_db(); cur2 = conn2.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur2.execute("SELECT * FROM quiz_schedules ORDER BY exam_date DESC")
    all_schedules = cur2.fetchall(); cur2.close(); conn2.close()
    preselect = request.args.get('schedule_id', '') or (str(get_selected_schedule_id()) if get_selected_schedule_id() else '')
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file.', 'error'); return redirect(url_for('admin_upload_csv'))
        file               = request.files['csv_file']
        upload_schedule_id = request.form.get('upload_schedule_id') or None
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file.', 'error'); return redirect(url_for('admin_upload_csv'))
        try:
            stream  = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            reader  = csv.DictReader(stream)
            required = {'question','option1','option2','option3','option4','answer'}
            if not required.issubset(set(reader.fieldnames or [])):
                flash('CSV missing required columns: question, option1–4, answer.', 'error')
                return redirect(url_for('admin_upload_csv'))
            conn = get_db(); cur = conn.cursor(); count = 0
            for row in reader:
                if row.get('question','').strip():
                    marks = int(row.get('marks',1)) if row.get('marks','').strip().isdigit() else 1
                    cur.execute("""INSERT INTO questions
                        (question,option1,option2,option3,option4,answer,category,marks,schedule_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (row['question'].strip(),row['option1'].strip(),row['option2'].strip(),
                         row['option3'].strip(),row['option4'].strip(),row['answer'].strip(),
                         row.get('category','General').strip(),marks,upload_schedule_id))
                    count += 1
            conn.commit(); cur.close(); conn.close()
            flash(f'{count} questions imported!', 'success')
            return redirect(url_for('admin_questions', schedule_id=upload_schedule_id or 'all'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    return render_template('admin/upload_csv.html', all_schedules=all_schedules, preselect=preselect)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    safe_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if not os.path.exists(safe_path):
        return "File not found", 404
    return send_file(safe_path)

# ─── STUDENTS (subject-scoped) ────────────────────────────────────────────────
@app.route('/admin/students')
@admin_required
def admin_students():
    sel_id = get_selected_schedule_id()
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    selected_schedule = get_schedule_by_id(sel_id) if sel_id else None

    if sel_id:
        # Only students who attempted the selected subject
        cur.execute("""SELECT u.id,u.name,u.roll_number,u.email,u.joined,
            COUNT(r.id) AS attempts,
            COALESCE(MAX(r.obtained_marks),0) AS best_marks,
            COALESCE(MAX(r.total_marks),0) AS total_marks,
            COALESCE(ROUND(MAX(r.obtained_marks*100.0/NULLIF(r.total_marks,0)),1),0) AS best_pct
            FROM users u
            JOIN results r ON u.id=r.user_id AND r.submitted=TRUE AND r.schedule_id=%s
            WHERE u.role='student'
            GROUP BY u.id ORDER BY best_marks DESC""", (sel_id,))
    else:
        cur.execute("""SELECT u.id,u.name,u.roll_number,u.email,u.joined,
            COUNT(r.id) AS attempts,
            COALESCE(MAX(r.obtained_marks),0) AS best_marks,
            COALESCE(MAX(r.total_marks),0) AS total_marks,
            COALESCE(ROUND(MAX(r.obtained_marks*100.0/NULLIF(r.total_marks,0)),1),0) AS best_pct,
            STRING_AGG(DISTINCT r.subject_name,', ')
                FILTER (WHERE r.subject_name IS NOT NULL AND r.subject_name != '') AS subjects
            FROM users u LEFT JOIN results r ON u.id=r.user_id AND r.submitted=TRUE
            WHERE u.role='student'
            GROUP BY u.id ORDER BY best_marks DESC""")

    students = cur.fetchall(); cur.close(); conn.close()
    return render_template('admin/students.html', students=students,
                           selected_schedule=selected_schedule)

@app.route('/admin/students/delete/<int:uid>', methods=['POST'])
@admin_required
def admin_delete_student(uid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s AND role='student'", (uid,))
    conn.commit(); cur.close(); conn.close()
    flash('Student deleted.', 'success')
    return redirect(url_for('admin_students'))

# ─── RESULTS (subject-scoped) ─────────────────────────────────────────────────
@app.route('/admin/results')
@admin_required
def admin_results():
    sel_id = get_selected_schedule_id()
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    selected_schedule = get_schedule_by_id(sel_id) if sel_id else None

    if sel_id:
        cur.execute("""SELECT r.id,u.name,u.roll_number,r.score,r.total,
            r.obtained_marks,r.total_marks,
            ROUND(r.obtained_marks*100.0/NULLIF(r.total_marks,0),1) AS pct,
            r.quiz_date,r.subject_name,r.paper_code,r.exam_date
            FROM results r JOIN users u ON r.user_id=u.id
            WHERE r.submitted=TRUE AND r.schedule_id=%s
            ORDER BY r.obtained_marks DESC,r.quiz_date DESC""", (sel_id,))
    else:
        cur.execute("""SELECT r.id,u.name,u.roll_number,r.score,r.total,
            r.obtained_marks,r.total_marks,
            ROUND(r.obtained_marks*100.0/NULLIF(r.total_marks,0),1) AS pct,
            r.quiz_date,r.subject_name,r.paper_code,r.exam_date
            FROM results r JOIN users u ON r.user_id=u.id
            WHERE r.submitted=TRUE
            ORDER BY r.obtained_marks DESC,r.quiz_date DESC""")

    results = cur.fetchall(); cur.close(); conn.close()
    return render_template('admin/results.html', results=results,
                           selected_schedule=selected_schedule)

@app.route('/admin/results/delete/<int:rid>', methods=['POST'])
@admin_required
def admin_delete_result(rid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM results WHERE id=%s", (rid,))
    conn.commit(); cur.close(); conn.close()
    flash('Result deleted.', 'success')
    return redirect(url_for('admin_results'))

# ─── PDF EXPORT (subject-scoped) ──────────────────────────────────────────────
@app.route('/admin/leaderboard/pdf')
@app.route('/admin/leaderboard/pdf/<int:schedule_id>')
@admin_required
def export_leaderboard_pdf(schedule_id=None):
    # If no schedule_id in URL, use session selection
    if schedule_id is None:
        schedule_id = get_selected_schedule_id()

    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if schedule_id:
        cur.execute("SELECT * FROM quiz_schedules WHERE id=%s", (schedule_id,))
        schedule_info = cur.fetchone()
        cur.execute("""SELECT u.name,u.roll_number,r.obtained_marks,r.total_marks,
            ROUND(r.obtained_marks*100.0/NULLIF(r.total_marks,0),1) AS pct,
            r.quiz_date,r.subject_name,r.paper_code,r.exam_date
            FROM results r JOIN users u ON r.user_id=u.id
            WHERE r.submitted=TRUE AND r.schedule_id=%s
            ORDER BY r.obtained_marks DESC""", (schedule_id,))
    else:
        schedule_info = None
        cur.execute("""SELECT u.name,u.roll_number,
            MAX(r.obtained_marks) AS obtained_marks,MAX(r.total_marks) AS total_marks,
            ROUND(MAX(r.obtained_marks*100.0/NULLIF(r.total_marks,0)),1) AS pct,
            MAX(r.quiz_date) AS quiz_date,MAX(r.subject_name) AS subject_name,
            MAX(r.paper_code) AS paper_code,MAX(r.exam_date) AS exam_date
            FROM results r JOIN users u ON r.user_id=u.id WHERE r.submitted=TRUE
            GROUP BY u.id,u.name,u.roll_number ORDER BY obtained_marks DESC""")
    leaders = cur.fetchall(); cur.close(); conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        rightMargin=0.5*inch, leftMargin=0.5*inch, topMargin=0.75*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    elements = []
    title_style = ParagraphStyle('T',fontSize=18,fontName='Helvetica-Bold',alignment=1,
        spaceAfter=4,textColor=colors.HexColor('#1a3a5c'))
    sub_style = ParagraphStyle('S',fontSize=10,fontName='Helvetica',alignment=1,
        spaceAfter=4,textColor=colors.grey)
    elements.append(Paragraph("Smart Online Quiz System", title_style))
    elements.append(Paragraph("Result Report", title_style))
    elements.append(Spacer(1,8))
    if schedule_info:
        elements.append(Paragraph(f"Subject: {schedule_info['subject_name']}  |  Paper Code: {schedule_info['paper_code']}", sub_style))
        exam_d = schedule_info['exam_date']
        elements.append(Paragraph(f"Exam Date: {exam_d.strftime('%d %B %Y') if exam_d else '—'}", sub_style))
        elements.append(Paragraph(f"Time: {schedule_info['start_time'].strftime('%I:%M %p')} — {schedule_info['end_time'].strftime('%I:%M %p')}", sub_style))
    else:
        elements.append(Paragraph(f"All Subjects — {datetime.now().strftime('%d %b %Y')}", sub_style))
    elements.append(Spacer(1,16))
    data = [['Rank','Name','Roll Number','Marks Obtained','Total Marks','Percentage']]
    for i,s in enumerate(leaders,1):
        data.append([str(i),s['name'],s['roll_number'] or '—',
            str(s['obtained_marks'] or 0),str(s['total_marks'] or 0),f"{s['pct'] or 0}%"])
    t = Table(data, colWidths=[0.5*inch,2.2*inch,1.5*inch,1.3*inch,1.3*inch,1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f7ff'),colors.white]),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#cccccc')),
        ('ROWHEIGHT',(0,0),(-1,-1),22),
        ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#ffd700')),
        ('BACKGROUND',(0,2),(-1,2),colors.HexColor('#e8e8e8')),
        ('BACKGROUND',(0,3),(-1,3),colors.HexColor('#cd7f32')),
        ('FONTNAME',(0,1),(-1,3),'Helvetica-Bold'),
    ]))
    elements.append(t); elements.append(Spacer(1,16))
    elements.append(Paragraph(f"Total Students: {len(leaders)}", styles['Normal']))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y at %I:%M %p')}", sub_style))
    doc.build(elements); buffer.seek(0)
    subj_safe = (schedule_info['subject_name'] if schedule_info else 'all_subjects').replace(' ','_')
    fname = f"result_{subj_safe}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=fname, mimetype='application/pdf')

@app.route('/admin/change-password', methods=['GET','POST'])
@admin_required
def admin_change_password():
    if request.method == 'POST':
        current  = request.form.get('current_password','')
        new_pass = request.form.get('new_password','')
        confirm  = request.form.get('confirm_password','')
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
        admin = cur.fetchone()
        if not check_password_hash(admin['password'], current):
            flash('Current password incorrect.', 'error')
        elif new_pass != confirm:
            flash('Passwords do not match.', 'error')
        elif len(new_pass) < 6:
            flash('Minimum 6 characters.', 'error')
        else:
            cur2 = conn.cursor()
            cur2.execute("UPDATE users SET password=%s WHERE id=%s",
                         (generate_password_hash(new_pass), session['user_id']))
            conn.commit(); cur2.close()
            flash('Password changed!', 'success')
            session.clear(); cur.close(); conn.close()
            return redirect(url_for('admin_login'))
        cur.close(); conn.close()
    return render_template('admin/change_password.html')

# ─── ERROR HANDLERS ───────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e): return render_template('error.html', code=404, message="Page not found."), 404

@app.errorhandler(500)
def server_error(e): return render_template('error.html', code=500, message="Something went wrong on our end."), 500

@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum 5MB.', 'error')
    return redirect(request.referrer or url_for('admin_questions'))

init_db()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
