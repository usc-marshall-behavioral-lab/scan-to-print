#!/usr/bin/env python3
"""
MBRL Scan-to-Print — Local Print Server
Run on the lab Mac: python3 server.py
Access from any device on the lab network: http://<mac-ip>:5050
"""

import os
import io
import csv
import smtplib
import subprocess
import tempfile
import urllib.request
import urllib.parse
import ssl
import ssl
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import qrcode

# ── Config (optional — gracefully disabled if config.py not found) ────────────
CFG = {}
try:
    import config as _cfg
    CFG = {k: v for k, v in vars(_cfg).items() if not k.startswith("_")}
    print("  Config: \u2713 loaded")
except ImportError:
    print("  Config: \u2717 config.py not found — email/SONA disabled. Copy config.example.py to config.py to enable.")

def cfg(key, default=None):
    return CFG.get(key, default)

app = Flask(__name__)
CORS(app)

HP_KEYWORDS   = ["ke203", "direct thermal"]
DYMO_KEYWORDS = ["dymo", "labelwriter"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = cfg("CSV_LOG_PATH", os.path.join(BASE_DIR, "checkout_log.csv"))


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
    qr = qrcode.QRCode(version=None,
                       error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


# ── Label generation ──────────────────────────────────────────────────────────

def make_hp_label(sona_id, timestamp, experiment=""):
    """4x6 landscape check-in label for HP KE203."""
    path = tempfile.mktemp(suffix=".pdf")
    h, w = 6 * inch, 4 * inch
    c = rl_canvas.Canvas(path, pagesize=(h, w))
    W, H = h, w

    c.setFillColor(colors.white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    c.setFillColorRGB(0.6, 0.0, 0.0)
    c.rect(0, H - 0.22 * inch, W, 0.22 * inch, fill=1, stroke=0)
    c.setFillColorRGB(1.0, 0.80, 0.0)
    c.rect(0, H - 0.255 * inch, W, 0.035 * inch, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, H - 0.158 * inch,
                        "USC MARSHALL  \u00b7  BEHAVIORAL RESEARCH LAB")

    left_pad  = 0.35 * inch
    divider_x = W * 0.56
    left_cx   = left_pad + (divider_x - left_pad) / 2

    c.setFillColorRGB(0.50, 0.45, 0.40)
    c.setFont("Helvetica", 10)
    c.drawCentredString(left_cx, H - 0.62 * inch, "PARTICIPANT ID")
    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.setLineWidth(0.5)
    c.line(left_pad, H - 0.72 * inch, divider_x - 0.15 * inch, H - 0.72 * inch)

    avail_w = divider_x - left_pad - 0.2 * inch
    for fs in range(80, 30, -2):
        c.setFont("Helvetica-Bold", fs)
        if c.stringWidth(sona_id, "Helvetica-Bold", fs) <= avail_w:
            break
    c.setFillColorRGB(0.11, 0.08, 0.04)
    c.drawCentredString(left_cx, H - 1.82 * inch, sona_id)

    if experiment:
        c.setFillColorRGB(0.50, 0.45, 0.40)
        c.setFont("Helvetica", 8)
        # Truncate if too wide
        exp_display = experiment
        while exp_display and c.stringWidth(exp_display, "Helvetica", 8) > avail_w:
            exp_display = exp_display[:-1]
        if exp_display != experiment:
            exp_display = exp_display[:-1] + "…"
        c.drawCentredString(left_cx, H - 2.10 * inch, exp_display)

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
    c.setStrokeColorRGB(1.0, 0.80, 0.0)
    c.setLineWidth(0.4)
    c.line(left_pad + 0.1 * inch, top_y - line_h * 1.55,
           left_pad + box_w - 0.1 * inch, top_y - line_h * 1.55)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColorRGB(0.6, 0.0, 0.0)
    c.drawCentredString(left_cx, top_y - line_h * 2.1,
        "Keep this label \u2014 your researcher will collect it")
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.40, 0.32, 0.18)
    c.drawCentredString(left_cx, top_y - line_h * 3.1,
        "from you upon completion to grant your credit (by next day).")

    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.setLineWidth(0.5)
    c.line(divider_x, H - 0.38 * inch, divider_x, 0.50 * inch)

    right_w = W - divider_x
    qr_size = 1.85 * inch
    qr_x    = divider_x + (right_w - qr_size) / 2
    qr_y    = H - 0.40 * inch - qr_size
    c.drawImage(make_qr(sona_id), qr_x, qr_y,
                width=qr_size, height=qr_size, preserveAspectRatio=True)
    c.setFillColorRGB(0.65, 0.60, 0.55)
    c.setFont("Helvetica", 7)
    c.drawCentredString(divider_x + right_w / 2, qr_y - 0.14 * inch, "Scan to verify")

    c.setStrokeColorRGB(0.88, 0.88, 0.88)
    c.line(0.3 * inch, 0.48 * inch, W - 0.3 * inch, 0.48 * inch)
    c.setFillColorRGB(0.65, 0.60, 0.55)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(W / 2, 0.27 * inch, timestamp)

    c.save()
    return path


def make_dymo_label(sona_id, timestamp):
    """3.5x1.125 Dymo label. PDF defined as portrait (1.125 x 3.5) with
    content rotated 90 deg CCW so CUPS prints correctly without orientation flags."""
    path = tempfile.mktemp(suffix=".pdf")
    PW, PH = 1.125 * inch, 3.5 * inch
    c = rl_canvas.Canvas(path, pagesize=(PW, PH))

    # Rotate canvas so drawing space becomes W=3.5", H=1.125"
    c.translate(0, PH)
    c.rotate(-90)
    W, H = 3.5 * inch, 1.125 * inch

    c.setFillColor(colors.white)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColorRGB(0.6, 0.0, 0.0)
    c.rect(0, 0, 0.07 * inch, H, fill=1, stroke=0)
    c.setFillColorRGB(0.50, 0.45, 0.40)
    c.setFont("Helvetica", 6)
    c.drawString(0.16 * inch, H - 0.18 * inch, "MBRL  ·  PARTICIPANT ID")

    avail_w = W * 0.55
    for fs in range(34, 14, -2):
        c.setFont("Helvetica-Bold", fs)
        if c.stringWidth(sona_id, "Helvetica-Bold", fs) <= avail_w:
            break
    c.setFillColorRGB(0.05, 0.09, 0.14)
    c.drawString(0.16 * inch, 0.25 * inch, sona_id)

    qr_size = 0.85 * inch
    c.drawImage(make_qr(sona_id),
                W - qr_size - 0.06 * inch, (H - qr_size) / 2,
                width=qr_size, height=qr_size, preserveAspectRatio=True)
    c.setFillColorRGB(0.65, 0.60, 0.55)
    c.setFont("Helvetica", 5)
    c.drawString(0.16 * inch, 0.08 * inch, timestamp)

    c.save()
    return path

def make_checkout_receipt(sona_id, experiment, timestamp, ptype):
    """Checkout receipt — same size as check-in label."""
    path = tempfile.mktemp(suffix=".pdf")

    if ptype == "dymo":
        PW, PH = 1.125 * inch, 3.5 * inch
        c = rl_canvas.Canvas(path, pagesize=(PW, PH))
        c.translate(0, PH)
        c.rotate(-90)
        w, h = 3.5 * inch, 1.125 * inch
        c.setFillColor(colors.white)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColorRGB(0.17, 0.48, 0.27)
        c.rect(0, 0, 0.07 * inch, h, fill=1, stroke=0)
        c.setFillColorRGB(0.17, 0.48, 0.27)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(0.16 * inch, h - 0.18 * inch, "MBRL  \u00b7  CHECKED OUT")

        avail_w = w * 0.55
        for fs in range(34, 14, -2):
            c.setFont("Helvetica-Bold", fs)
            if c.stringWidth(sona_id, "Helvetica-Bold", fs) <= avail_w:
                break
        c.setFillColorRGB(0.05, 0.09, 0.14)
        c.drawString(0.16 * inch, 0.25 * inch, sona_id)

        if experiment:
            c.setFillColorRGB(0.50, 0.45, 0.40)
            c.setFont("Helvetica", 5.5)
            c.drawRightString(w - 0.10 * inch, h - 0.18 * inch, experiment[:20])

        c.setFillColorRGB(0.65, 0.60, 0.55)
        c.setFont("Helvetica", 5)
        c.drawString(0.16 * inch, 0.08 * inch, timestamp)

    else:
        h, w = 6 * inch, 4 * inch
        c = rl_canvas.Canvas(path, pagesize=(h, w))
        W, H = h, w

        c.setFillColor(colors.white)
        c.rect(0, 0, W, H, fill=1, stroke=0)

        c.setFillColorRGB(0.17, 0.48, 0.27)
        c.rect(0, H - 0.22 * inch, W, 0.22 * inch, fill=1, stroke=0)
        c.setFillColorRGB(1.0, 0.80, 0.0)
        c.rect(0, H - 0.255 * inch, W, 0.035 * inch, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(W / 2, H - 0.158 * inch,
                            "USC MARSHALL  \u00b7  BEHAVIORAL RESEARCH LAB")

        left_pad  = 0.35 * inch
        divider_x = W * 0.56
        left_cx   = left_pad + (divider_x - left_pad) / 2

        c.setFillColorRGB(0.17, 0.48, 0.27)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(left_cx, H - 0.60 * inch, "CHECKED OUT")

        c.setStrokeColorRGB(0.88, 0.88, 0.88)
        c.setLineWidth(0.5)
        c.line(left_pad, H - 0.72 * inch, divider_x - 0.15 * inch, H - 0.72 * inch)

        avail_w = divider_x - left_pad - 0.2 * inch
        for fs in range(80, 30, -2):
            c.setFont("Helvetica-Bold", fs)
            if c.stringWidth(sona_id, "Helvetica-Bold", fs) <= avail_w:
                break
        c.setFillColorRGB(0.11, 0.08, 0.04)
        c.drawCentredString(left_cx, H - 1.82 * inch, sona_id)

        if experiment:
            c.setFillColorRGB(0.50, 0.45, 0.40)
            c.setFont("Helvetica", 9)
            c.drawCentredString(left_cx, H - 2.15 * inch, experiment)

        box_y = 0.68 * inch
        box_h = 0.50 * inch
        box_w = divider_x - left_pad - 0.1 * inch
        c.setFillColorRGB(0.93, 0.98, 0.94)
        c.setStrokeColorRGB(0.17, 0.48, 0.27)
        c.setLineWidth(0.6)
        c.roundRect(left_pad, box_y, box_w, box_h, 3, fill=1, stroke=1)
        c.setFillColorRGB(0.10, 0.35, 0.18)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(left_cx, box_y + box_h - 0.16 * inch,
            "Session complete. Credit will be granted by next business day.")
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(left_cx, box_y + 0.14 * inch,
            "Thank you for participating!")

        c.setStrokeColorRGB(0.88, 0.88, 0.88)
        c.setLineWidth(0.5)
        c.line(divider_x, H - 0.38 * inch, divider_x, 0.50 * inch)

        right_w = W - divider_x
        qr_size = 1.85 * inch
        qr_x    = divider_x + (right_w - qr_size) / 2
        qr_y    = H - 0.40 * inch - qr_size
        c.drawImage(make_qr(sona_id), qr_x, qr_y,
                    width=qr_size, height=qr_size, preserveAspectRatio=True)
        c.setFillColorRGB(0.65, 0.60, 0.55)
        c.setFont("Helvetica", 7)
        c.drawCentredString(divider_x + right_w / 2, qr_y - 0.14 * inch, "Checkout confirmed")

        c.setStrokeColorRGB(0.88, 0.88, 0.88)
        c.line(0.3 * inch, 0.48 * inch, W - 0.3 * inch, 0.48 * inch)
        c.setFillColorRGB(0.65, 0.60, 0.55)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(W / 2, 0.27 * inch, timestamp)

    c.save()
    return path


# ── CSV logging ───────────────────────────────────────────────────────────────

def log_checkout_csv(sona_id, experiment, ra_email, timestamp_str):
    try:
        file_exists = os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "SONA ID", "Experiment", "RA Email", "Date", "Time"])
            now = datetime.now()
            writer.writerow([
                now.strftime("%Y-%m-%d %H:%M:%S"),
                sona_id,
                experiment or "",
                ra_email or "",
                now.strftime("%b %d, %Y"),
                now.strftime("%I:%M %p"),
            ])
        return True
    except Exception as e:
        print(f"  CSV log error: {e}")
        return False


# ── SONA API ──────────────────────────────────────────────────────────────────
# Uses the official Sona Systems REST API (api_key auth, User-Agent required).
# Base URL: https://{domain}.sona-systems.com/services/SonaAPI.svc/

SONA_USER_AGENT = "MBRL-ScanToPrint/2025"

def _sona_get(path, params):
    """Make an authenticated GET request to the SONA API."""
    domain  = cfg("SONA_DOMAIN")
    api_key = cfg("SONA_API_TOKEN")
    params["api_key"] = api_key
    url = f"https://{domain}.sona-systems.com/services/SonaAPI.svc/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": SONA_USER_AGENT})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        return resp.read().decode()


