import os
import io
import threading
import sqlite3
import datetime
import json
from flask import Flask, render_template, request, jsonify, send_file, abort
from model import train_model_background, extract_embedding_for_image, MODEL_PATH


#---new hide---
import os
from dotenv import load_dotenv

# Wakes up the hidden .env file
load_dotenv() 

# ---------- Security Configuration ----------
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default_fallback_key")



#---gamma ai---
from ai_assistant import get_ai_explanation

#----oswasp---
import re
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import session, redirect, url_for, flash

#--new ai 
import requests

# Wakes up the hidden .env file


#----mailman----
import smtplib
from email.mime.text import MIMEText
import threading


def send_welcome_email(student_email, student_name):
    sender_email = os.environ.get("EMAIL_USER")
    app_password = os.environ.get("EMAIL_PASS")

    msg = MIMEText(f"Hello {student_name},\n\nYou have been successfully registered in the IntelliAttend system.")
    msg['Subject'] = "Registration Successful - IntelliAttend"
    msg['From'] = sender_email
    msg['To'] = student_email

    try:
       server = smtplib.SMTP('smtp.gmail.com', 587)
       server.ehlo()
       server.starttls() # This secures the connection
       server.login(sender_email, app_password)
       server.send_message(msg)
       server.quit()
       print(f" Real welcome email sent to {student_email}")
       
       
       
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_alert_email(student_email, student_name, message_body):
    sender_email = os.environ.get("EMAIL_USER")
    app_password = os.environ.get("EMAIL_PASS")
   

    msg = MIMEText(message_body)
    msg['Subject'] = f"Attendance Alert for {student_name}"
    msg['From'] = sender_email
    msg['To'] = student_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f" Failed to send email: {e}")
        return False
    
    
    
    
    
    
    





















APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")
DATASET_DIR = os.path.join(APP_DIR, "dataset")
os.makedirs(DATASET_DIR, exist_ok=True)

TRAIN_STATUS_FILE = os.path.join(APP_DIR, "train_status.json")

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------- Security Configuration ----------
# Use an environment variable for the secret key, with a fallback for local hackathon testing
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "hackathon_super_secret_key_123")

