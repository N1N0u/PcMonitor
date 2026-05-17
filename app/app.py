#!/usr/bin/env python3

import subprocess
import threading
import time
import os
import signal
import psutil
from flask import Flask, render_template_string, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)

metrics = PrometheusMetrics(app)
metrics.info('app_info', 'Application info', version='1.0.0')

# ─── CONFIG ───────────────────────────────────────────────────
DURATION = 30
CPU_CORES = os.cpu_count() or 1
RAM_SIZE = "10G"

# ─── STATE ────────────────────────────────────────────────────
active_processes = []
stress_log = []
stress_running = False
lock = threading.Lock()


def log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    with lock:
        stress_log.append(entry)
        if len(stress_log) > 200:
            stress_log.pop(0)
    print(entry)


def run_stress(cmd: list[str], label: str):
    global stress_running
    with lock:
        stress_running = True
    log(f"▶ Starting {label}...")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=os.setsid,
        )
        with lock:
            active_processes.append(proc)
        for line in proc.stdout:
            log(line.rstrip())
        proc.wait()
        log(f"{label} done (exit {proc.returncode}).")
    except FileNotFoundError as e:
        log(f"Command not found: {e}. Is stress-ng installed?")
    except Exception as e:
        log(f"Error during {label}: {e}")
    finally:
        with lock:
            active_processes[:] = [p for p in active_processes if p.poll() is None]
            stress_running = False


def stop_all():
    log("Stopping all stress processes...")
    with lock:
        for proc in active_processes:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
        active_processes.clear()
    # Also kill any lingering stress-ng
    subprocess.run(["pkill", "-f", "stress-ng"], capture_output=True)
    subprocess.run(["pkill", "-f", "gpu_burn"], capture_output=True)
    log("All stopped. System is idle.")


# ─── ROUTES ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE,
                                  duration=DURATION,
                                  cpu_cores=CPU_CORES,
                                  ram_size=RAM_SIZE)


@app.route("/api/start", methods=["POST"])
def api_start():
    global DURATION, RAM_SIZE
    data = request.get_json() or {}
    mode = data.get("mode", "cpu")

    # Allow override of duration/ram from frontend
    try:
        DURATION = int(data.get("duration", DURATION))
    except ValueError:
        pass
    RAM_SIZE = data.get("ram_size", RAM_SIZE)

    if stress_running:
        return jsonify({"ok": False, "msg": "A stress task is already running."})

    if mode == "cpu":
        cmd = ["stress-ng", "--cpu", str(CPU_CORES),
               "--timeout", f"{DURATION}s", "--metrics-brief"]
        label = f"CPU Stress ({CPU_CORES} cores, {DURATION}s)"

    elif mode == "ram":
        cmd = ["stress-ng", "--vm", "1", "--vm-bytes", RAM_SIZE,
               "--timeout", f"{DURATION}s", "--metrics-brief"]
        label = f"RAM Stress ({RAM_SIZE}, {DURATION}s)"

    elif mode == "both":
        cmd = ["stress-ng",
               "--cpu", str(CPU_CORES),
               "--vm", "1", "--vm-bytes", RAM_SIZE,
               "--timeout", f"{DURATION}s", "--metrics-brief"]
        label = f"CPU + RAM Stress ({DURATION}s)"

    elif mode == "gpu":
        threading.Thread(target=_gpu_stress_thread, daemon=True).start()
        return jsonify({"ok": True, "msg": "GPU stress started."})

    else:
        return jsonify({"ok": False, "msg": f"Unknown mode: {mode}"})

    threading.Thread(target=run_stress, args=(cmd, label), daemon=True).start()
    return jsonify({"ok": True, "msg": f"{label} started."})