def _sona_find_signup_id(sona_id, experiment_id):
    """
    Look up the signup_id for a participant in a given experiment.
    Strategy:
      1. Get all timeslots with signups for the experiment (fill_status=S).
      2. For each timeslot, fetch signups and match anon_id_code to sona_id.
      3. Return the first matching signup_id.
    """
    import xml.etree.ElementTree as ET

    # Step 1 — get timeslots that have at least one signup
    xml_ts = _sona_get("SonaGetTimeslotsByExperimentID", {
        "experiment_id": experiment_id,
        "fill_status":   "S",
    })
    root = ET.fromstring(xml_ts)
    ns   = {"a": "http://schemas.datacontract.org/2004/07/emsdotnet.sonasystems"}

    timeslot_ids = []
    for ts in root.iter("{http://schemas.datacontract.org/2004/07/emsdotnet.sonasystems}timeslot_id"):
        tid = ts.text
        if tid:
            timeslot_ids.append(tid)

    if not timeslot_ids:
        return None, "No timeslots with signups found for that experiment ID"

    # Step 2 — search each timeslot's signups for this participant's anon_id_code
    for tid in timeslot_ids:
        try:
            xml_su = _sona_get("SonaGetSignUpsForTimeslot", {"timeslot_id": tid})
            su_root = ET.fromstring(xml_su)
            for signup in su_root.iter("{http://schemas.datacontract.org/2004/07/emsdotnet.sonasystems}APISignUp"):
                anon = signup.find("{http://schemas.datacontract.org/2004/07/emsdotnet.sonasystems}anon_id_code")
                sid  = signup.find("{http://schemas.datacontract.org/2004/07/emsdotnet.sonasystems}signup_id")
                if anon is not None and anon.text and anon.text.strip() == sona_id.strip():
                    return sid.text.strip(), None
        except Exception:
            continue  # try next timeslot

    return None, f"No signup found for participant {sona_id} in experiment {experiment_id}"


