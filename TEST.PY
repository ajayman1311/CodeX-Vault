import os
import json
import socket
import time
import shutil
import zipfile
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, session, send_file
from werkzeug.utils import secure_filename
from plyer import notification

app = Flask(__name__)
app.secret_key = 'codex_vault_atomic_final_2026_fixed'

# --- 1. CONFIGURATION & SESSION ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=120)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'vault_files')
CHUNKS_DIR = os.path.join(BASE_DIR, 'temp_chunks')
CONFIG_FILE = os.path.join(BASE_DIR, 'vault_settings.json')

def ensure_dirs():
    for d in [UPLOAD_FOLDER, CHUNKS_DIR]:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

ensure_dirs()

# --- 2. HELPERS ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {'password': '', 'protection_key': ''}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        return ip
    except: return "127.0.0.1"

def smart_cleanup():
    now = time.time()
    if os.path.exists(CHUNKS_DIR):
        for f in os.listdir(CHUNKS_DIR):
            fp = os.path.join(CHUNKS_DIR, f)
            if os.stat(fp).st_mtime < now - 86400:
                try: os.remove(fp)
                except: pass

smart_cleanup()

# --- 3. UI COMPONENTS (MOBILE RESPONSIVE) ---
UI_SHARED = '''
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    :root { 
        --neon: #00f2ff; --bg: #000; --card: rgba(255, 255, 255, 0.05);
        --border: rgba(255, 255, 255, 0.15); --text: #fff;
        --grad: radial-gradient(at 0% 0%, rgba(0, 119, 255, 0.2) 0px, transparent 50%), radial-gradient(at 100% 100%, rgba(0, 242, 255, 0.15) 0px, transparent 50%);
    }
    body.light-mode {
        --bg: #f4f7f6; --card: rgba(255, 255, 255, 0.8);
        --text: #1a1a1a; --border: rgba(0, 0, 0, 0.1); --grad: none;
    }
    body { 
        margin: 0; background: var(--bg); background-image: var(--grad); 
        color: var(--text); font-family: 'Segoe UI', sans-serif; min-height: 100vh; 
        display: flex; flex-direction: column; align-items: center; transition: 0.3s;
    }
    .glass-card { 
        background: var(--card); backdrop-filter: blur(45px) saturate(180%); 
        border: 1px solid var(--border); border-radius: 30px; padding: 30px; 
        width: 90%; max-width: 800px; box-shadow: 0 25px 50px rgba(0,0,0,0.6); 
        text-align: center; margin-top: 20px; margin-bottom: 20px;
    }
    .logo { font-size: 24px; font-weight: 900; color: var(--neon); letter-spacing: 4px; text-transform: uppercase; margin-bottom: 20px; }
    input { 
        background: rgba(255, 255, 255, 0.07); border: 1px solid var(--border); 
        color: var(--text); padding: 15px; border-radius: 12px; width: 100%; margin-bottom: 15px; box-sizing: border-box;
    }
    .btn { 
        background: var(--neon); color: #000; border: none; padding: 12px 20px; 
        border-radius: 12px; font-weight: bold; cursor: pointer; transition: 0.3s; text-decoration: none; display: inline-block;
    }
    .btn:active { transform: scale(0.95); }
    .file-item { 
        background: rgba(255,255,255,0.02); margin-bottom: 12px; padding: 15px; 
        border-radius: 18px; display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--border);
    }
    /* Mobile Specific Layout */
    @media (max-width: 500px) {
        .glass-card { padding: 20px; width: 85%; border-radius: 20px; }
        header { flex-direction: column; gap: 15px; }
        .header-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
        .header-actions .btn { font-size: 11px; padding: 10px 5px; text-align: center; }
        .file-item { flex-direction: column; align-items: flex-start; gap: 12px; }
        .file-actions { align-self: flex-end; display: flex; gap: 20px; }
        .logo { font-size: 18px; }
    }
    .prog-wrapper { width: 100%; margin: 20px 0; display: none; text-align: left; }
    .prog-container { height: 8px; background: rgba(255,255,255,0.05); border-radius: 10px; overflow: hidden; }
    .prog-bar { height: 100%; width: 0%; background: var(--neon); transition: 0.4s; }
    .status-msg { font-size: 11px; margin-top: 8px; font-weight: bold; color: var(--neon); }
    .theme-toggle { position: fixed; bottom: 20px; right: 20px; cursor: pointer; font-size: 28px; z-index: 100; background: var(--card); padding: 10px; border-radius: 50%; border: 1px solid var(--border); }
    .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(10px); }
    .modal-content { background: var(--bg); border: 1px solid var(--neon); border-radius: 25px; width: 85%; max-width: 350px; margin: 30% auto; padding: 30px; text-align: center; }
</style>
'''

