# MBRL Scan-to-Print

Webapp for participant check-in. Scan a SONA QR code → print an ID label instantly.

Works on iPad (camera scanning), MacBook, and desktop — any device on the lab network.

---

## How It Works

```
iPad / MacBook / Desktop
        │
        │  browser  (http://lab-mac-ip:5050)
        ▼
  Flask server  ←── runs on lab Mac
        │
        │  CUPS / lp
        ▼
  HP KE203 or Dymo LabelWriter
```

The webapp is served by a small Python server running on the lab Mac. Any device on the same WiFi/network can open it in a browser. The server detects whichever label printer is plugged in and sends print jobs directly.

---

## Setup (One Time)

### 1 — Clone from GitHub
```bash
git clone https://github.com/<your-lab-org>/mbrl-scan-to-print.git
cd mbrl-scan-to-print
```

### 2 — Install Python dependencies
```bash
pip3 install -r requirements.txt
```

### 3 — Plug in the printer
Connect the HP KE203 (or Dymo) via USB. Make sure it's powered on.

### 4 — Start the server
```bash
chmod +x start.sh
./start.sh
```

The terminal will print the network URL (e.g. `http://10.0.0.45:5050`).

---

## Daily Use

### On the lab Mac
```bash
./start.sh
```
Browser opens automatically.

### On iPad
Open Safari → go to `http://<mac-ip>:5050` → tap **Share → Add to Home Screen** to bookmark it like an app.

### Scanning options
| Method | How |
|--------|-----|
| **Camera** (iPad) | Tap "Start Camera" → point at participant's phone |
| **USB scanner** | Plug in Eyoyo scanner → scan directly, no clicks needed |
| **Manual** | Type SONA ID in the field → tap Print or press Enter |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Server offline" in browser | Run `./start.sh` on the lab Mac |
| "No printer detected" | Check USB cable, make sure printer is on, restart server |
| iPad can't reach the URL | Make sure iPad and Mac are on the same WiFi network |
| Camera not working on iPad | Tap Allow when Safari asks for camera permission |
| USB scanner not triggering print | Click anywhere on the page first (page must have focus) |

---

## Adding to GitHub

Push to your lab GitHub repo:
```bash
git init
git add .
git commit -m "Initial MBRL Scan-to-Print setup"
git remote add origin https://github.com/<your-lab-org>/mbrl-scan-to-print.git
git push -u origin main
```

On any new Mac in the lab, just `git clone` and run `./start.sh`.

---

## Files

| File | Purpose |
|------|---------|
| `server.py` | Flask server — serves webapp + handles print jobs |
| `templates/index.html` | The webapp UI |
| `start.sh` | One-click launcher |
| `requirements.txt` | Python dependencies |