def _gpu_stress_thread():
    global stress_running

    with lock:
        stress_running = True

    log("🎮 Starting GPU stress...")

    try:
        import torch

        if not torch.cuda.is_available():
            log("❌ CUDA not available.")
            return

        device = torch.device("cuda:0")

        gpu_name = torch.cuda.get_device_name(device)
        total_mem = torch.cuda.get_device_properties(device).total_memory / 1e9

        log(f"✅ GPU detected: {gpu_name}")
        log(f"🧠 VRAM: {total_mem:.2f} GB")

        # Large tensors
        size = 8192

        a = torch.randn(size, size, device=device)
        b = torch.randn(size, size, device=device)

        end_time = time.time() + DURATION
        iterations = 0

        while time.time() < end_time:
            c = torch.mm(a, b)

            # Extra load
            c = torch.relu(c)

            torch.cuda.synchronize()

            iterations += 1

            if iterations % 5 == 0:
                allocated = torch.cuda.memory_allocated(device) / 1e9
                reserved = torch.cuda.memory_reserved(device) / 1e9

                log(
                    f"🔥 Iteration {iterations} | "
                    f"VRAM {allocated:.2f}/{reserved:.2f} GB"
                )

        log("✅ GPU stress completed successfully.")

    except Exception as e:
        log(f"❌ GPU stress error: {e}")

    finally:
        try:
            torch.cuda.empty_cache()
        except:
            pass

        with lock:
            stress_running = False


@app.route("/api/stop", methods=["POST"])
def api_stop():
    threading.Thread(target=stop_all, daemon=True).start()
    return jsonify({"ok": True, "msg": "Stop signal sent."})


@app.route("/api/logs")
def api_logs():
    with lock:
        return jsonify({"logs": list(stress_log), "running": stress_running})


