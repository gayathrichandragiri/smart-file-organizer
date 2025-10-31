from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import shutil
import sqlite3
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import socket

# ----------------------- Flask Setup -----------------------
app = Flask(__name__)
app.secret_key = "MGForever"

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = 'file_records.db'


# ----------------------- Utility: DB Init -----------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS organized_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    filetype TEXT,
                    new_path TEXT,
                    date TEXT
                )''')
    conn.commit()
    conn.close()


# ----------------------- Utility: Save Record -----------------------
def save_to_db(filename, filetype, new_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO organized_files (filename, filetype, new_path, date) VALUES (?, ?, ?, ?)",
              (filename, filetype, new_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


# ----------------------- Utility: Render Detection -----------------------
def is_running_on_render():
    """Detect if app runs on Render Cloud."""
    hostname = socket.gethostname().lower()
    return "render" in hostname or os.environ.get("RENDER") == "true"


# ----------------------- PDF Report Generator -----------------------
def generate_pdf_report(directory):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename, filetype, new_path, date FROM organized_files WHERE new_path LIKE ?", (f"%{directory}%",))
    rows = c.fetchall()
    conn.close()

    filename = os.path.join(directory, "organization_report.pdf")
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    content = [Paragraph("<b>File Organizer Report</b>", styles['Title']), Spacer(1, 12)]

    for r in rows:
        text = f"<b>{r[0]}</b> ({r[1]}) → {r[2]} <br/> Date: {r[3]}"
        content.append(Paragraph(text, styles['Normal']))
        content.append(Spacer(1, 8))

    doc.build(content)
    return filename


# ----------------------- Core Function: Organize Files -----------------------
def organize_files(target_path=None):
    try:
        # Detect environment
        cloud_mode = is_running_on_render()

        # Decide folder based on environment
        if cloud_mode:
            base_folder = UPLOAD_FOLDER
            mode = "cloud"
        else:
            if target_path and os.path.exists(target_path):
                base_folder = target_path
                mode = "local"
            else:
                base_folder = UPLOAD_FOLDER
                mode = "cloud (fallback)"

        # File categories
        categories = {
            "Images": [".jpg", ".jpeg", ".png", ".gif"],
            "Documents": [".pdf", ".docx", ".txt", ".pptx", ".csv"],
            "Videos": [".mp4", ".mkv", ".mov"],
            "Audio": [".mp3", ".wav"],
            "Archives": [".zip", ".rar"]
        }

        moved_count = 0
        for filename in os.listdir(base_folder):
            filepath = os.path.join(base_folder, filename)
            if not os.path.isfile(filepath):
                continue

            ext = os.path.splitext(filename)[1].lower()
            category_name = next((cat for cat, exts in categories.items() if ext in exts), "Others")

            category_path = os.path.join(base_folder, category_name)
            os.makedirs(category_path, exist_ok=True)

            new_path = os.path.join(category_path, filename)
            shutil.move(filepath, new_path)
            moved_count += 1

            # Save record
            save_to_db(filename, category_name, new_path)

        flash(f"✅ Organized {moved_count} files successfully! (Mode: {mode})")
        return {"moved": moved_count, "mode": mode}

    except Exception as e:
        flash(f"⚠️ Error: {str(e)}")
        return {"error": str(e)}


# ----------------------- Flask Routes -----------------------
@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    files = []
    if os.path.exists(UPLOAD_FOLDER):
        files = os.listdir(UPLOAD_FOLDER)
    return render_template('dashboard.html', files=files, recent_logs=[])


@app.route('/organize', methods=['POST'])
def organize_route():
    data = request.get_json() if request.is_json else request.form
    dest_path = data.get('local_path')

    result = organize_files(dest_path)
    msg = f"Organized {result.get('moved', 0)} files successfully! (Mode: {result.get('mode', 'unknown')})"
    flash(msg)

    if request.is_json:
        return jsonify(result)
    return redirect(url_for("dashboard"))


@app.route('/records')
def records():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM organized_files ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return render_template('records.html', files=rows)


@app.route('/api/summary')
def api_summary():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filetype, COUNT(*) FROM organized_files GROUP BY filetype")
    rows = c.fetchall()
    conn.close()
    data = {r[0]: r[1] for r in rows}
    for k in ['Images', 'Documents', 'Videos', 'Audio', 'Archives', 'Others']:
        data.setdefault(k, 0)
    return jsonify(data)


@app.route('/api/chartdata')
def api_chartdata():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date, COUNT(*) FROM organized_files GROUP BY date ORDER BY date ASC")
    rows = c.fetchall()
    conn.close()
    labels = [r[0].split(' ')[0] for r in rows]
    counts = [r[1] for r in rows]
    return jsonify({'labels': labels, 'counts': counts})


@app.route("/upload", methods=["POST"])
def upload_file():
    if 'files' not in request.files:
        flash("No file part")
        return redirect(request.url)

    files = request.files.getlist("files")
    for file in files:
        if file.filename:
            file.save(os.path.join(UPLOAD_FOLDER, file.filename))

    organize_files(UPLOAD_FOLDER)
    flash("✅ Files uploaded and organized successfully!")
    return redirect(url_for("index"))


# ----------------------- Run App -----------------------
if __name__ == '__main__':
    init_db()
    # Auto-open dashboard when running locally
    if not is_running_on_render():
        import webbrowser
        webbrowser.open('http://127.0.0.1:5000/dashboard')
    app.run(debug=True)