# --- 4. ACCESS CONTROL ---
@app.before_request
def handle_access():
    session.permanent = True
    conf = load_config()
    public = ['setup', 'login', 'recovery', 'static', 'notify_success']
    if not conf['password'] and request.endpoint != 'setup': return redirect(url_for('setup'))
    if conf['password'] and not session.get('auth') and request.endpoint not in public:
        return redirect(url_for('login'))

# --- 5. ROUTES ---

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if load_config()['password']: return redirect(url_for('login'))
    if request.method == 'POST':
        save_config({'password': request.form.get('np'), 'protection_key': request.form.get('npk')})
        return redirect(url_for('login'))
    return render_template_string(f'<html><head>{UI_SHARED}</head><body><div class="glass-card" style="max-width:400px;"><div class="logo">VAULT SETUP</div><form method="post"><input type="password" name="np" placeholder="Set Key" required><input type="password" name="npk" placeholder="Set Recovery ID" required><button class="btn" style="width:100%;">ACTIVATE</button></form></div></body></html>')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('auth'): return redirect('/')
    error = None
    if request.method == 'POST':
        if request.form.get('p') == load_config()['password']:
            session['auth'] = True; return redirect('/')
        error = "WRONG KEY"
    return render_template_string(f'''
<html>
<head>
    {UI_SHARED}
    <link href="https://fonts.googleapis.com/css2?family=Russo+One&display=swap" rel="stylesheet">
    <style>
        .logo {{
            font-family: 'Russo One', sans-serif;
            font-size: 28px;
            letter-spacing: 1px;
            color: #ffffff;
            margin-bottom: 20px;
            text-transform: none !important; /* Ensure case sensitivity */
        }}
        .x-red {{
            color: #ff4d4d;
        }}
    </style>
</head>
<body>
    <div class="glass-card" style="max-width:400px;">
        <div class="logo">Code<span class="x-red">X</span> VAULT</div>
        <form method="post">
            <input type="password" name="p" placeholder="Enter Key" required>
            <button class="btn" style="width:100%;">UNLOCK</button>
        </form>
        {{% if error %}}
            <p style="color:#ff4d4d; font-size:12px; margin-top:10px;">{{{{error}}}}</p>
        {{% endif %}}
    </div>
    <a href="/recovery" style="color:gray; font-size:12px; margin-top:10px; text-decoration:none;">Forget Password?</a>
</body>
</html>
''', error=error)