def sona_grant_credit(sona_id, experiment_id):
    """
    Full credit-grant flow:
      1. Find the signup_id for this participant + experiment.
      2. Call SonaGrantCreditBySignupID.
    """
    domain  = cfg("SONA_DOMAIN")
    api_key = cfg("SONA_API_TOKEN")

    if not domain or not api_key or api_key == "YOUR_SONA_API_TOKEN_HERE":
        return False, "SONA not configured"
    if not experiment_id:
        return False, "No experiment ID provided"

    try:
        signup_id, err = _sona_find_signup_id(sona_id, experiment_id)
        if not signup_id:
            return False, err or "Signup not found"

        xml_result = _sona_get("SonaGrantCreditBySignupID", {
            "signup_id":         signup_id,
            "credit_type":       "G",
            "credits":           "-1",       # use study's default credit value
            "comments":          "Granted via MBRL Scan-to-Print at checkout",
            "skip_credit_email": "false",    # send participant the credit email
        })

        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_result)
        result_el = root.find(".//{http://schemas.datacontract.org/2004/07/emsdotnet.sonasystems}Result")
        if result_el is not None and result_el.text == "true":
            return True, f"Credit granted (signup {signup_id})"
        elif result_el is not None and result_el.text == "false":
            return True, f"Already granted (signup {signup_id})"
        return False, f"Unexpected response: {xml_result[:200]}"

    except Exception as e:
        return False, str(e)


