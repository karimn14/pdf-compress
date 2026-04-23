import os
import sys
import glob
import subprocess
import tempfile
from flask import Flask, request, send_file, jsonify, render_template_string

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

def find_ghostscript():
    """Find Ghostscript executable across platforms."""
    # Windows: try common install paths and registry-style locations
    if sys.platform == 'win32':
        candidates = ['gswin64c', 'gswin32c', 'gs']
        # Also search Program Files
        for pattern in [
            r'C:\Program Files\gs\gs*\bin\gswin64c.exe',
            r'C:\Program Files\gs\gs*\bin\gswin32c.exe',
            r'C:\Program Files (x86)\gs\gs*\bin\gswin64c.exe',
            r'C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe',
        ]:
            matches = glob.glob(pattern)
            if matches:
                return sorted(matches)[-1]  # latest version
        for cmd in candidates:
            try:
                subprocess.run([cmd, '--version'], capture_output=True, check=True)
                return cmd
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        return None
    # Linux / macOS
    for cmd in ['gs', 'ghostscript']:
        try:
            subprocess.run([cmd, '--version'], capture_output=True, check=True)
            return cmd
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return None

GS_CMD = find_ghostscript()

COMPRESSION_PROFILES = {
    "light": {
        "settings": "/printer",
        "dpi": 300,
        "label": "Light",
        "desc": "Minimal quality loss, moderate size reduction"
    },
    "balanced": {
        "settings": "/ebook",
        "dpi": 150,
        "label": "Balanced",
        "desc": "Good compression with acceptable quality"
    },
    "extreme": {
        "settings": "/screen",
        "dpi": 72,
        "label": "Extreme",
        "desc": "Maximum compression, smaller file size"
    }
}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>PDF Compressor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0d0d0d;
    --surface: #141414;
    --border: #222;
    --border-hover: #3a3a3a;
    --text: #e8e8e8;
    --muted: #555;
    --accent: #c8ff00;
    --accent-dim: rgba(200,255,0,0.08);
    --accent-mid: rgba(200,255,0,0.15);
    --danger: #ff4444;
    --radius: 12px;
    --transition: 0.2s cubic-bezier(0.4,0,0.2,1);
  }

  html, body {
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: 'Syne', sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  body {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px;
  }

  .grain {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    opacity: 0.03;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
    background-size: 200px;
  }

  .container {
    position: relative;
    z-index: 1;
    width: 100%;
    max-width: 520px;
  }

  .header {
    margin-bottom: 40px;
    text-align: center;
  }

  .logo {
    font-size: 11px;
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.25em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 16px;
  }

  .logo span {
    color: var(--accent);
  }

  h1 {
    font-size: clamp(32px, 6vw, 44px);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1;
    color: var(--text);
  }

  h1 em {
    font-style: normal;
    color: var(--accent);
  }

  .subtitle {
    margin-top: 10px;
    font-size: 13px;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-weight: 300;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    margin-bottom: 12px;
    transition: border-color var(--transition);
  }

  /* Drop Zone */
  .drop-zone {
    border: 1.5px dashed var(--border);
    border-radius: var(--radius);
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
    transition: all var(--transition);
    position: relative;
    background: transparent;
    margin-bottom: 12px;
  }

  .drop-zone:hover, .drop-zone.drag-over {
    border-color: var(--accent);
    background: var(--accent-dim);
  }

  .drop-zone input[type="file"] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
  }

  .drop-icon {
    width: 40px;
    height: 40px;
    margin: 0 auto 14px;
    opacity: 0.4;
    transition: opacity var(--transition);
  }

  .drop-zone:hover .drop-icon { opacity: 0.9; }

  .drop-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 4px;
  }

  .drop-hint {
    font-size: 11px;
    font-family: 'DM Mono', monospace;
    color: var(--muted);
  }

  /* File info */
  .file-info {
    display: none;
    align-items: center;
    gap: 12px;
    background: var(--accent-dim);
    border: 1px solid rgba(200,255,0,0.2);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
  }

  .file-info.show { display: flex; }

  .file-icon {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    background: var(--accent-mid);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .file-details { flex: 1; min-width: 0; }
  .file-name {
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text);
  }
  .file-size {
    font-size: 11px;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    margin-top: 2px;
  }

  .remove-btn {
    background: none;
    border: none;
    color: var(--muted);
    cursor: pointer;
    padding: 4px;
    line-height: 1;
    font-size: 16px;
    transition: color var(--transition);
    flex-shrink: 0;
  }
  .remove-btn:hover { color: var(--danger); }

  /* Level selector */
  .section-label {
    font-size: 11px;
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 10px;
  }

  .levels {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 20px;
  }

  .level-btn {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 8px;
    cursor: pointer;
    text-align: center;
    transition: all var(--transition);
    position: relative;
    overflow: hidden;
  }

  .level-btn:hover {
    border-color: var(--border-hover);
    background: rgba(255,255,255,0.02);
  }

  .level-btn.active {
    border-color: var(--accent);
    background: var(--accent-dim);
  }

  .level-btn.active::before {
    content: '';
    position: absolute;
    top: 6px; right: 6px;
    width: 6px; height: 6px;
    background: var(--accent);
    border-radius: 50%;
  }

  .level-name {
    font-size: 13px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 4px;
    letter-spacing: -0.02em;
  }

  .level-dpi {
    font-size: 10px;
    font-family: 'DM Mono', monospace;
    color: var(--muted);
    margin-bottom: 6px;
  }

  .level-bars {
    display: flex;
    gap: 2px;
    justify-content: center;
    align-items: flex-end;
    height: 14px;
  }

  .bar {
    width: 5px;
    border-radius: 2px;
    background: var(--muted);
    opacity: 0.3;
    transition: all var(--transition);
  }

  .level-btn.active .bar { opacity: 1; }
  .level-btn.active .bar { background: var(--accent); }

  /* Submit */
  .compress-btn {
    width: 100%;
    background: var(--accent);
    color: #0d0d0d;
    border: none;
    border-radius: 8px;
    padding: 15px;
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all var(--transition);
    position: relative;
    overflow: hidden;
  }

  .compress-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(200,255,0,0.25);
  }

  .compress-btn:active:not(:disabled) { transform: translateY(0); }

  .compress-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
    transform: none;
  }

  /* Progress */
  .progress-wrap {
    display: none;
    margin-top: 16px;
  }

  .progress-wrap.show { display: block; animation: fadeUp 0.2s ease; }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }

  .progress-label {
    font-size: 11px;
    font-family: 'DM Mono', monospace;
    color: var(--muted);
    letter-spacing: 0.08em;
  }

  .progress-pct {
    font-size: 22px;
    font-weight: 800;
    font-family: 'Syne', sans-serif;
    color: var(--accent);
    letter-spacing: -0.04em;
    line-height: 1;
    transition: all 0.15s ease;
    min-width: 52px;
    text-align: right;
  }

  .progress-bar-track {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    position: relative;
  }

  .progress-bar-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    width: 0%;
    transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
  }

  .progress-bar-fill::after {
    content: '';
    position: absolute;
    right: 0;
    top: 0;
    height: 100%;
    width: 40px;
    background: linear-gradient(to right, transparent, rgba(200,255,0,0.6));
    border-radius: 2px;
  }

  .progress-steps {
    display: flex;
    gap: 6px;
    margin-top: 10px;
  }

  .progress-step {
    flex: 1;
    font-size: 9px;
    font-family: 'DM Mono', monospace;
    color: var(--muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    opacity: 0.4;
    transition: all 0.3s ease;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .progress-step.active {
    color: var(--accent);
    opacity: 1;
  }

  .progress-step.done {
    color: var(--text);
    opacity: 0.5;
  }

  /* Result */
  .result-card {
    display: none;
    background: var(--surface);
    border: 1px solid rgba(200,255,0,0.25);
    border-radius: var(--radius);
    padding: 20px;
    margin-top: 12px;
  }

  .result-card.show { display: block; }

  .result-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }

  .result-stat { text-align: center; }
  .result-stat .val {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: var(--text);
  }
  .result-stat .lbl {
    font-size: 10px;
    font-family: 'DM Mono', monospace;
    color: var(--muted);
    text-transform: uppercase;
    margin-top: 2px;
  }

  .result-divider { color: var(--border); font-size: 20px; }

  .saving-badge {
    text-align: center;
  }
  .saving-badge .pct {
    font-size: 28px;
    font-weight: 800;
    color: var(--accent);
    letter-spacing: -0.04em;
  }
  .saving-badge .lbl {
    font-size: 10px;
    font-family: 'DM Mono', monospace;
    color: var(--muted);
    text-transform: uppercase;
  }

  .download-btn {
    width: 100%;
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    border-radius: 8px;
    padding: 12px;
    font-family: 'Syne', sans-serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all var(--transition);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .download-btn:hover {
    background: var(--accent);
    color: #0d0d0d;
  }

  /* Error */
  .error-msg {
    display: none;
    font-size: 12px;
    font-family: 'DM Mono', monospace;
    color: var(--danger);
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(255,68,68,0.06);
    border: 1px solid rgba(255,68,68,0.15);
    border-radius: 6px;
  }
  .error-msg.show { display: block; }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .container { animation: fadeUp 0.5s ease both; }
</style>
</head>
<body>
<div class="grain"></div>
<div class="container">
  <div class="header">
    <div class="logo">— <span>PDF</span> Tools —</div>
    <h1>Com<em>press</em></h1>
    <p class="subtitle">drop · choose · download</p>
  </div>

  <!-- Drop Zone -->
  <div class="drop-zone" id="dropZone">
    <input type="file" id="fileInput" accept=".pdf" />
    <svg class="drop-icon" viewBox="0 0 40 40" fill="none">
      <rect x="8" y="4" width="18" height="24" rx="2" stroke="#c8ff00" stroke-width="1.5"/>
      <path d="M26 4l6 6v18a2 2 0 01-2 2H10" stroke="#c8ff00" stroke-width="1.5" stroke-linecap="round"/>
      <path d="M26 4v6h6" stroke="#c8ff00" stroke-width="1.5" stroke-linecap="round"/>
      <path d="M14 32v4M14 36l-3-3M14 36l3-3" stroke="#c8ff00" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <div class="drop-title">Drop your PDF here</div>
    <div class="drop-hint">or click to browse · max 100MB</div>
  </div>

  <!-- File info chip -->
  <div class="file-info" id="fileInfo">
    <div class="file-icon">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="1" width="9" height="13" rx="1" stroke="#c8ff00" stroke-width="1.2"/>
        <path d="M11 1l3 3v9a1 1 0 01-1 1H5" stroke="#c8ff00" stroke-width="1.2"/>
        <path d="M11 1v3h3" stroke="#c8ff00" stroke-width="1.2"/>
      </svg>
    </div>
    <div class="file-details">
      <div class="file-name" id="fileName">—</div>
      <div class="file-size" id="fileSize">—</div>
    </div>
    <button class="remove-btn" id="removeBtn" title="Remove file">✕</button>
  </div>

  <!-- Level selector -->
  <div class="card">
    <div class="section-label">Compression Level</div>
    <div class="levels">
      <button class="level-btn active" data-level="light">
        <div class="level-name">Light</div>
        <div class="level-dpi">300 dpi</div>
        <div class="level-bars">
          <div class="bar" style="height:6px"></div>
          <div class="bar" style="height:10px"></div>
          <div class="bar" style="height:6px"></div>
        </div>
      </button>
      <button class="level-btn" data-level="balanced">
        <div class="level-name">Balanced</div>
        <div class="level-dpi">150 dpi</div>
        <div class="level-bars">
          <div class="bar" style="height:6px"></div>
          <div class="bar" style="height:10px"></div>
          <div class="bar" style="height:14px"></div>
        </div>
      </button>
      <button class="level-btn" data-level="extreme">
        <div class="level-name">Extreme</div>
        <div class="level-dpi">72 dpi</div>
        <div class="level-bars">
          <div class="bar" style="height:6px"></div>
          <div class="bar" style="height:10px"></div>
          <div class="bar" style="height:14px"></div>
        </div>
      </button>
    </div>

    <button class="compress-btn" id="compressBtn" disabled>Compress PDF</button>

    <div class="progress-wrap" id="progressWrap">
      <div class="progress-header">
        <span class="progress-label" id="progressLabel">Uploading…</span>
        <span class="progress-pct" id="progressPct">0%</span>
      </div>
      <div class="progress-bar-track">
        <div class="progress-bar-fill" id="progressFill"></div>
      </div>
      <div class="progress-steps">
        <span class="progress-step" id="step1">Upload</span>
        <span class="progress-step" id="step2">Analyze</span>
        <span class="progress-step" id="step3">Compress</span>
        <span class="progress-step" id="step4">Finalize</span>
      </div>
    </div>

    <div class="error-msg" id="errorMsg"></div>
  </div>

  <!-- Result -->
  <div class="result-card" id="resultCard">
    <div class="result-row">
      <div class="result-stat">
        <div class="val" id="origSize">—</div>
        <div class="lbl">Original</div>
      </div>
      <div class="saving-badge">
        <div class="pct" id="savingPct">—%</div>
        <div class="lbl">saved</div>
      </div>
      <div class="result-stat">
        <div class="val" id="compSize">—</div>
        <div class="lbl">Compressed</div>
      </div>
    </div>
    <button class="download-btn" id="downloadBtn">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M7 2v7M4 6l3 3 3-3M2 11h10" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      Download Compressed PDF
    </button>
  </div>
</div>

<script>
let selectedFile = null;
let selectedLevel = 'light';
let downloadUrl = null;

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const removeBtn = document.getElementById('removeBtn');
const compressBtn = document.getElementById('compressBtn');
const progressWrap = document.getElementById('progressWrap');
const errorMsg = document.getElementById('errorMsg');
const resultCard = document.getElementById('resultCard');

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/(1024*1024)).toFixed(2) + ' MB';
}