@app.route("/api/metrics")
def api_metrics():
    """Live system metrics for the dashboard."""
    try:
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        cores = [p for p in psutil.cpu_percent(percpu=True)]
        return jsonify({
            "cpu_total": cpu,
            "cpu_cores": cores,
            "ram_used_gb": round(mem.used / 1e9, 2),
            "ram_total_gb": round(mem.total / 1e9, 2),
            "ram_percent": mem.percent,
            "running": stress_running,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── HTML TEMPLATE ────────────────────────────────────────────

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>STRESS — System Stress Tool</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@700;900&display=swap');

  :root {
    --bg:        #0a0c0f;
    --panel:     #0f1318;
    --border:    #1e2730;
    --accent1:   #00ffe0;   /* cyan */
    --accent2:   #ff4060;   /* red */
    --accent3:   #ffcc00;   /* yellow */
    --accent4:   #a64dff;   /* purple */
    --accent5:   #00bfff;   /* blue */
    --text:      #c8d8e8;
    --dim:       #4a5a6a;
    --mono:      'Share Tech Mono', monospace;
    --display:   'Orbitron', sans-serif;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    min-height: 100vh;
    overflow-x: hidden;
    background-image:
      radial-gradient(ellipse 80% 40% at 50% -10%, rgba(0,255,224,0.07) 0%, transparent 70%),
      repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,255,224,0.03) 40px),
      repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,255,224,0.03) 40px);
  }

  /* ── HEADER ── */
  header {
    padding: 2rem 2.5rem 1rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .logo {
    font-size: 1.8rem;
    font-weight: 900;
    font-family: var(--display);
    letter-spacing: 0.1em;
    background: linear-gradient(90deg, var(--accent1), var(--accent4));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .logo span { color: var(--accent2); }

  .tagline {
    font-size: 0.65rem;
    color: var(--dim);
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .status-pill {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    background: rgba(255,64,96, 0.1);
    border: 1px solid var(--accent2);
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: bold;
  }

  .status-pill.running {
    background: rgba(0,255,224, 0.1);
    border-color: var(--accent1);
  }

  .status-dot {
    width: 8px;
    height: 8px;
    background: var(--accent2);
    border-radius: 50%;
    animation: pulse 2s infinite;
  }

  .status-pill.running .status-dot {
    background: var(--accent1);
  }

  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

  /* ── MAIN LAYOUT ── */
  main {
    padding: 2rem 2.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1.5rem;
    margin-bottom: 2rem;
  }

  .card-title {
    font-size: 0.85rem;
    text-transform: uppercase;
    color: var(--accent1);
    margin-bottom: 1rem;
    letter-spacing: 0.08em;
    font-weight: bold;
  }

  /* ── CONFIG ROW ── */
  .config-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .field {
    display: flex;
    flex-direction: column;
  }

  .field label {
    font-size: 0.7rem;
    color: var(--dim);
    margin-bottom: 0.3rem;
    text-transform: uppercase;
  }

  .field input {
    background: rgba(0,255,224, 0.05);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.5rem 0.75rem;
    font-family: var(--mono);
    font-size: 0.85rem;
    border-radius: 2px;
  }

  .field input:focus {
    outline: none;
    border-color: var(--accent1);
    box-shadow: 0 0 8px rgba(0,255,224, 0.3);
  }

  /* ── BUTTON GRID ── */
  .btn-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.75rem;
  }

  .btn {
    padding: 0.75rem 1rem;
    font-family: var(--mono);
    font-size: 0.75rem;
    text-transform: uppercase;
    font-weight: bold;
    border: 1px solid;
    background: transparent;
    cursor: pointer;
    border-radius: 2px;
    transition: all 0.2s;
  }

  .btn.cpu  { color: var(--accent2); border-color: var(--accent2); }
  .btn.ram  { color: var(--accent3); border-color: var(--accent3); }
  .btn.both { color: var(--accent4); border-color: var(--accent4); }
  .btn.gpu  { color: var(--accent5); border-color: var(--accent5); }
  .btn.stop { color: var(--accent2); border-color: var(--accent2); }

  .btn:hover {
    box-shadow: 0 0 12px currentColor;
    text-shadow: 0 0 6px currentColor;
  }

  /* ── METRICS ── */
  .metric-group {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .metric-box {
    background: rgba(0,255,224, 0.05);
    border: 1px solid var(--border);
    padding: 1rem;
    border-radius: 2px;
  }

  .metric-label {
    font-size: 0.7rem;
    color: var(--dim);
    text-transform: uppercase;
    margin-bottom: 0.3rem;
  }

  .metric-value {
    font-size: 1.8rem;
    font-weight: bold;
    color: var(--accent1);
    font-family: var(--display);
    margin-bottom: 0.3rem;
  }

  .metric-value.warn { color: var(--accent3); }
  .metric-value.hot  { color: var(--accent2); }

  .metric-sub {
    font-size: 0.65rem;
    color: var(--dim);
    margin-bottom: 0.5rem;
  }

  .prog-wrap {
    width: 100%;
    height: 4px;
    background: rgba(0,255,224, 0.1);
    border-radius: 2px;
    overflow: hidden;
  }

  .prog-fill {
    height: 100%;
    background: var(--accent1);
    transition: width 0.3s;
  }

  .prog-fill.warn { background: var(--accent3); }

  /* ── BAR CHART ── */
  .bar-chart {
    display: flex;
    align-items: flex-end;
    justify-content: flex-start;
    gap: 3px;
    height: 60px;
    padding: 0.5rem 0;
  }

  .bar-col {
    flex: 1;
    min-width: 2px;
    background: var(--accent1);
    border-radius: 1px;
  }

  .bar-col.warm { background: var(--accent3); }
  .bar-col.hot  { background: var(--accent2); }

  /* ── CONSOLE ── */
  .log-card {
    display: flex;
    flex-direction: column;
  }

  .console-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .clear-btn {
    padding: 0.3rem 0.6rem;
    font-size: 0.65rem;
    background: rgba(255,64,96, 0.2);
    color: var(--accent2);
    border: 1px solid var(--accent2);
    border-radius: 2px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .clear-btn:hover {
    background: rgba(255,64,96, 0.4);
  }

  .console {
    background: rgba(0,0,0, 0.3);
    border: 1px solid var(--border);
    padding: 1rem;
    border-radius: 2px;
    font-size: 0.75rem;
    max-height: 300px;
    overflow-y: auto;
    font-family: var(--mono);
  }

  .log-line {
    display: block;
    line-height: 1.4;
    color: var(--dim);
  }

  .log-line.info  { color: var(--accent5); }
  .log-line.ok    { color: #00e87a; }
  .log-line.warn  { color: var(--accent3); }
  .log-line.err   { color: var(--accent2); }
  .log-line.start { color: var(--accent1); }

  /* ── TOAST ── */
  #toast-area {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .toast {
    background: rgba(15,19,24, 0.95);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent1);
    padding: 0.6rem 1rem;
    font-size: 0.75rem;
    border-radius: 2px;
    animation: slideIn 0.3s ease, fadeOut 0.4s 2.6s ease forwards;
    max-width: 280px;
    color: var(--text);
  }
  .toast.err  { border-left-color: var(--accent2); color: var(--accent2); }
  .toast.ok   { border-left-color: #00e87a; }
  @keyframes slideIn  { from { opacity:0; transform: translateX(20px); } to { opacity:1; transform:none; } }
  @keyframes fadeOut  { to { opacity:0; transform: translateX(10px); } }

  /* ── FOOTER ── */
  footer {
    text-align: center;
    padding: 1.5rem;
    font-size: 0.62rem;
    letter-spacing: 0.15em;
    color: var(--dim);
    border-top: 1px solid var(--border);
    text-transform: uppercase;
  }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">STR<span>E</span>SS</div>
    <div class="tagline">System Stress Tool — {{ cpu_cores }} Cores / {{ ram_size }} RAM</div>
  </div>
  <div class="status-pill" id="status-pill">
    <div class="status-dot" id="status-dot"></div>
    <span id="status-text">IDLE</span>
  </div>
</header>

<main>

  <!-- ── CONTROLS ── -->
  <div class="card">
    <div class="card-title">⚙ Configuration</div>
    <div class="config-row">
      <div class="field">
        <label>Duration (s)</label>
        <input type="number" id="cfg-duration" value="{{ duration }}" min="1" max="3600" />
      </div>
      <div class="field">
        <label>RAM Size</label>
        <input type="text" id="cfg-ram" value="{{ ram_size }}" placeholder="e.g. 4G" />
      </div>
    </div>

    <div class="card-title">⚡ Stress Mode</div>
    <div class="btn-grid">
      <button class="btn cpu"  onclick="startStress('cpu')">🔥 CPU</button>
      <button class="btn ram"  onclick="startStress('ram')">🧠 RAM</button>
      <button class="btn both" onclick="startStress('both')">💥 CPU + RAM</button>
      <button class="btn gpu"  onclick="startStress('gpu')">🎮 GPU</button>
      <button class="btn stop" onclick="stopStress()">⛔ STOP ALL</button>
    </div>
  </div>

  <!-- ── METRICS ── -->
  <div class="card">
    <div class="card-title">📊 Live Metrics</div>
    <div class="metric-group">
      <div class="metric-box">
        <div class="metric-label">CPU Total</div>
        <div class="metric-value" id="m-cpu">—</div>
        <div class="metric-sub">% utilization</div>
        <div class="prog-wrap"><div class="prog-fill" id="pb-cpu" style="width:0%"></div></div>
      </div>
      <div class="metric-box">
        <div class="metric-label">RAM Used</div>
        <div class="metric-value" id="m-ram">—</div>
        <div class="metric-sub" id="m-ram-sub">— / — GB</div>
        <div class="prog-wrap"><div class="prog-fill" id="pb-ram" style="width:0%"></div></div>
      </div>
    </div>

    <div class="card-title" style="margin-top:0.5rem">Per-Core Load</div>
    <div class="bar-chart" id="core-bars"></div>
  </div>

  <!-- ── LOG CONSOLE ── -->
  <div class="card log-card">
    <div class="console-header">
      <div class="card-title" style="margin:0">📋 Output Console</div>
      <button class="clear-btn" onclick="clearLogs()">Clear</button>
    </div>
    <div class="console" id="console">
      <span class="log-line info">Stress tool ready. Choose a mode above.</span>
    </div>
  </div>

</main>

<div id="toast-area"></div>

<footer>stress.py — python flask edition — system load testing tool</footer>

<script>
  let knownLogCount = 0;
  let metricsInterval, logsInterval;

  // ── API ──────────────────────────────────────────────────────
  async function startStress(mode) {
    const duration = parseInt(document.getElementById('cfg-duration').value) || {{ duration }};
    const ram_size = document.getElementById('cfg-ram').value.trim() || '{{ ram_size }}';
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, duration, ram_size }),
    });
    const data = await res.json();
    toast(data.msg, data.ok ? 'ok' : 'err');
  }

  async function stopStress() {
    const res = await fetch('/api/stop', { method: 'POST' });
    const data = await res.json();
    toast(data.msg, data.ok ? 'ok' : 'err');
  }

  // ── METRICS POLL ─────────────────────────────────────────────
  async function fetchMetrics() {
    try {
      const res = await fetch('/api/metrics');
      const d = await res.json();
      if (d.error) return;

      const cpuPct = d.cpu_total;
      const ramPct = d.ram_percent;

      document.getElementById('m-cpu').textContent = cpuPct.toFixed(1) + '%';
      document.getElementById('m-cpu').className =
        'metric-value' + (cpuPct > 90 ? ' hot' : cpuPct > 60 ? ' warn' : '');
      document.getElementById('pb-cpu').style.width = cpuPct + '%';
      document.getElementById('pb-cpu').className =
        'prog-fill' + (cpuPct > 75 ? ' warn' : '');

      document.getElementById('m-ram').textContent = d.ram_used_gb + ' GB';
      document.getElementById('m-ram').className =
        'metric-value' + (ramPct > 90 ? ' hot' : ramPct > 70 ? ' warn' : '');
      document.getElementById('m-ram-sub').textContent =
        `${d.ram_used_gb} / ${d.ram_total_gb} GB`;
      document.getElementById('pb-ram').style.width = ramPct + '%';
      document.getElementById('pb-ram').className =
        'prog-fill' + (ramPct > 75 ? ' warn' : '');

      // Per-core bars
      const bars = document.getElementById('core-bars');
      if (d.cpu_cores && d.cpu_cores.length > 0) {
        bars.innerHTML = d.cpu_cores.map(pct => {
          const h = Math.max(2, Math.round(pct * 0.6));
          const cls = pct > 90 ? 'hot' : pct > 60 ? 'warm' : '';
          return `<div class="bar-col ${cls}" style="height:${h}px" title="Core ${pct}%"></div>`;
        }).join('');
      }

      // Status pill
      const pill = document.getElementById('status-pill');
      const txt  = document.getElementById('status-text');
      if (d.running) {
        pill.classList.add('running');
        txt.textContent = 'RUNNING';
      } else {
        pill.classList.remove('running');
        txt.textContent = 'IDLE';
      }
    } catch(e) { /* silent */ }
  }

  // ── LOG POLL ─────────────────────────────────────────────────
  async function fetchLogs() {
    try {
      const res = await fetch('/api/logs');
      const d = await res.json();
      if (d.logs.length === knownLogCount) return;
      knownLogCount = d.logs.length;

      const con = document.getElementById('console');
      con.innerHTML = d.logs.map(line => {
        let cls = 'log-line';
        if (line.includes('✅') || line.includes('done'))     cls += ' ok';
        else if (line.includes('❌') || line.includes('Error')) cls += ' err';
        else if (line.includes('⚠') || line.includes('warn')) cls += ' warn';
        else if (line.includes('▶') || line.includes('Starting')) cls += ' start';
        else if (line.includes('[') )                          cls += ' info';
        return `<span class="${cls}">${escHtml(line)}</span>`;
      }).join('\n');
      con.scrollTop = con.scrollHeight;
    } catch(e) { /* silent */ }
  }

  function clearLogs() {
    document.getElementById('console').innerHTML =
      '<span class="log-line info">Console cleared.</span>';
    knownLogCount = 0;
  }

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── TOAST ────────────────────────────────────────────────────
  function toast(msg, type='ok') {
    const area = document.getElementById('toast-area');
    const el = document.createElement('div');
    el.className = `toast ${type === 'err' ? 'err' : 'ok'}`;
    el.textContent = msg;
    area.appendChild(el);
    setTimeout(() => el.remove(), 3100);
  }

  // ── INIT ─────────────────────────────────────────────────────
  fetchMetrics();
  fetchLogs();
  metricsInterval = setInterval(fetchMetrics, 800);
  logsInterval    = setInterval(fetchLogs,    1000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import sys

    # Check for psutil
    try:
        import psutil  # noqa: F401
    except ImportError:
        print("psutil not found. Install it: pip install psutil flask")
        sys.exit(1)

    port = int(os.environ.get("PORT", 5000))
    print(f"\n  🔥 STRESS webapp running → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)