import os
import io
import threading
import sqlite3
import datetime
import json
from flask import Flask, render_template, request, jsonify, send_file, abort
from model import train_model_background, extract_embedding_for_image, MODEL_PATH


#--new ai 
import requests



APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")
DATASET_DIR = os.path.join(APP_DIR, "dataset")
os.makedirs(DATASET_DIR, exist_ok=True)

TRAIN_STATUS_FILE = os.path.join(APP_DIR, "train_status.json")

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------- DB helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    roll TEXT,
                    class TEXT,
                    section TEXT,
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
def index():
    return render_template("index.html")


#--- gemini api ----
@app.route("/ai_summary", methods=["GET"])
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
        
        api_key = "YOUR_GEMINI_API_KEY"
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
def add_student():
    if request.method == "GET":
        return render_template("add_student.html")
    # POST: save student metadata and return student_id
    data = request.form
    name = data.get("name","").strip()
    roll = data.get("roll","").strip()
    cls = data.get("class","").strip()
    sec = data.get("sec","").strip()
    reg_no = data.get("reg_no","").strip()
    if not name:
        return jsonify({"error":"name required"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    c.execute("INSERT INTO students (name, roll, class, section, reg_no, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (name, roll, cls, sec, reg_no, now))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    # create dataset folder for this student
    os.makedirs(os.path.join(DATASET_DIR, str(sid)), exist_ok=True)
    return jsonify({"student_id": sid})

# -------- Upload face images (after capture) --------
@app.route("/upload_face", methods=["POST"])
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
        try:
            fname = f"{datetime.datetime.utcnow().timestamp():.6f}_{saved}.jpg"
            path = os.path.join(folder, fname)
            f.save(path)
            saved += 1
        except Exception as e:
            app.logger.error("save error: %s", e)
    return jsonify({"saved": saved})

# -------- Train model (start background thread) --------
@app.route("/train_model", methods=["GET"])
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
def students_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, roll, class, section, reg_no, created_at FROM students ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    data = [ {"id":r[0],"name":r[1],"roll":r[2],"class":r[3],"section":r[4],"reg_no":r[5],"created_at":r[6]} for r in rows ]
    return jsonify({"students": data})

@app.route("/students/<int:sid>", methods=["DELETE"])
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
@app.route("/generate_absence_notices", methods=["GET"])
def generate_absence_notices():
    try:
        # 1. Connect to the database safely
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 2. Find students who do NOT have attendance recorded today
        today = datetime.date.today().isoformat()
        c.execute("SELECT id, name FROM students WHERE id NOT IN (SELECT student_id FROM attendance WHERE date(timestamp) = ?)", (today,))
        absent_students = c.fetchall()
        conn.close()

        # 3. If everyone is present, stop here
        if not absent_students:
            return jsonify({"status": "success", "message": "All students are present today! No notices needed."})

        # 4. Extract just the names of the absent students
        names_list = ", ".join([row[1] for row in absent_students])
        
        # 5. Create a fake AI response for testing (we will connect real AI later)
        ai_response = f"Drafted Notice: 'Dear Parent, our records indicate {names_list} missed class today. Please confirm the reason for absence.'"

        return jsonify({"status": "success", "message": ai_response})
        
    except Exception as e:
        app.logger.error(f"Notice Generator Error: {e}")
        return jsonify({"status": "error", "message": "An error occurred while generating notices."}), 500
    


# -------- new Attendance AI Insight Chat --------
@app.route("/ask_ai", methods=["POST"])
def ask_ai():
    try:
        data = request.get_json()
        question = data.get("question", "")

        # 1. Safely read the database to get the latest stats
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get total days present for each student
        c.execute("""
            SELECT s.name, COUNT(a.id) 
            FROM students s 
            LEFT JOIN attendance a ON s.id = a.student_id 
            GROUP BY s.id
        """)
        records = c.fetchall()
        
        # Get who is specifically present today
        today = datetime.date.today().isoformat()
        c.execute("SELECT name FROM attendance WHERE date(timestamp) = ?", (today,))
        present_today = [r[0] for r in c.fetchall()]
        conn.close()

        # 2. Translate the raw data into a text format Gemma can understand
        attendance_summary = ", ".join([f"{row[0]} ({row[1]} days present)" for row in records])
        today_summary = ", ".join(present_today) if present_today else "Nobody yet"

        # 3. Build the prompt for Gemma
        ai_prompt = f"""
        You are the IntelliAttend AI assistant. Answer the teacher's question using ONLY this data:
        - Overall Attendance: {attendance_summary}
        - Students Present Today: {today_summary}
        
        Teacher's question: "{question}"
        """

        # 4. Connect to Open-Source Gemma AI (via Hugging Face)
        API_URL = "https://api-inference.huggingface.co/models/google/gemma-1.1-7b-it"
        headers = {"Authorization": "Bearer YOUR_HUGGINGFACE_TOKEN"} # <-- Put your Hugging Face token here

        # Tell Gemma exactly how to behave (Grounding)
        system_instructions = "You are a school database assistant. You must ONLY use the provided data to answer the question. Keep your answer under 3 sentences. Do not make up information."
        
        full_prompt = f"{system_instructions}\n\nData:\n- Overall Attendance: {attendance_summary}\n- Present Today: {today_summary}\n\nTeacher Question: {question}\nAnswer:"

        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": 100,
                "temperature": 0.2, # Low temperature forces the AI to stick to the facts
                "return_full_text": False
            }
        }

        # Tell Python to ignore any invisible proxy settings on your computer
        proxies = {
            "http": None,
            "https": None
        }

        # Send the data to Gemma with the proxy bypass and the correct try/except blocks
        try:
            response = requests.post(API_URL, headers=headers, json=payload, proxies=proxies, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                ai_answer = result[0]['generated_text'].strip()
            elif response.status_code == 503:
                ai_answer = "The open-source AI is currently overloaded. Please wait a moment."
            else:
                ai_answer = f"AI API Error: Received status code {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            ai_answer = "Network Error: Could not connect to the AI server. Please check your firewall."
        except requests.exceptions.Timeout:
            ai_answer = "Network Timeout: The AI server took too long to respond."

        return jsonify({"answer": ai_answer})

    except Exception as e:
        app.logger.error(f"AI Chat Error: {e}")
        return jsonify({"answer": "I am having trouble connecting to the database right now."}), 500


    
# ---------------- run ------------------------
if __name__ == "__main__":
    app.run(debug=True)