# ── Email notification ────────────────────────────────────────────────────────

def send_checkout_email(sona_id, experiment, ra_email, timestamp_str, sona_ok, sona_msg):
    smtp_host  = cfg("EMAIL_SMTP_HOST")
    smtp_port  = cfg("EMAIL_SMTP_PORT", 587)
    email_addr = cfg("EMAIL_ADDRESS")
    email_pass = cfg("EMAIL_PASSWORD")
    lab_mgr    = cfg("EMAIL_LAB_MANAGER", "")

    if not smtp_host or not email_addr or not email_pass \
       or email_pass == "YOUR_APP_PASSWORD_HERE":
        return False, "Email not configured"

    recipients = [r for r in [lab_mgr, ra_email] if r and "@" in r]
    if not recipients:
        return False, "No recipients"

    sona_status = "Granted automatically" if sona_ok else f"Manual grant needed ({sona_msg})"

    body = f"""MBRL Scan-to-Print — Checkout Notification

Participant checked out at {timestamp_str}

  SONA ID:     {sona_id}
  Experiment:  {experiment or '(not specified)'}
  RA:          {ra_email or '(not specified)'}
  SONA Credit: {sona_status}

--
Marshall Behavioral Research Lab
behaviorallab@marshall.usc.edu
"""

    try:
        msg = MIMEMultipart()
        msg["From"]    = email_addr
        msg["To"]      = ", ".join(recipients)
        msg["Subject"] = f"MBRL Checkout -- Participant {sona_id}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(email_addr, email_pass)
            server.sendmail(email_addr, recipients, msg.as_string())
        return True, "Sent"
    except Exception as e:
        return False, str(e)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    name, ptype = detect_printer()
    has_sona  = bool(cfg("SONA_DOMAIN") and cfg("SONA_API_TOKEN")
                     and cfg("SONA_API_TOKEN") != "YOUR_SONA_API_TOKEN_HERE")
    has_email = bool(cfg("EMAIL_ADDRESS") and cfg("EMAIL_PASSWORD")
                     and cfg("EMAIL_PASSWORD") != "YOUR_APP_PASSWORD_HERE")
    if name:
        label = "HP KE203" if ptype == "hp" else "Dymo LabelWriter"
        return jsonify({"ok": True, "printer": name, "type": ptype, "label": label,
                        "sona": has_sona, "email": has_email})
    return jsonify({"ok": False, "printer": None, "label": "No printer detected",
                    "sona": has_sona, "email": has_email})



