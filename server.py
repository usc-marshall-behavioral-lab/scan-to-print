#!/usr/bin/env python3
"""
MBRL Scan-to-Print — Local Print Server
Run on the lab Mac: python3 server.py
Access from any device on the lab network: http://<mac-ip>:5050
"""

import os
import io
import subprocess
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import qrcode

app = Flask(__name__)
CORS(app)

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


# ── QR code helper ────────────────────────────────────────────────────────────

def make_qr(data):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


# ── Label generation ──────────────────────────────────────────────────────────

def make_hp_label(sona_id, timestamp):
    """4x6 label, defined as landscape (w=6, h=4) so printer cannot rotate it."""
    path = tempfile.mktemp(suffix=".pdf")

    # Swap w/h so PDF is natively landscape — printer has no choice
    h, w = 6 * inch, 4 * inch   # h=6wide, w=4tall in landscape
    c = rl_canvas.Canvas(path, pagesize=(h, w))

    W, H = h, w   # W = 6in wide, H = 4in tall

    c.setFillColor(colors.white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Cardinal top bar
    c.setFillColorRGB(0.6, 0.0, 0.0)
    c.rect(0, H - 0.22 * inch, W, 0.22 * inch, fill=1, stroke=0)

    # Gold accent line
    c.setFillColorRGB(1.0, 0.80, 0.0)
    c.rect(0, H - 0.255 * inch, W, 0.035 * inch, fill=1, stroke=0)

    # Header text
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, H - 0.158 * inch,
                        "USC MARSHALL  ·  BEHAVIORAL RESEARCH LAB")

    # Column split: left 56%, right 44%
    left_pad  = 0.35 * inch
    divider_x = W * 0.56
    left_cx   = left_pad + (divider_x - left_pad) / 2

    # PARTICIPANT ID label
    c.setFillColorRGB(0.50, 0.45, 0.40)
    c.setFont("Helvetica", 10)
    c.drawCentredString(left_cx, H - 0.62 * inch, "PARTICIPANT ID")

    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.setLineWidth(0.5)
    c.line(left_pad, H - 0.72 * inch, divider_x - 0.15 * inch, H - 0.72 * inch)

    # Auto-fit SONA ID to available width
    avail_w = divider_x - left_pad - 0.2 * inch
    for fs in range(80, 30, -2):
        c.setFont("Helvetica-Bold", fs)
        if c.stringWidth(sona_id, "Helvetica-Bold", fs) <= avail_w:
            break

    c.setFillColorRGB(0.11, 0.08, 0.04)
    c.drawCentredString(left_cx, H - 1.82 * inch, sona_id)

    # Instruction box
    box_y = 0.68 * inch
    box_h = 0.66 * inch
    box_w = divider_x - left_pad - 0.1 * inch
    c.setFillColorRGB(1.0, 0.97, 0.88)
    c.setStrokeColorRGB(1.0, 0.80, 0.0)
    c.setLineWidth(0.6)
    c.roundRect(left_pad, box_y, box_w, box_h, 3, fill=1, stroke=1)

    line_h = 0.135 * inch
    top_y  = box_y + box_h - 0.13 * inch

    c.setFillColorRGB(0.25, 0.18, 0.08)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(left_cx, top_y,
        "Enter this number when prompted during your study.")

    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.40, 0.32, 0.18)
    c.drawCentredString(left_cx, top_y - line_h,
        "May appear as: SONA ID, Participant ID, Subject ID, or User ID")

    # Divider inside box
    c.setStrokeColorRGB(1.0, 0.80, 0.0)
    c.setLineWidth(0.4)
    c.line(left_pad + 0.1 * inch, top_y - line_h * 1.55,
           left_pad + box_w - 0.1 * inch, top_y - line_h * 1.55)

    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColorRGB(0.6, 0.0, 0.0)
    c.drawCentredString(left_cx, top_y - line_h * 2.1,
        "Keep this label — your researcher will collect it")
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.40, 0.32, 0.18)
    c.drawCentredString(left_cx, top_y - line_h * 3.1,
        "from you upon completion to grant your credit (by next day).")

    # Vertical divider
    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.setLineWidth(0.5)
    c.line(divider_x, H - 0.38 * inch, divider_x, 0.50 * inch)

    # Right column: QR code
    right_w = W - divider_x
    qr_size = 1.85 * inch
    qr_x    = divider_x + (right_w - qr_size) / 2
    qr_y    = H - 0.40 * inch - qr_size
    c.drawImage(make_qr(sona_id), qr_x, qr_y,
                width=qr_size, height=qr_size, preserveAspectRatio=True)

    c.setFillColorRGB(0.65, 0.60, 0.55)
    c.setFont("Helvetica", 7)
    c.drawCentredString(divider_x + right_w / 2, qr_y - 0.14 * inch,
                        "Scan to verify")

    # Bottom timestamp
    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.line(0.3 * inch, 0.48 * inch, W - 0.3 * inch, 0.48 * inch)
    c.setFillColorRGB(0.65, 0.60, 0.55)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(W / 2, 0.27 * inch, timestamp)

    c.save()
    return path


def make_dymo_label(sona_id, timestamp):
    """3.5x1.12 Dymo 30252 label with small QR code."""
    path = tempfile.mktemp(suffix=".pdf")
    w, h = 3.5 * inch, 1.12 * inch
    c = rl_canvas.Canvas(path, pagesize=(w, h))

    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    c.setFillColorRGB(0.6, 0.0, 0.0)
    c.rect(0, 0, 0.07 * inch, h, fill=1, stroke=0)

    c.setFillColorRGB(0.50, 0.45, 0.40)
    c.setFont("Helvetica", 6)
    c.drawString(0.16 * inch, h - 0.18 * inch, "MBRL  ·  PARTICIPANT ID")

    avail_w = w * 0.62
    for fs in range(34, 14, -2):
        c.setFont("Helvetica-Bold", fs)
        if c.stringWidth(sona_id, "Helvetica-Bold", fs) <= avail_w:
            break

    c.setFillColorRGB(0.05, 0.09, 0.14)
    c.drawString(0.16 * inch, 0.25 * inch, sona_id)

    qr_size = 0.80 * inch
    c.drawImage(make_qr(sona_id),
                w - qr_size - 0.08 * inch, (h - qr_size) / 2,
                width=qr_size, height=qr_size, preserveAspectRatio=True)

    c.setFillColorRGB(0.65, 0.60, 0.55)
    c.setFont("Helvetica", 5)
    c.drawString(0.16 * inch, 0.08 * inch, timestamp)

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
    data    = request.get_json()
    sona_id = (data.get("sona_id") or "").strip()

    if not sona_id:
        return jsonify({"ok": False, "error": "No SONA ID provided"}), 400

    name, ptype = detect_printer()
    if not name:
        return jsonify({"ok": False, "error": "No printer found"}), 503

    ts       = datetime.now().strftime("%b %d, %Y  ·  %I:%M %p")
    pdf_path = (make_dymo_label(sona_id, ts)
                if ptype == "dymo" else make_hp_label(sona_id, ts))

    try:
        result = subprocess.run(
            ["lp", "-d", name,
             "-o", "media=4x6",
             "-o", "orientation-requested=4",
             pdf_path],
            capture_output=True, text=True, timeout=10
        )
        success = result.returncode == 0
    except Exception:
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
