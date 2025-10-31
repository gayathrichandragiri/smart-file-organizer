from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import shutil
import sqlite3
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "MGForever"

DB_PATH = 'file_records.db'

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

FILE_TYPES = {
    "images": ["jpg", "jpeg", "png", "gif"],
    "documents": ["pdf", "docx", "txt", "csv", "pptx"],
    "videos": ["mp4", "mkv", "mov"],
    "audio": ["mp3", "wav"],
    "archives": ["zip", "rar"],
}

def save_to_db(filename, filetype, new_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO organized_files (filename, filetype, new_path, date) VALUES (?, ?, ?, ?)",
              (filename, filetype, new_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

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

def organize_files(target_path=None):
    try:
        # Detect if path exists (local mode)
        if target_path and os.path.exists(target_path):
            base_folder = target_path
            mode = "local"
        else:
            # Cloud/Render mode → use uploads folder
            base_folder = UPLOAD_FOLDER
            mode = "cloud"

        # Create categorized folders
        categories = {
            "Images": [".jpg", ".jpeg", ".png", ".gif"],
            "Documents": [".pdf", ".docx", ".txt", ".pptx"],
            "Videos": [".mp4", ".mkv"],
            "Audio": [".mp3", ".wav"],
            "Archives": [".zip", ".rar"]
        }

        moved_count = 0
        for filename in os.listdir(base_folder):
            filepath = os.path.join(base_folder, filename)
            if not os.path.isfile(filepath):
                continue

            ext = os.path.splitext(filename)[1].lower()
            for category, exts in categories.items():
                if ext in exts:
                    category_path = os.path.join(base_folder, category)
                    os.makedirs(category_path, exist_ok=True)
                    shutil.move(filepath, os.path.join(category_path, filename))
                    moved_count += 1
                    break

        flash(f"✅ Organized {moved_count} files successfully! (Mode: {mode})")
        return {"moved": moved_count, "mode": mode}

    except Exception as e:
        flash(f"⚠️ Error: {str(e)}")
        return {"error": str(e)}
    
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', files=os.listdir(UPLOAD_FOLDER), recent_logs=[])


@app.route('/organize', methods=['POST'])
def organize_route():
    dest_path = request.form.get('local_path') or request.json.get('local_path')
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
    # ensure all keys present
    for k in ['images','documents','videos','audio','archives','others']:
        data.setdefault(k,0)
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

    # Automatically organize uploaded files in cloud mode
    organize_files(UPLOAD_FOLDER)
    flash("✅ Files uploaded and organized successfully!")
    return redirect(url_for("index"))




if __name__ == '__main__':
    init_db()
    app.run(debug=True)    #by copying url we can execute in browser
"""
   #without typing after run the code directly execute in browser defaultly
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000/dashboard')
    app.run(debug=True)
"""