@app.route('/')
def index():
    items = []
    ensure_dirs()
    for entry in os.listdir(UPLOAD_FOLDER):
        full_p = os.path.join(UPLOAD_FOLDER, entry)
        items.append({
            'raw': entry,
            'name': entry.split('_', 1)[-1] if '_' in entry else entry,
            'type': 'folder' if os.path.isdir(full_p) else 'file',
            'time': datetime.fromtimestamp(os.path.getmtime(full_p)).strftime('%y-%m-%d %H:%M')
        })
    items.sort(key=lambda x: x['time'], reverse=True)
    return render_template_string('''
    <html><head>''' + UI_SHARED + '''</head><body>
    <div class="theme-toggle" onclick="toggleMode()" id="theme-icon">☀️</div>
    
    <div id="codexModal" class="modal">
        <div class="modal-content">
            <div class="logo" style="font-size:16px;">Authorization</div>
            <p id="modalInfo" style="font-size:12px; margin-bottom:20px; opacity:0.8;"></p>
            <div style="display:flex; gap:10px; justify-content:center;">
                <button class="btn" id="startSync" style="flex:1;">START</button>
                <button class="btn" id="cancelSync" style="background:none; border:1px solid #ff4d4d; color:#ff4d4d; flex:1;">CANCEL</button>
            </div>
        </div>
    </div>

    <div class="glass-card">
        <header style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:15px; margin-bottom:20px;">
           <!-- Font link (Head section mein daalein) -->
<link href="https://fonts.googleapis.com/css2?family=Russo+One&display=swap" rel="stylesheet">

<!-- Logo Code -->
<div class="logo" style="
    margin: 0; 
    font-family: 'Russo One', sans-serif; 
    font-size: 48px; 
    text-transform: none; 
    letter-spacing: 1px;
    color: white; 
    # background-color: #111; 
    padding: 10px 20px; 
    display: inline-block;
">
    Code<span style="color: #ff0000;">X</span>
</div>
            <div class="header-actions">
                <label class="btn">FILE + <input type="file" id="u-file" multiple style="display:none;"></label>
                <label class="btn" style="background:#ffcc00;">FOLDER + <input type="file" id="u-folder" webkitdirectory directory multiple style="display:none;"></label>
                <a href="/settings" class="btn" style="background:none; border:1px solid var(--border); color:var(--text);">⚙️</a>
                <a href="/logout" class="btn" style="background:none; border:1px solid #ff4d4d; color:#ff4d4d;">Logout</a>
            </div>
        </header>

        <div class="prog-wrapper" id="p-wrapper">
            <div style="display:flex; justify-content:space-between; font-size:10px; margin-bottom:5px;">
                <span id="p-name" style="color:var(--neon); font-weight:bold;"></span>
                <span id="p-count"></span>
            </div>
            <div class="prog-container"><div class="prog-bar" id="p-bar"></div></div>
            <div class="status-msg" id="p-text">Linking...</div>
        </div>

        <div id="file-list">
            {% for i in items %}
            <div class="file-item">
                <div style="text-align:left;">
                    <b style="color:var(--text); font-size:14px;">{% if i.type == 'folder' %}📁{% else %}📄{% endif %} {{ i.name }}</b><br>
                    <small style="color:gray; font-size:10px;">{{ i.time }}</small>
                </div>
                <div class="file-actions">
                    <a href="/download/{{ i.raw }}" style="color:var(--neon); text-decoration:none; font-weight:bold;">GET</a>
                    <a href="/delete/{{ i.raw }}" style="color:#ff4d4d; text-decoration:none;">✕</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
        let isSyncing = false;
        let globalFiles = [];

        const closeModal = () => {
            if(isSyncing) return;
            document.getElementById("codexModal").style.display = "none";
        };

        const initSync = (e) => {
            if(isSyncing) return;
            const files = e.target.files;
            if(!files.length) return;
            globalFiles = Array.from(files);
            document.getElementById("modalInfo").innerText = `Sync ${globalFiles.length} items?`;
            document.getElementById("codexModal").style.display = "block";
        };

        document.getElementById("u-file").onchange = initSync;
        document.getElementById("u-folder").onchange = initSync;
        document.getElementById("cancelSync").onclick = closeModal;

        document.getElementById("startSync").onclick = async function() {
            if(isSyncing) return;
            isSyncing = true;
            this.disabled = true;
            document.getElementById("codexModal").style.display = "none";
            document.getElementById("p-wrapper").style.display = "block";
            const sid = Math.floor(Date.now() / 1000);

            for(let j=0; j < globalFiles.length; j++) {
                const f = globalFiles[j];
                const path = f.webkitRelativePath || f.name;
                const fid = btoa(path + f.size).substring(0, 12);
                document.getElementById("p-name").innerText = path.substring(0,20)+"...";
                document.getElementById("p-count").innerText = `${j+1}/${globalFiles.length}`;

                const CHUNK = 1024 * 1024 * 2;
                const total = Math.ceil(f.size / CHUNK);
                let done = [];
                try {
                    const check = await fetch(`/check_progress?fid=${fid}`);
                    done = await check.json();
                } catch(e) {}

                for (let i = 0; i < total; i++) {
                    if (done.includes(i.toString())) continue;
                    let ok = false;
                    while(!ok) {
                        const fd = new FormData();
                        fd.append("file", f.slice(i * CHUNK, (i + 1) * CHUNK));
                        fd.append("fid", fid); fd.append("index", i);
                        try {
                            const res = await fetch("/upload_chunk", { method: "POST", body: fd });
                            if(res.ok) { ok = true; 
                                let p = Math.round(((i+1)/total)*100);
                                document.getElementById("p-bar").style.width = p + "%";
                                document.getElementById("p-text").innerText = `Moving: ${p}%`;
                            } else throw "e";
                        } catch { await new Promise(r => setTimeout(r, 2000)); }
                    }
                }
                await fetch("/assemble", { method: "POST", body: new URLSearchParams({fid, path, total, sid}) });
            }
            fetch("/notify_success");
            location.reload();
        };

        function toggleMode() {
            document.body.classList.toggle('light-mode');
            localStorage.setItem('vault-theme', document.body.classList.contains('light-mode') ? 'light' : 'dark');
        }
        if(localStorage.getItem('vault-theme') === 'light') document.body.classList.add('light-mode');
    </script></body></html>''', items=items)

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    f, fid, idx = request.files['file'], request.form.get('fid'), request.form.get('index')
    f.save(os.path.join(CHUNKS_DIR, f"{fid}_{idx}"))
    return "OK"

