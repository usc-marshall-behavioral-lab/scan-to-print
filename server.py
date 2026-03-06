#!/usr/bin/env python3
"""
MBRL Scan-to-Print — Local Print Server
Serves the webapp and handles print jobs.
Run on the lab Mac: python3 server.py
Access from any device on the lab network: http://<mac-ip>:5050
"""

import os
import subprocess
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors

app = Flask(__name__)
CORS(app, origins=['https://usc-marshall-behavioral-lab.github.io', 'http://localhost:5050', 'http://127.0.0.1:5050'])

HP_KEYWORDS   = ["ke203", "hp", "direct thermal"]
DYMO_KEYWORDS = ["dymo", "labelwriter"]


# ── Printer detection ─────────────────────────────────────────────────────────

def get_printers():
    try:
        result = subprocess.run(
            ["lpstat", "-a"], capture_output=True, text=True, timeout=4
        )
        return [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def detect_printer():
    printers = get_printers()
    for p in printers:
        if any(k in p.lower() for k in HP_KEYWORDS):
            return p, "hp"
    for p in printers:
        if any(k in p.lower() for k in DYMO_KEYWORDS):
            return p, "dymo"
    if printers:
        return printers[0], "hp"
    return None, None


# ── Label generation ──────────────────────────────────────────────────────────

def make_hp_label(sona_id, timestamp):
    path = tempfile.mktemp(suffix=".pdf")
    w, h = 6 * inch, 4 * inch
    c = rl_canvas.Canvas(path, pagesize=(w, h))

    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Top accent bar (USC Cardinal)
    c.setFillColorRGB(0.600, 0.000, 0.000)
    c.rect(0, h - 0.18 * inch, w, 0.18 * inch, fill=1, stroke=0)

    # Header
    c.setFillColorRGB(0.40, 0.40, 0.40)
    c.setFont("Helvetica", 11)
    c.drawCentredString(w / 2, h - 0.52 * inch, "MARSHALL BEHAVIORAL RESEARCH LAB")

    # Divider
    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.setLineWidth(0.5)
    c.line(0.4 * inch, h - 0.68 * inch, w - 0.4 * inch, h - 0.68 * inch)

    # Subheader
    c.setFillColorRGB(0.55, 0.60, 0.70)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 1.05 * inch, "PARTICIPANT ID")

    # SONA ID
    c.setFillColorRGB(0.05, 0.09, 0.14)
    font_size = 96 if len(sona_id) <= 6 else 72
    c.setFont("Helvetica-Bold", font_size)
    c.drawCentredString(w / 2, h - 2.45 * inch, sona_id)

    # Bottom divider + timestamp
    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.line(0.4 * inch, 0.55 * inch, w - 0.4 * inch, 0.55 * inch)
    c.setFillColorRGB(0.65, 0.68, 0.75)
    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, 0.3 * inch, timestamp)

    c.save()
    return path


def make_dymo_label(sona_id, timestamp):
    path = tempfile.mktemp(suffix=".pdf")
    w, h = 3.5 * inch, 1.12 * inch
    c = rl_canvas.Canvas(path, pagesize=(w, h))

    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    c.setFillColorRGB(0.600, 0.000, 0.000)
    c.rect(0, 0, 0.07 * inch, h, fill=1, stroke=0)

    c.setFillColorRGB(0.55, 0.60, 0.70)
    c.setFont("Helvetica", 6)
    c.drawString(0.16 * inch, h - 0.18 * inch, "MBRL  ·  PARTICIPANT ID")

    c.setFillColorRGB(0.05, 0.09, 0.14)
    font_size = 36 if len(sona_id) <= 6 else 28
    c.setFont("Helvetica-Bold", font_size)
    c.drawString(0.16 * inch, 0.28 * inch, sona_id)

    c.setFillColorRGB(0.65, 0.68, 0.75)
    c.setFont("Helvetica", 5)
    c.drawRightString(w - 0.08 * inch, 0.08 * inch, timestamp)

    c.save()
    return path


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    name, ptype = detect_printer()
    if name:
        label = "HP KE203" if ptype == "hp" else "Dymo LabelWriter"
        return jsonify({"ok": True, "printer": name, "type": ptype, "label": label})
    return jsonify({"ok": False, "printer": None, "label": "No printer detected"})


@app.route("/api/print", methods=["POST"])
def print_label():
    data = request.get_json()
    sona_id = (data.get("sona_id") or "").strip()

    if not sona_id:
        return jsonify({"ok": False, "error": "No SONA ID provided"}), 400

    name, ptype = detect_printer()
    if not name:
        return jsonify({"ok": False, "error": "No printer found"}), 503

    ts = datetime.now().strftime("%b %d, %Y  ·  %I:%M %p")
    pdf_path = make_dymo_label(sona_id, ts) if ptype == "dymo" else make_hp_label(sona_id, ts)

    try:
        result = subprocess.run(
            ["lp", "-d", name, pdf_path],
            capture_output=True, text=True, timeout=10
        )
        success = result.returncode == 0
    except Exception as e:
        success = False
    finally:
        try:
            os.unlink(pdf_path)
        except Exception:
            pass

    if success:
        return jsonify({"ok": True, "sona_id": sona_id, "printer": name})
    else:
        return jsonify({"ok": False, "error": "Print command failed"}), 500


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "unknown"

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  MBRL Scan-to-Print  ·  Print Server")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Local:    http://localhost:5050")
    print(f"  Network:  http://{local_ip}:5050")
    print("  Open either URL in any browser on the lab network")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