function setFile(file) {
  if (!file || file.type !== 'application/pdf') {
    showError('Please select a valid PDF file.');
    return;
  }
  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatSize(file.size);
  fileInfo.classList.add('show');
  dropZone.style.display = 'none';
  compressBtn.disabled = false;
  clearResult();
  clearError();
}

removeBtn.addEventListener('click', () => {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.classList.remove('show');
  dropZone.style.display = '';
  compressBtn.disabled = true;
  clearResult();
  clearError();
});

fileInput.addEventListener('change', e => {
  if (e.target.files[0]) setFile(e.target.files[0]);
});

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

// Level buttons
document.querySelectorAll('.level-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.level-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedLevel = btn.dataset.level;
  });
});

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.classList.add('show');
}
function clearError() { errorMsg.classList.remove('show'); }
function clearResult() {
  resultCard.classList.remove('show');
  if (downloadUrl) { URL.revokeObjectURL(downloadUrl); downloadUrl = null; }
}

// Progress engine
let progressInterval = null;
let currentPct = 0;
let targetPct = 0;

function setProgress(pct, label) {
  targetPct = Math.min(pct, 100);
  const fill = document.getElementById('progressFill');
  const pctEl = document.getElementById('progressPct');
  const labelEl = document.getElementById('progressLabel');
  fill.style.width = targetPct + '%';
  pctEl.textContent = Math.round(targetPct) + '%';
  if (label) labelEl.textContent = label;

  // Update step highlights
  const steps = ['step1','step2','step3','step4'];
  const thresholds = [0, 30, 55, 85];
  steps.forEach((id, i) => {
    const el = document.getElementById(id);
    el.className = 'progress-step';
    if (targetPct >= thresholds[i]) {
      const isLast = i === steps.length - 1;
      const nextThreshold = thresholds[i + 1] || 101;
      if (targetPct < nextThreshold) el.classList.add('active');
      else el.classList.add('done');
    }
  });
}

