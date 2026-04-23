# PDF Compressor

A minimal, self-hosted PDF compression web app running on localhost. Drop a PDF, pick a compression level, download the result — no uploads to third-party servers, no accounts, no internet required after setup.

---

## Preview

```
┌─────────────────────────────────┐
│        — PDF Tools —            │
│                                 │
│          Compress               │
│       drop · choose · download  │
│                                 │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐  │
│       Drop your PDF here        │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘  │
│                                 │
│  [ Light ] [Balanced] [Extreme] │
│                                 │
│  ████████████████  COMPRESS     │
└─────────────────────────────────┘
```

---

## Features

- **3 compression levels** — Light, Balanced, Extreme powered by Ghostscript
- **Real upload progress** — percentage counter tracks actual bytes sent via XHR
- **Animated stage indicator** — Upload → Analyze → Compress → Finalize steps
- **Before/after stats** — shows original size, compressed size, and % saved
- **Safe fallback** — returns original file if compression makes it larger
- **100% local** — your PDF never leaves your machine
- **Cross-platform** — Windows, macOS, Linux

---

## Requirements

| Dependency | Version | Purpose |
|---|---|---|
| Python | 3.8+ | Runtime |
| Flask | any | Web server |
| Ghostscript | any | PDF compression engine |

---

## Installation

### 1. Install Python dependencies

```bash
pip install flask
```

### 2. Install Ghostscript

**Windows**

Download the installer from https://ghostscript.com/releases/gsdnld.html (choose 64-bit).
During installation, make sure **"Add to PATH"** is checked. Restart your terminal after installing.

**macOS**

```bash
brew install ghostscript
```

**Linux (Debian/Ubuntu)**

```bash
sudo apt install ghostscript
```

---

## Usage

```bash
python pdf_compressor_app.py
```

Then open your browser at:

```
http://localhost:5000
```

### Workflow

1. **Drop** your PDF onto the upload zone (or click to browse)
2. **Choose** a compression level
3. **Click** Compress PDF and watch the progress bar
4. **Download** the compressed file when done

---

## Compression Levels

| Level | Ghostscript Profile | Image DPI | Best For |
|---|---|---|---|
| **Light** | `/printer` | 300 dpi | Print-quality docs, minimal quality loss |
| **Balanced** | `/ebook` | 150 dpi | Sharing via email or web |
| **Extreme** | `/screen` | 72 dpi | Maximum size reduction, screen-only viewing |

> The app automatically returns the original file if the compressed version ends up larger (common with already-optimized PDFs).

---

## File Size Limit

Maximum upload size is **100 MB**. To change it, edit this line in `pdf_compressor_app.py`:

```python
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
```

---

## Project Structure

```
pdf_compressor/
├── pdf_compressor_app.py   # Flask app (backend + frontend in one file)
└── README.md
```

The entire frontend (HTML, CSS, JS) is embedded as a Python string inside `pdf_compressor_app.py` — no build tools, no node_modules, no separate template files needed.

---

## Troubleshooting

**`[WinError 2] The system cannot find the file specified`**
Ghostscript is not installed or not on PATH. Install it from ghostscript.com and restart your terminal.

**App starts but shows "Ghostscript NOT found" warning**
Same as above. The startup log will print the exact install link for your platform.

**Compressed file is the same size as the original**
The PDF is already well-optimized. Try the Extreme level, or the file may not compress further.

**Port 5000 already in use**
Change the port at the bottom of `pdf_compressor_app.py`:
```python
app.run(debug=False, host='0.0.0.0', port=5001)
```

---

## Tech Stack

- **Backend** — Python + Flask
- **Compression** — Ghostscript (`gs` / `gswin64c`)
- **Frontend** — Vanilla HTML/CSS/JS (no framework)
- **Fonts** — Syne (display) + DM Mono (labels) via Google Fonts
- **Design** — Dark minimalist, `#c8ff00` lime accent

---

## License

MIT — use freely, modify freely.