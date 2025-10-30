from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os 
import shutil
import sqlite3
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "organizer_secret"

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

def organize_files(directory):
    if not os.path.exists(directory):
        return {"status":"error", "message":"Directory not found."}, {}
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    if not files:
        return {"status":"warning", "message":"No files found to organize."}, {}

    summary = {"images": 0, "documents": 0, "videos": 0, "audio": 0, "archives": 0, "others": 0}
    count = 0
    for file in files:
        ext = file.split(".")[-1].lower() if "." in file else ""
        moved = False
        for folder, extensions in FILE_TYPES.items():
            if ext in extensions:
                folder_path = os.path.join(directory, folder)
                os.makedirs(folder_path, exist_ok=True)
                shutil.move(os.path.join(directory, file), os.path.join(folder_path, file))
                save_to_db(file, folder, folder_path)
                summary[folder] += 1
                count += 1
                moved = True
                break
        if not moved:
            others_path = os.path.join(directory, "others")
            os.makedirs(others_path, exist_ok=True)
            shutil.move(os.path.join(directory, file), os.path.join(others_path, file))
            save_to_db(file, "others", others_path)
            summary["others"] += 1
            count += 1

    pdf_path = generate_pdf_report(directory)
    message = f"{count} files organized. PDF: {pdf_path}"
    return {"status":"ok","message":message,"count":count,"pdf":pdf_path}, summary

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/organize', methods=['POST'])
def organize_route():
    dest_path = request.form.get('path') or request.json.get('path')
    result, summary = organize_files(dest_path)
    # if AJAX JSON request
    if request.is_json:
        return jsonify(result)
    flash(result.get('message'))
    return render_template('success.html', message=result.get('message'), summary=summary)

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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)    #by copying url we can execute in browser
"""
   #without typing after run the code directly execute in browser defaultly
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000/dashboard')
    app.run(debug=True)
"""