function startSimulatedProgress(startPct, endPct, durationMs, label) {
  clearInterval(progressInterval);
  const steps = 60;
  const interval = durationMs / steps;
  let step = 0;
  setProgress(startPct, label);
  progressInterval = setInterval(() => {
    step++;
    // Ease-out curve: fast start, slow finish
    const t = step / steps;
    const eased = 1 - Math.pow(1 - t, 2);
    const pct = startPct + (endPct - startPct) * eased;
    setProgress(pct, label);
    if (step >= steps) clearInterval(progressInterval);
  }, interval);
}

compressBtn.addEventListener('click', () => {
  if (!selectedFile) return;
  clearError();
  clearResult();

  compressBtn.disabled = true;
  progressWrap.classList.add('show');
  setProgress(0, 'Uploading…');

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('level', selectedLevel);

  // Use XHR to get real upload progress
  const xhr = new XMLHttpRequest();

  xhr.upload.addEventListener('progress', e => {
    if (e.lengthComputable) {
      const uploadPct = (e.loaded / e.total) * 28;
      setProgress(uploadPct, 'Uploading…');
    }
  });

  xhr.upload.addEventListener('load', () => {
    // Upload done → simulate server-side stages
    setProgress(30, 'Analyzing…');
    setTimeout(() => startSimulatedProgress(30, 55, 800, 'Analyzing…'), 80);
    setTimeout(() => startSimulatedProgress(55, 88, 1800, 'Compressing…'), 900);
    setTimeout(() => startSimulatedProgress(88, 95, 1200, 'Finalizing…'), 2750);
  });

  xhr.addEventListener('load', async () => {
    clearInterval(progressInterval);
    if (xhr.status !== 200) {
      try {
        const err = JSON.parse(xhr.responseText);
        showError(err.error || 'Compression failed');
      } catch { showError('Compression failed'); }
      compressBtn.disabled = false;
      progressWrap.classList.remove('show');
      return;
    }

    // Snap to 100%
    setProgress(100, 'Done!');
    await new Promise(r => setTimeout(r, 500));

    const blob = xhr.response;
    const origBytes = selectedFile.size;
    const compBytes = blob.size;
    const saved = Math.max(0, ((origBytes - compBytes) / origBytes * 100)).toFixed(1);

    document.getElementById('origSize').textContent = formatSize(origBytes);
    document.getElementById('compSize').textContent = formatSize(compBytes);
    document.getElementById('savingPct').textContent = saved + '%';

    downloadUrl = URL.createObjectURL(blob);
    document.getElementById('downloadBtn').onclick = () => {
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = selectedFile.name.replace('.pdf', '') + '_compressed.pdf';
      a.click();
    };

    resultCard.classList.add('show');
    compressBtn.disabled = false;
    await new Promise(r => setTimeout(r, 300));
    progressWrap.classList.remove('show');
    setProgress(0, 'Uploading…');
  });

  xhr.addEventListener('error', () => {
    clearInterval(progressInterval);
    showError('Network error. Is the server running?');
    compressBtn.disabled = false;
    progressWrap.classList.remove('show');
  });

  xhr.open('POST', '/compress');
  xhr.responseType = 'blob';
  xhr.send(formData);
});
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/compress', methods=['POST'])
def compress():
    if not GS_CMD:
        install_hint = (
            'Ghostscript not found. '
            'Windows: download from https://ghostscript.com/releases/gsdnld.html '
            'then restart this app. '
            'macOS: brew install ghostscript. '
            'Linux: sudo apt install ghostscript'
        )
        return jsonify({'error': install_hint}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    level = request.form.get('level', 'balanced')

    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Invalid file. Please upload a PDF.'}), 400

    profile = COMPRESSION_PROFILES.get(level, COMPRESSION_PROFILES['balanced'])

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as in_f:
        file.save(in_f.name)
        in_path = in_f.name

    out_fd, out_path = tempfile.mkstemp(suffix='.pdf')
    os.close(out_fd)

    try:
        cmd = [
            GS_CMD,
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.5',
            f'-dPDFSETTINGS={profile["settings"]}',
            '-dNOPAUSE',
            '-dQUIET',
            '-dBATCH',
            f'-dColorImageResolution={profile["dpi"]}',
            f'-dGrayImageResolution={profile["dpi"]}',
            f'-dMonoImageResolution={profile["dpi"]}',
            '-dCompressFonts=true',
            '-dSubsetFonts=true',
            '-dEmbedAllFonts=true',
            f'-sOutputFile={out_path}',
            in_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)

        if result.returncode != 0:
            raise Exception(f'Ghostscript error: {result.stderr.decode()}')

        original_size = os.path.getsize(in_path)
        compressed_size = os.path.getsize(out_path)

        # If compressed is bigger, return original
        if compressed_size >= original_size:
            send_path = in_path
        else:
            send_path = out_path

        return send_file(
            send_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='compressed.pdf'
        )

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Compression timed out. Try a smaller file.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try: os.unlink(in_path)
        except: pass
        try: os.unlink(out_path)
        except: pass

if __name__ == '__main__':
    print("\n  PDF Compressor → http://localhost:5000")
    if GS_CMD:
        print(f"  Ghostscript found: {GS_CMD}")
    else:
        print("  WARNING: Ghostscript NOT found.")
        print("     Windows: https://ghostscript.com/releases/gsdnld.html")
        print("     macOS:   brew install ghostscript")
        print("     Linux:   sudo apt install ghostscript")
    print()
    app.run(debug=False, host='0.0.0.0', port=5000)