@app.route('/assemble', methods=['POST'])
def assemble():
    fid, rel_path, total = request.form.get('fid'), request.form.get('path'), int(request.form.get('total'))
    sid = request.form.get('sid')
    parts = rel_path.split('/')
    session_root = f"{sid}_{secure_filename(parts[0])}"
    if len(parts) > 1:
        sub_p = os.path.join(*[secure_filename(p) for p in parts[1:]])
        final_p = os.path.join(UPLOAD_FOLDER, session_root, sub_p)
    else:
        final_p = os.path.join(UPLOAD_FOLDER, f"{sid}_{secure_filename(rel_path)}")
    os.makedirs(os.path.dirname(final_p), exist_ok=True)
    with open(final_p, 'wb') as main:
        for i in range(total):
            cp = os.path.join(CHUNKS_DIR, f"{fid}_{i}")
            if os.path.exists(cp):
                with open(cp, 'rb') as c: main.write(c.read())
                try: os.remove(cp)
                except: pass
    return "OK"

@app.route('/notify_success')
def notify_success():
    try: notification.notify(title="Vault", message="Task Complete!", timeout=2)
    except: pass
    return "OK"

@app.route('/download/<path:item>')
def download(item):
    p = os.path.join(UPLOAD_FOLDER, item)
    if os.path.isdir(p):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(p):
                for f in files:
                    fp = os.path.join(root, f)
                    zf.write(fp, os.path.relpath(fp, p))
        buf.seek(0)
        return send_file(buf, download_name=f"{item.split('_',1)[-1]}.zip", as_attachment=True)
    return send_from_directory(UPLOAD_FOLDER, item, as_attachment=True)

@app.route('/delete/<path:item>')
def delete(item):
    p = os.path.join(UPLOAD_FOLDER, item)
    # FIX: Add check to prevent FileNotFoundError
    if os.path.exists(p):
        if os.path.isdir(p): shutil.rmtree(p)
        else: os.remove(p)
    return redirect('/')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conf = load_config(); msg = None
    if request.method == 'POST':
        if request.form.get('np'): conf['password'] = request.form.get('np')
        if request.form.get('npk'): conf['protection_key'] = request.form.get('npk')
        save_config(conf); msg = "UPDATED"
    return render_template_string(f'<html><head>{UI_SHARED}</head><body><div class="glass-card" style="max-width:400px;"><div class="logo">SETTINGS</div><form method="post"><input type="password" name="np" placeholder="Key"><input type="password" name="npk" placeholder="Recovery ID"><button class="btn" style="width:100%;">SAVE</button></form><a href="/" style="display:block; margin-top:20px; color:gray; text-decoration:none;">Back</a>{{% if msg %}}<p style="color:var(--neon);">{{{{msg}}}}</p>{{% endif %}}</div></body></html>', msg=msg)

@app.route('/recovery', methods=['GET', 'POST'])
def recovery():
    if request.method == 'POST':
        if request.form.get('pk') == load_config()['protection_key']:
            session['auth'] = True; return redirect('/settings')
    return render_template_string(f'<html><head>{UI_SHARED}</head><body><div class="glass-card" style="max-width:400px;"><div class="logo" style="color:red;">RECOVERY</div><form method="post"><input type="password" name="pk" placeholder="Recovery ID" required><button class="btn" style="width:100%; background:red; color:white;">VERIFY</button></form></div></body></html>')

@app.route('/check_progress')
def check_progress():
    fid = request.args.get('fid')
    try: return json.dumps([f.split('_')[1] for f in os.listdir(CHUNKS_DIR) if f.startswith(fid)])
    except: return json.dumps([])

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

if __name__ == '__main__':
    from waitress import serve
    print(f"CodeX Vault ACTIVE at http://{get_ip()}:5000")
    serve(app, host='0.0.0.0', port=5000, threads=12)
