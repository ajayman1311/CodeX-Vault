import os
import json
import shutil
import socket
import time
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'codex_vault_persistent_v3_2026'

# --- Configuration & Paths ---
BASE_DIR = os.getcwd()
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'vault_files')
CHUNKS_DIR = os.path.join(BASE_DIR, 'temp_chunks')
CONFIG_FILE = os.path.join(BASE_DIR, 'vault_settings.json')

# 1. SMART CLEANUP: Startup par sirf purana kachra saaf karega (24hr old)
# Isse server restart hone par bhi current uploads delete nahi honge.
def smart_cleanup():
    if not os.path.exists(CHUNKS_DIR):
        os.makedirs(CHUNKS_DIR)
        return
    now = time.time()
    for f in os.listdir(CHUNKS_DIR):
        file_path = os.path.join(CHUNKS_DIR, f)
        # Agar chunk 24 ghante se zyada purana hai, toh delete karo
        if os.stat(file_path).st_mtime < now - 86400:
            try: os.remove(file_path)
            except: pass

smart_cleanup()
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {'password': 'admin', 'protection_key': 'MES2026'}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "127.0.0.1"

# --- UI with Smart Resume Logic ---
UI_SHARED = '''
<style>
    :root { --neon: #00f2ff; --glass: rgba(255, 255, 255, 0.05); --border: rgba(255, 255, 255, 0.15); }
    body { margin: 0; background: #000; background-image: radial-gradient(at 0% 0%, rgba(0, 119, 255, 0.2) 0px, transparent 50%), radial-gradient(at 100% 100%, rgba(0, 242, 255, 0.15) 0px, transparent 50%); color: white; font-family: 'Segoe UI', sans-serif; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .glass-card { background: var(--glass); backdrop-filter: blur(45px) saturate(180%); border: 1px solid var(--border); border-radius: 30px; padding: 40px; width: 90%; max-width: 800px; box-shadow: 0 25px 50px rgba(0,0,0,0.6); text-align: center; }
    .logo { font-size: 24px; font-weight: 900; color: var(--neon); letter-spacing: 4px; text-transform: uppercase; margin-bottom: 20px; }
    input { background: rgba(255, 255, 255, 0.07); border: 1px solid var(--border); color: white; padding: 15px; border-radius: 12px; width: 100%; box-sizing: border-box; margin-bottom: 15px; }
    .btn { background: var(--neon); color: #000; border: none; padding: 12px 20px; border-radius: 12px; font-weight: bold; cursor: pointer; transition: 0.3s; text-decoration: none; display: inline-block; }
    .btn:hover { box-shadow: 0 0 25px var(--neon); transform: translateY(-2px); }
    .file-item { background: rgba(255,255,255,0.03); margin-bottom: 12px; padding: 18px; border-radius: 18px; display: flex; justify-content: space-between; border: 1px solid var(--border); align-items: center; }
    .prog-wrapper { width: 100%; margin: 25px 0; display: none; }
    .prog-container { height: 10px; width: 100%; background: rgba(255,255,255,0.05); border-radius: 10px; overflow: hidden; }
    .prog-bar { height: 100%; width: 0%; background: var(--neon); box-shadow: 0 0 15px var(--neon); transition: 0.4s; }
    .status-msg { font-size: 12px; margin-top: 10px; font-weight: bold; color: var(--neon); }
    .slow-warning { color: #ffcc00; display: none; font-size: 11px; margin-top: 5px; animation: blink 1s infinite; }
    @keyframes blink { 50% { opacity: 0.5; } }
</style>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    conf = load_config()
    if session.get('auth'): return redirect('/')
    error = None
    if request.method == 'POST':
        if request.form.get('p') == conf['password']:
            session['auth'] = True
            return redirect('/')
        error = "WRONG KEY"
    return render_template_string(f'<html><head>{UI_SHARED}</head><body><div class="glass-card"><div class="logo">CodeX Vault</div><form method="post"><input type="password" name="p" placeholder="Enter Key" required><button class="btn" style="width:100%;">UNLOCK</button></form><a href="/recovery" style="color:#666; font-size:12px; text-decoration:none; display:block; margin-top:15px;">Forget Password?</a>{{% if error %}}<p style="color:red;">{{{{error}}}}</p>{{% endif %}}</div></body></html>', error=error)

@app.route('/recovery', methods=['GET', 'POST'])
def recovery():
    error = None
    if request.method == 'POST':
        if request.form.get('pk') == load_config()['protection_key']:
            session['auth'] = True
            return redirect('/settings')
        error = "INVALID PROTECTION ID"
    return render_template_string(f'<html><head>{UI_SHARED}</head><body><div class="glass-card"><h1>RECOVERY</h1><form method="post"><input type="password" name="pk" placeholder="Enter Protection ID" required><button class="btn" style="width:100%;">VERIFY</button></form><a href="/login" style="color:#555; text-decoration:none; display:block; margin-top:15px;">Back to Login</a>{{% if error %}}<p style="color:red;">{{{{error}}}}</p>{{% endif %}}</div></body></html>', error=error)

@app.route('/')
def index():
    if not session.get('auth'): return redirect(url_for('login'))
    raw_files = os.listdir(UPLOAD_FOLDER)
    files = [{'raw': f, 'name': f.split('_', 2)[-1] if '_' in f else f, 'time': datetime.fromtimestamp(os.path.getmtime(os.path.join(UPLOAD_FOLDER, f))).strftime('%Y-%m-%d %H:%M')} for f in raw_files]
    files.sort(key=lambda x: x['time'], reverse=True)
    return render_template_string('''
    <html><head>''' + UI_SHARED + '''</head><body><div class="glass-card">
        <header style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px;">
            <div class="logo" style="margin:0;">Vault</div>
            <div style="display:flex; gap:10px;">
                <label class="btn">UPLOAD + <input type="file" id="u-file" style="display:none;"></label>
                <a href="/settings" class="btn" style="background:none; border:1px solid var(--border); color:white;">SETTINGS</a>
                <a href="/logout" class="btn" style="background:none; border:1px solid #ff4d4d; color:#ff4d4d;">LOGOUT</a>
            </div>
        </header>
        <div class="prog-wrapper" id="p-wrapper">
            <div class="prog-container"><div class="prog-bar" id="p-bar"></div></div>
            <div class="status-msg" id="p-text">Ready</div>
            <div class="slow-warning" id="slow-msg">⚠️ Server response slow. Adjusting...</div>
        </div>
        <div id="file-list">
            {% for f in files %}
            <div class="file-item">
                <div style="text-align:left;"><b style="color:#eee;">{{ f.name }}</b><br><small style="color:#555;">{{ f.time }}</small></div>
                <div style="display:flex; gap:15px;"><a href="/download/{{ f.raw }}" style="color:var(--neon); text-decoration:none; font-weight:bold;">GET</a><a href="/delete/{{ f.raw }}" style="color:#ff4d4d; text-decoration:none;">✕</a></div>
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
    document.getElementById("u-file").onchange = async (e) => {
        const file = e.target.files[0];
        if(!file) return;
        document.getElementById("p-wrapper").style.display = "block";
        const CHUNK_SIZE = 1024 * 1024 * 2;
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
        
        // Generate a Persistent ID for this specific file
        const fid = btoa(file.name + file.size).substring(0, 16);

        // 1. Check if some chunks already exist (Smart Resume)
        const checkResp = await fetch(`/check_progress?fid=${fid}`);
        const uploadedChunks = await checkResp.json();

        for (let i = 0; i < totalChunks; i++) {
            // Skip if chunk already exists on server
            if (uploadedChunks.includes(i.toString())) continue;

            let success = false;
            while (!success) {
                try {
                    const fd = new FormData();
                    fd.append("file", file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE));
                    fd.append("fid", fid);
                    fd.append("index", i);
                    const startTime = Date.now();
                    const resp = await fetch("/upload_chunk", { method: "POST", body: fd });
                    if (!resp.ok) throw new Error();
                    
                    if (Date.now() - startTime > 3000) document.getElementById("slow-msg").style.display = "block";
                    else document.getElementById("slow-msg").style.display = "none";
                    
                    success = true;
                    let p = Math.round(((i + 1) / totalChunks) * 100);
                    document.getElementById("p-bar").style.width = p + "%";
                    document.getElementById("p-text").innerText = "Uploading: " + p + "%";
                } catch (err) {
                    document.getElementById("p-text").innerText = "Network Lost. Resuming in 5s...";
                    document.getElementById("p-text").style.color = "red";
                    await new Promise(r => setTimeout(r, 5000));
                }
            }
            document.getElementById("p-text").style.color = "var(--neon)";
        }
        document.getElementById("p-text").innerText = "Finalizing...";
        await fetch("/assemble", { method: "POST", body: new URLSearchParams({fid, name: file.name, total: totalChunks}) });
        location.reload();
    };
    </script></body></html>''', files=files)

@app.route('/check_progress')
def check_progress():
    fid = request.args.get('fid')
    # List down all chunks indices already on server for this fid
    existing = [f.split('_')[1] for f in os.listdir(CHUNKS_DIR) if f.startswith(fid)]
    return json.dumps(existing)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('auth'): return redirect(url_for('login'))
    conf = load_config()
    msg = None
    if request.method == 'POST':
        if request.form.get('new_p'): conf['password'] = request.form.get('new_p')
        if request.form.get('new_pk'): conf['protection_key'] = request.form.get('new_pk')
        save_config(conf)
        msg = "SECURITY UPDATED!"
    return render_template_string(f'''
    <html><head>{UI_SHARED}</head><body><div class="glass-card">
        <div class="logo">Settings</div>
        <form method="post">
            <input type="password" name="new_p" placeholder="New Vault Key">
            <input type="password" name="new_pk" placeholder="New Protection ID">
            <button class="btn" style="width:100%;">SAVE CHANGES</button>
        </form>
        <a href="/" style="color:#555; text-decoration:none; display:block; margin-top:20px;">Back to Dashboard</a>
        {{% if msg %}}<p style="color:var(--neon);">{{{{msg}}}}</p>{{% endif %}}
    </div></body></html>''', msg=msg)

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    f = request.files['file']
    f.save(os.path.join(CHUNKS_DIR, f"{request.form.get('fid')}_{request.form.get('index')}"))
    return "OK"

@app.route('/assemble', methods=['POST'])
def assemble():
    fid, name, total = request.form.get('fid'), secure_filename(request.form.get('name')), int(request.form.get('total'))
    filepath = os.path.join(UPLOAD_FOLDER, f"{datetime.now().strftime('%m%d_%H%M')}_{name}")
    with open(filepath, 'wb') as main:
        for i in range(total):
            chunk_path = os.path.join(CHUNKS_DIR, f"{fid}_{i}")
            if os.path.exists(chunk_path):
                with open(chunk_path, 'rb') as c: main.write(c.read())
                os.remove(chunk_path)
    return "OK"

@app.route('/download/<path:filename>')
def download(filename): return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/delete/<name>')
def delete(name):
    try: os.remove(os.path.join(UPLOAD_FOLDER, name))
    except: pass
    return redirect('/')

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

if __name__ == '__main__':
    from waitress import serve
    ip = get_ip()
    print(f"CodeX Vault Persistent Mode Active: http://{ip}:5000")
    serve(app, host='0.0.0.0', port=5000, threads=12, channel_timeout=300)