# Admin credentials (Password is dynamically hashed so plaintext is not hardcoded as a persistent string)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_HASH", generate_password_hash("admin123"))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Authentication Decorator ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            # Return JSON 401 for API routes, redirect to login for UI routes
            if request.is_json or request.path.startswith('/train_') or request.path.startswith('/students'):
                return jsonify({"error": "Unauthorized. Admin access required."}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Global Error Handler ----------
@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Server Error: {e}")
    # Do not leak stack traces to the user
    return jsonify({"error": "Something went wrong. Please try again."}), 500



# ---------- DB helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    roll TEXT,
                    class TEXT,
                    email TEXT,
                    reg_no TEXT,
                    created_at TEXT
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    name TEXT,
                    timestamp TEXT
                )""")
    conn.commit()
    conn.close()

init_db()

# ---------- Train status helpers ----------
def write_train_status(status_dict):
    with open(TRAIN_STATUS_FILE, "w") as f:
        json.dump(status_dict, f)

def read_train_status():
    if not os.path.exists(TRAIN_STATUS_FILE):
        return {"running": False, "progress": 0, "message": "Not trained"}
    with open(TRAIN_STATUS_FILE, "r") as f:
        return json.load(f)

# ensure initial train status file exists
write_train_status({"running": False, "progress": 0, "message": "No training yet."})

# ---------- Routes ----------
@app.route("/")
@login_required
def index():
    return render_template("index.html")




# ---------- Login & Logout Routes ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        # Verify credentials using Werkzeug hash checking
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["logged_in"] = True
            return redirect(url_for("index"))
        
        # If login fails, reload page with error message
        return render_template("login.html", error="Invalid username or password")
    
    # If request is GET, just show the login page
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear() # Destroys the session token securely
    return redirect(url_for("login"))





#--- gemini api ----
@app.route("/ai_summary", methods=["GET"])
@login_required
def ai_summary():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 1. Get total number of registered students
        c.execute("SELECT COUNT(id) FROM students")
        total_students = c.fetchone()[0]
        
        # 2. Get unique students present today
        today = datetime.date.today().isoformat()
        c.execute("SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date(timestamp) = ?", (today,))
        present_today = c.fetchone()[0]
        conn.close()
        
        absent_today = total_students - present_today
        
        # 3. Create the prompt
        prompt = f"Today's Attendance - Present: {present_today}, Absent: {absent_today}, Total: {total_students}. Write a short 2-sentence summary of this data in a professional tone."
        
        # 4. The Safe Web Request Method (No pip installs required)
        import urllib.request
        import json
        
        api_key = os.environ.get("GEMINI_API_KEY")
        # Use the standard generateContent URL with the API key in the query string
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # The strictly required JSON format for the Gemini API
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"), method="POST")
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            # Extract the generated text from Google's response structure
            summary_text = result["candidates"][0]["content"]["parts"][0]["text"]
            
        return jsonify({"summary": summary_text.strip()})
    except Exception as e:
        app.logger.error(f"AI Summary Error: {e}")
        return jsonify({"error": str(e)}), 500


    
# Dashboard simple API for attendance stats (last 30 days)
@app.route("/attendance_stats")
@login_required
def attendance_stats():
    import pandas as pd
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT timestamp FROM attendance", conn)
    conn.close()
    if df.empty:
        from datetime import date, timedelta
        days = [(date.today() - datetime.timedelta(days=i)).strftime("%d-%b") for i in range(29, -1, -1)]
        return jsonify({"dates": days, "counts": [0]*30})
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    last_30 = [ (datetime.date.today() - datetime.timedelta(days=i)) for i in range(29, -1, -1) ]
    counts = [ int(df[df['date'] == d].shape[0]) for d in last_30 ]
    dates = [ d.strftime("%d-%b") for d in last_30 ]
    return jsonify({"dates": dates, "counts": counts})

# -------- Add student (form) --------
@app.route("/add_student", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "GET":
        return render_template("add_student.html")
    # POST: save student metadata and return student_id
    data = request.form
    name = data.get("name","").strip()
    roll = data.get("roll","").strip()
    cls = data.get("class","").strip()
    email = data.get("email","").strip()
    reg_no = data.get("reg_no","").strip()
    # if not name:
        # return jsonify({"error":"name required"}), 400

    # --- NEW: Input Validation ---
    if not name or not re.match(r"^[A-Za-z\s]+$", name):
        return jsonify({"error":"Invalid name. Use letters and spaces only."}), 400
    if email and not re.match(EMAIL_REGEX, email):
        return jsonify({"error":"Invalid email format."}), 400

    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    c.execute("INSERT INTO students (name, roll, class, email, reg_no, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (name, roll, cls, email, reg_no, now))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    # create dataset folder for this student
    os.makedirs(os.path.join(DATASET_DIR, str(sid)), exist_ok=True)

    # NEW: Trigger the email in the background
    if email:
        email_thread = threading.Thread(target=send_welcome_email, args=(email, name))
        email_thread.start()


    return jsonify({"student_id": sid})

# -------- Upload face images (after capture) --------
@app.route("/upload_face", methods=["POST"])
@login_required
def upload_face():
    student_id = request.form.get("student_id")
    if not student_id:
        return jsonify({"error":"student_id required"}), 400
    files = request.files.getlist("images[]")
    saved = 0
    folder = os.path.join(DATASET_DIR, student_id)
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    for f in files:
        # --- NEW: Secure File Validation ---
     if f and allowed_file(f.filename):
        try:
            # secure_filename strips malicious directory paths (like ../../)
            safe_name = secure_filename(f.filename)
            ext = safe_name.rsplit('.', 1)[1].lower()

            fname = f"{datetime.datetime.utcnow().timestamp():.6f}_{saved}.jpg"
            path = os.path.join(folder, fname)
            f.save(path)
            saved += 1
        except Exception as e:
            app.logger.error("save error: %s", e)
    return jsonify({"saved": saved})

# -------- Train model (start background thread) --------
@app.route("/train_model", methods=["GET"])
@login_required
def train_model_route():
    # if already running, respond accordingly
    status = read_train_status()
    if status.get("running"):
        return jsonify({"status":"already_running"}), 202
    # reset status
    write_train_status({"running": True, "progress": 0, "message": "Starting training"})
    # start background thread
    t = threading.Thread(target=train_model_background, args=(DATASET_DIR, lambda p,m: write_train_status({"running": True, "progress": p, "message": m})))
    t.daemon = True
    t.start()
    return jsonify({"status":"started"}), 202

# -------- Train progress (polling) --------
@app.route("/train_status", methods=["GET"])
def train_status():
    return jsonify(read_train_status())

# -------- Mark attendance page --------
@app.route("/mark_attendance", methods=["GET"])
def mark_attendance_page():
    return render_template("mark_attendance.html")

# -------- Recognize face endpoint (POST image) --------
@app.route("/recognize_face", methods=["POST"])
def recognize_face():
    if "image" not in request.files:
        return jsonify({"recognized": False, "error":"no image"}), 400
    img_file = request.files["image"]
    try:
        emb = extract_embedding_for_image(img_file.stream)
        if emb is None:
            return jsonify({"recognized": False, "error":"no face detected"}), 200
        # attempt prediction
        from model import load_model_if_exists, predict_with_model
        clf = load_model_if_exists()
        if clf is None:
            return jsonify({"recognized": False, "error":"model not trained"}), 200
        pred_label, conf = predict_with_model(clf, emb)
        # threshold confidence
        if conf < 0.5:
            return jsonify({"recognized": False, "confidence": float(conf)}), 200
        # find student name
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM students WHERE id=?", (int(pred_label),))
        row = c.fetchone()
        name = row[0] if row else "Unknown"
        # save attendance record with timestamp
        ts = datetime.datetime.utcnow().isoformat()
        c.execute("INSERT INTO attendance (student_id, name, timestamp) VALUES (?, ?, ?)", (int(pred_label), name, ts))
        conn.commit()
        conn.close()
        return jsonify({"recognized": True, "student_id": int(pred_label), "name": name, "confidence": float(conf)}), 200
    except Exception as e:
        app.logger.exception("recognize error")
        return jsonify({"recognized": False, "error": str(e)}), 500

# -------- Attendance records & filters --------
@app.route("/attendance_record", methods=["GET"])
@login_required
def attendance_record():
    period = request.args.get("period", "all")  # all, daily, weekly, monthly
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    q = "SELECT id, student_id, name, timestamp FROM attendance"
    params = ()
    if period == "daily":
        today = datetime.date.today().isoformat()
        q += " WHERE date(timestamp) = ?"
        params = (today,)
    elif period == "weekly":
        start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        q += " WHERE date(timestamp) >= ?"
        params = (start,)
    elif period == "monthly":
        start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        q += " WHERE date(timestamp) >= ?"
        params = (start,)
    q += " ORDER BY timestamp DESC LIMIT 5000"
    c.execute(q, params)
    rows = c.fetchall()
    conn.close()
    return render_template("attendance_record.html", records=rows, period=period)

# -------- CSV download --------
@app.route("/download_csv", methods=["GET"])
@login_required
def download_csv():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, student_id, name, timestamp FROM attendance ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    output = io.StringIO()
    output.write("id,student_id,name,timestamp\n")
    for r in rows:
        output.write(f'{r[0]},{r[1]},{r[2]},{r[3]}\n')
    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name="attendance.csv", mimetype="text/csv")

# -------- Students API for listing/editing --------
@app.route("/students", methods=["GET"])
@login_required
def students_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, roll, class, email, reg_no, created_at FROM students ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    data = [ {"id":r[0],"name":r[1],"roll":r[2],"class":r[3],"email":r[4],"reg_no":r[5],"created_at":r[6]} for r in rows ]
    return jsonify({"students": data})

@app.route("/students/<int:sid>", methods=["DELETE"])
@login_required
def delete_student(sid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE id=?", (sid,))
    c.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
    conn.commit()
    conn.close()
    # also delete dataset folder
    folder = os.path.join(DATASET_DIR, str(sid))
    if os.path.isdir(folder):
        import shutil
        shutil.rmtree(folder, ignore_errors=True)
    return jsonify({"deleted": True})


# -------- AI Absence Notice Generator --------



# -------- AI Absence Notice Generator --------
@app.route("/generate_absence_notices", methods=["GET"])
@login_required
def generate_absence_notices():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        today = datetime.date.today().isoformat()
        c.execute("SELECT id, name, email FROM students WHERE id NOT IN (SELECT student_id FROM attendance WHERE date(timestamp) = ?)", (today,))
        absent_students = c.fetchall()
        conn.close()

        if not absent_students:
            return jsonify({"status": "success", "message": "All students are present today! No notices needed."})

        #-----email
        sent_count = 0
        for student in absent_students:
            student_id, name, email = student
            if email:
                message = f"Dear {name},\n\nOur records indicate you missed class today. Please ensure you maintain the required attendance threshold."
                if send_alert_email(email, name, message):
                    sent_count += 1

        return jsonify({"status": "success", "message": f"Successfully sent {sent_count} absence emails."})
        
    except Exception as e:
        app.logger.error(f"Notice Generator Error: {e}")
        return jsonify({"status": "error", "message": "An error occurred while generating notices."}), 500

       


# -------- AI Attendance Assistant --------
@app.route("/ask_ai", methods=["POST"])
def ask_ai():
    req_data = request.json
    action = req_data.get("action", "summary")
    student_data = req_data.get("data", {})

    if not student_data or "student" not in student_data:
        return jsonify({"success": False, "message": "Invalid attendance data provided."}), 400

    success, ai_response = get_ai_explanation(student_data, action)

    if success:
        return jsonify({"success": True, "response": ai_response})
    else:
        return jsonify({"success": False, "message": ai_response}), 503



    
# ---------------- run ------------------------
if __name__ == "__main__":
    app.run(debug=True)