@app.route("/api/studies")
def get_studies():
    """Fetch active approved studies from SONA and return as JSON list."""
    domain  = cfg("SONA_DOMAIN")
    api_key = cfg("SONA_API_TOKEN")
    if not domain or not api_key or api_key == "YOUR_SONA_API_TOKEN_HERE":
        return jsonify({"ok": False, "error": "SONA not configured", "studies": []})
    try:
        import xml.etree.ElementTree as ET
        xml_data = _sona_get("SonaGetStudyList", {"active": "1", "approved": "1", "web_flag": "0", "survey_flag": "0"})
        root = ET.fromstring(xml_data)
        ns   = "http://schemas.datacontract.org/2004/07/emsdotnet.sonasystems"
        studies = []
        for study in root.iter(f"{{{ns}}}APIStudyInfo"):
            exp_id = study.find(f"{{{ns}}}experiment_id")
            name   = study.find(f"{{{ns}}}study_name")
            if exp_id is not None and name is not None:
                studies.append({
                    "id":   exp_id.text.strip(),
                    "name": name.text.strip() if name.text else "(unnamed)",
                })
        studies.sort(key=lambda s: s["name"].lower())
        return jsonify({"ok": True, "studies": studies})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "studies": []})

@app.route("/api/verify", methods=["POST"])
def verify_signup():
    """Check if a participant has a signup for the given experiment."""
    data        = request.get_json()
    sona_id     = (data.get("sona_id")  or "").strip()
    exp_id      = (data.get("exp_id")   or "").strip()

    if not sona_id or not exp_id:
        return jsonify({"ok": False, "error": "Missing sona_id or exp_id"})

    domain  = cfg("SONA_DOMAIN")
    api_key = cfg("SONA_API_TOKEN")
    if not domain or not api_key or api_key == "YOUR_SONA_API_TOKEN_HERE":
        return jsonify({"ok": None, "msg": "SONA not configured — skipping verification"})

    try:
        signup_id, err = _sona_find_signup_id(sona_id, exp_id)
        if signup_id:
            return jsonify({"ok": True, "signup_id": signup_id,
                            "msg": f"Confirmed — signup {signup_id} found"})
        else:
            return jsonify({"ok": False, "msg": err or "No signup found"})
    except Exception as e:
        return jsonify({"ok": None, "msg": f"Verification error: {e}"})

