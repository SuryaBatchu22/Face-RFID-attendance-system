# app.py

import os
import base64
import datetime
from datetime import timedelta
import cv2
import numpy as np
import pandas as pd
import face_recognition
import serial
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
# ── Load environment variables from .env ────────────────────────────────────
load_dotenv()

# ── DEMO MODE CONFIG ─────────────────────────────────────────────────────────
# When True, /scan_rfid returns a preset UID instead of reading hardware.
DEMO_MODE = True
DEMO_UIDS = {
    'embedded':    'e3b4a936',
    'intelligent': '05D4E6F7'
}

# ── CONFIGURATION ────────────────────────────────────────────────────────────
SERIAL_PORT   = 'COM7'
BAUD_RATE     = 9600

# Account and app‐password for sending email notifications
CLASS_ACCOUNT = {
    "email":        os.getenv("GMAIL_USER"),
    "app_password": os.getenv("GMAIL_APP_PASSWORD")
}

# Define each class: its name, Excel file, schedule, and professor email
CLASSES = {
    'embedded': {
        'name':          'Embedded Systems',
        'students_file': 'embedded_students.xlsx',
        'prefix':        'embedded',
        'start_time':    datetime.time(13, 45),     # class start at 13:30
        'prof_email':    os.getenv("EMBEDDED_PROF"), #paste your subject professor email here
        'days':          [0, 2, 3, 4, 6]             # Mon, Wed, Thu, Fri, Sun
    },
    'intelligent': {
        'name':          'Intelligent Systems',
        'students_file': 'intelligent_students.xlsx',
        'prefix':        'intelligent',
        'start_time':    datetime.time(16, 0),      # class start at 16:00
        'prof_email':    os.getenv("INTELLIGENT_PROF"), #paste your subject professor email here
        'days':          [1, 3]                     # Tue, Thu
    }
}

FACES_DIR   = "faces"               # where face images are stored
REPORTS_DIR = "attendance_reports"  # where daily sheets are saved

# Track which professors have been emailed today
emailed_professor = { key: False for key in CLASSES }

# ── FLASK SETUP ───────────────────────────────────────────────────────────────
app = Flask(__name__)
os.makedirs(FACES_DIR,   exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
# Uncomment when real hardware is connected:
# ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=10)

# ── EMAIL HELPERS ─────────────────────────────────────────────────────────────
def send_email(to_addr, subject, body, attachment_path=None):
    """Send an email (with optional attachment)."""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From']    = CLASS_ACCOUNT['email']
    msg['To']      = to_addr
    msg.set_content(body)
    if attachment_path:
        with open(attachment_path, 'rb') as f:
            data = f.read()
            fn   = os.path.basename(attachment_path)
        msg.add_attachment(data, maintype='application', subtype='octet-stream', filename=fn)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(CLASS_ACCOUNT['email'], CLASS_ACCOUNT['app_password'])
        smtp.send_message(msg)

def send_professor_report(subject_key, subject_cfg):
    """Email the daily attendance sheet to the professor if it exists."""
    prefix = subject_cfg['prefix']
    today  = datetime.date.today().strftime("%Y_%m_%d")
    path   = os.path.join(REPORTS_DIR, f"{prefix}_{today}.xlsx")
    if os.path.exists(path):
        subj = subject_cfg['name']
        subject_line = f"Daily Attendance Sheet: {subj} ({today})"
        body = f"Please find attached the attendance sheet for {subj} on {today}."
        send_email(subject_cfg['prof_email'], subject_line, body, attachment_path=path)

# ── STUDENT EMAIL HELPERS ────────────────────────────────────────────────────
def send_registration_email(cfg, student_email, student_name):
    """Notify student of successful registration."""
    subj = cfg['name']
    subject_line = f"Registered for {subj} Attendance"
    body = f"Hello {student_name},\n\nYou have been registered for {subj} attendance."
    send_email(student_email, subject_line, body)

def send_attendance_email(cfg, student_email, student_name):
    """Notify student when their attendance is marked."""
    subj = cfg['name']
    subject_line = f"Attendance Marked for {subj}"
    body = f"Dear {student_name},\n\nYour attendance for {subj} has been marked."
    send_email(student_email, subject_line, body)

# ── CLASS WINDOW HELPER ───────────────────────────────────────────────────────
def get_current_class():
    """
    Return (key, cfg) if current time is within -10/+20 min of any class on its meeting days.
    Otherwise return (None, None).
    """
    now      = datetime.datetime.now()
    today_wd = now.weekday()
    for key, cfg in CLASSES.items():
        if today_wd not in cfg['days']:
            continue
        start_dt     = datetime.datetime.combine(now.date(), cfg['start_time'])
        window_start = start_dt - timedelta(minutes=10)
        window_end   = start_dt + timedelta(minutes=20)
        if window_start <= now <= window_end:
            return key, cfg
    return None, None

# ── STUDENT DATA HELPERS ─────────────────────────────────────────────────────
def load_students(subject):
    """Load or create the student list for a subject."""
    fn = CLASSES[subject]['students_file']
    if not os.path.exists(fn):
        pd.DataFrame(columns=["Student_ID","Roll_Number","Name","Email"]) \
          .to_excel(fn, index=False)
    df = pd.read_excel(fn)
    df.columns = [c.strip() for c in df.columns]
    return df

def save_students(subject, df):
    """Save the students DataFrame back to Excel."""
    df.to_excel(CLASSES[subject]['students_file'], index=False)

# ── ATTENDANCE FILE HELPERS ───────────────────────────────────────────────────
def create_daily_file(subject):
    """Create today’s attendance sheet if missing, with all students marked Absent."""
    prefix = CLASSES[subject]['prefix']
    today  = datetime.date.today().strftime("%Y_%m_%d")
    fn     = os.path.join(REPORTS_DIR, f"{prefix}_{today}.xlsx")
    if not os.path.exists(fn):
        df = load_students(subject).copy()
        df["Status"] = "Absent"
        df["Time"]   = "N/A"
        df.to_excel(fn, index=False)
    return fn

def mark_attendance(subject, sid):
    """Mark a student Present in today’s sheet; return (message, first_time?)."""
    fn = create_daily_file(subject)
    df = pd.read_excel(fn)
    df["Time"] = df["Time"].astype(str)
    mask = df["Student_ID"].astype(str) == str(sid)
    if not mask.any():
        return "Student Unknown", False
    if df.loc[mask, "Status"].iloc[0] == "Present":
        return "Already Present", False
    now = datetime.datetime.now().strftime("%H:%M:%S")
    df.loc[mask, "Status"] = "Present"
    df.loc[mask, "Time"]   = now
    df.to_excel(fn, index=False)
    students_df = load_students(subject)
    name = students_df.loc[students_df["Student_ID"].astype(str)==str(sid), "Name"].iloc[0]
    return f"{name} Marked Present", True

# ── PROFESSOR EMAIL SCHEDULER ─────────────────────────────────────────────────
def check_and_send_reports():
    """Periodic job: after each class window ends, email the sheet if not yet sent."""
    now      = datetime.datetime.now()
    today    = now.date().strftime("%Y_%m_%d")
    today_wd = now.weekday()
    for key, cfg in CLASSES.items():
        if today_wd not in cfg['days']:
            continue
        cutoff = datetime.datetime.combine(now.date(), cfg['start_time']) \
                 + timedelta(minutes=20)
        if not emailed_professor[key] and now > cutoff:
            report_fn = os.path.join(REPORTS_DIR, f"{cfg['prefix']}_{today}.xlsx")
            if os.path.exists(report_fn):
                send_professor_report(key, cfg)
            emailed_professor[key] = True

scheduler = BackgroundScheduler()
scheduler.add_job(check_and_send_reports, 'interval', minutes=1)
scheduler.start()

# ── ROUTES ───────────────────────────────────────────────────────────────────
@app.route('/')
def attendance_page():
    """Render the attendance page, with buttons enabled only during an active window."""
    subj_key, cfg = get_current_class()
    if subj_key:
        st = cfg['start_time'].strftime("%H:%M:%S")
        et = (datetime.datetime.combine(datetime.date.today(), cfg['start_time'])
              + timedelta(minutes=20)).time().strftime("%H:%M:%S")
    else:
        st, et = "", ""
    return render_template(
        'attendance.html',
        active=bool(subj_key),
        subject_name=cfg['name'] if subj_key else "",
        start_time=st,
        end_time=et
    )

@app.route('/register')
def register_page():
    """Render the registration page, active only in the same time window."""
    subj_key, cfg = get_current_class()
    if subj_key:
        st = cfg['start_time'].strftime("%H:%M:%S")
        et = (datetime.datetime.combine(datetime.date.today(), cfg['start_time'])
              + timedelta(minutes=20)).time().strftime("%H:%M:%S")
    else:
        st, et = "", ""
    return render_template(
        'register.html',
        active=bool(subj_key),
        subject_name=cfg['name'] if subj_key else "",
        start_time=st,
        end_time=et
    )

@app.route('/scan_rfid', methods=['POST'])
def scan_rfid():
    """Handle RFID scans: demo or real hardware."""
    subj_key, _ = get_current_class()
    if not subj_key:
        return jsonify(rfid="", message="Attendance closed"), 403

    if DEMO_MODE:
        uid = DEMO_UIDS.get(subj_key, "")
        if uid:
            return jsonify(rfid=uid, message=f"RFID (demo): {uid}")
        return jsonify(rfid="", message="No demo UID configured"), 400

    # Real hardware code would go here:
    # ser.reset_input_buffer()
    # ser.write(b"READ\n")
    # uid = ser.readline().decode().strip()
    # if not uid or uid == "NOTAG":
    #     ser.write(b"Red\n")
    #     return jsonify(rfid="", message="No tag found")
    # return jsonify(rfid=uid, message=f"RFID: {uid}")

@app.route('/capture_face', methods=['POST'])
def capture_face():
    """Capture and register a new student’s face for the given UID."""
    subj_key, cfg = get_current_class()
    if not subj_key:
        return jsonify(message="Registration closed"), 403

    students_df = load_students(subj_key)
    data        = request.get_json(force=True)
    sid         = str(data.get("rfid","")).strip()
    img_str     = data.get("image","")

    if not sid:
        return jsonify(message="RFID missing"), 400
    if sid in students_df["Student_ID"].astype(str).values:
        return jsonify(message="RFID already registered"), 400
    if not img_str.startswith("data:image"):
        return jsonify(message="Image data missing"), 400

    # Decode the base64 image and find the face
    blob  = base64.b64decode(img_str.split(",",1)[1])
    arr   = np.frombuffer(blob, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    locs  = face_recognition.face_locations(frame)
    if not locs:
        return jsonify(message="No face detected")
    encs  = face_recognition.face_encodings(frame, locs)

    # Prevent duplicate face registrations
    existing = []
    for f in os.listdir(FACES_DIR):
        if f.startswith(f"{subj_key}_") and f.endswith(".jpg"):
            img = face_recognition.load_image_file(os.path.join(FACES_DIR, f))
            e   = face_recognition.face_encodings(img)
            if e:
                existing.append(e[0])
    if encs and any(face_recognition.compare_faces(existing, encs[0], tolerance=0.5)):
        return jsonify(message="Face already registered")

    # Save the cropped face image
    top, right, bottom, left = locs[0]
    crop = frame[top:bottom, left:right]
    fn   = os.path.join(FACES_DIR, f"{subj_key}_{sid}.jpg")
    cv2.imwrite(fn, crop)
    return jsonify(message="Face captured")

@app.route('/register_student', methods=['POST'])
def register_student():
    """Save a new student’s details and add them to today’s attendance file."""
    subj_key, cfg = get_current_class()
    if not subj_key:
        return jsonify(message="Registration closed"), 403

    students_df = load_students(subj_key)
    data        = request.get_json(force=True)
    sid   = str(data.get("rfid","")).strip()
    roll  = data.get("roll","").strip()
    name  = data.get("name","").strip()
    email = data.get("email","").strip()

    if not all([sid, roll, name, email]):
        return jsonify(message="All fields required"), 400
    if sid in students_df["Student_ID"].astype(str).values:
        return jsonify(message="RFID already registered"), 400

    # Append to the students sheet
    students_df.loc[len(students_df)] = {
        "Student_ID":  sid,
        "Roll_Number": roll,
        "Name":        name,
        "Email":       email
    }
    save_students(subj_key, students_df)

    # Also add to today’s attendance if it exists
    att_fn = create_daily_file(subj_key)
    att_df = pd.read_excel(att_fn)
    if sid not in att_df["Student_ID"].astype(str).values:
        att_df.loc[len(att_df)] = {
            "Student_ID":  sid,
            "Roll_Number": roll,
            "Name":        name,
            "Email":       email,
            "Status":      "Absent",
            "Time":        "N/A"
        }
        att_df.to_excel(att_fn, index=False)

    send_registration_email(cfg, email, name)
    return jsonify(message=f"{name} registered")

@app.route('/verify_both', methods=['POST'])
def verify_both():
    """Verify RFID + face, then mark attendance and email student."""
    subj_key, cfg = get_current_class()
    if not subj_key:
        return jsonify(message="Attendance closed"), 403

    students_df = load_students(subj_key)
    data        = request.get_json(force=True)
    uid         = str(data.get("rfid","")).strip()
    img_str     = data.get("image","")

    if not uid:
        return jsonify(message="RFID missing"), 400
    # New card → ask to register first
    if uid not in students_df["Student_ID"].astype(str).values:
        return jsonify(message="Student not registered, please register first"), 200
    if not img_str.startswith("data:image"):
        return jsonify(message="Image data missing"), 400

    # Decode and find face
    blob  = base64.b64decode(img_str.split(",",1)[1])
    arr   = np.frombuffer(blob, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    encs  = face_recognition.face_encodings(frame)
    if not encs:
        return jsonify(message="No face detected")

    # Load known faces for this subject
    existing, ids = [], []
    for f in os.listdir(FACES_DIR):
        if f.startswith(f"{subj_key}_") and f.endswith(".jpg"):
            sid2 = f.split("_",1)[1].split(".",1)[0]
            img  = face_recognition.load_image_file(os.path.join(FACES_DIR, f))
            e    = face_recognition.face_encodings(img)
            if e:
                existing.append(e[0])
                ids.append(sid2)

    # Compare face + UID match
    match = face_recognition.compare_faces(existing, encs[0], tolerance=0.5)
    if True not in match:
        return jsonify(message="Face not recognized")
    matched_sid = ids[match.index(True)]
    if matched_sid != uid:
        return jsonify(message="ID & face mismatch")

    # Mark attendance
    result, first = mark_attendance(subj_key, uid)
    if first:
        row = students_df[students_df["Student_ID"].astype(str)==uid].iloc[0]
        send_attendance_email(cfg, row["Email"], row["Name"])

    # Return student info + status
    row = students_df[students_df["Student_ID"].astype(str)==uid].iloc[0]
    return jsonify(
        message=result,
        roll  = row["Roll_Number"],
        name  = row["Name"],
        email = row["Email"],
        time  = datetime.datetime.now().strftime("%H:%M:%S")
    )

if __name__=='__main__':
    # Start the Flask server
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