@app.route("/api/print", methods=["POST"])
def print_label():
    data       = request.get_json()
    sona_id    = (data.get("sona_id")    or "").strip()
    experiment = (data.get("experiment") or "").strip()

    if not sona_id:
        return jsonify({"ok": False, "error": "No SONA ID provided"}), 400

    name, ptype = detect_printer()
    if not name:
        return jsonify({"ok": False, "error": "No printer found"}), 503

    ts       = datetime.now().strftime("%b %d, %Y  \u00b7  %I:%M %p")
    pdf_path = make_dymo_label(sona_id, ts) if ptype == "dymo" else make_hp_label(sona_id, ts, experiment)

    try:
        if ptype == "dymo":
            cmd = ["lp", "-d", name, pdf_path]
        else:
            cmd = ["lp", "-d", name, "-o", "media=4x6",
                   "-o", "orientation-requested=4", pdf_path]
        result  = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        success = result.returncode == 0
    except Exception:
        success = False
    finally:
        try: os.unlink(pdf_path)
        except: pass

    if success:
        return jsonify({"ok": True, "sona_id": sona_id, "printer": name})
    return jsonify({"ok": False, "error": "Print command failed"}), 500


@app.route("/api/checkout", methods=["POST"])
def checkout():
    data       = request.get_json()
    sona_id    = (data.get("sona_id")    or "").strip()
    experiment = (data.get("experiment") or "").strip()
    ra_email   = (data.get("ra_email")   or "").strip()
    exp_id     = (data.get("exp_id")     or "").strip()

    if not sona_id:
        return jsonify({"ok": False, "error": "No SONA ID provided"}), 400

    name, ptype = detect_printer()
    ts = datetime.now().strftime("%b %d, %Y  \u00b7  %I:%M %p")
    result = {"ok": True, "sona_id": sona_id, "steps": {}}

    # 1 — CSV log
    csv_ok = log_checkout_csv(sona_id, experiment, ra_email, ts)
    result["steps"]["csv"] = "logged" if csv_ok else "failed"

    # 2 — SONA credit
    sona_ok, sona_msg = sona_grant_credit(sona_id, exp_id)
    result["steps"]["sona"] = sona_msg

    # 3 — Email
    email_ok, email_msg = send_checkout_email(
        sona_id, experiment, ra_email, ts, sona_ok, sona_msg)
    result["steps"]["email"] = email_msg

    # 4 — Print receipt
    if name:
        pdf_path = make_checkout_receipt(sona_id, experiment, ts, ptype)
        try:
            if ptype == "dymo":
                cmd = ["lp", "-d", name, pdf_path]
            else:
                cmd = ["lp", "-d", name, "-o", "media=4x6",
                       "-o", "orientation-requested=4", pdf_path]
            pr = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            result["steps"]["receipt"] = "printed" if pr.returncode == 0 else "failed"
        except Exception as e:
            result["steps"]["receipt"] = f"error: {e}"
        finally:
            try: os.unlink(pdf_path)
            except: pass
    else:
        result["steps"]["receipt"] = "no printer"

    return jsonify(result)


if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "unknown"

    print("\n\u2501" * 42)
    print("  MBRL Scan-to-Print  \u00b7  Print Server")
    print("\u2501" * 42)
    print(f"  Local:    http://localhost:5050")
    print(f"  Network:  http://{local_ip}:5050")
    print("\u2501" * 42 + "\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
