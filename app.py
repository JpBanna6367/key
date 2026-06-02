#!/usr/bin/env python3
# 🦅 KEY GENERATOR + UP4EVER UPLOAD SERVER

from flask import Flask, request, jsonify, render_template_string, session, redirect
import requests
import random
import string
import time
import json
import os
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "6367824530"

# ==================== CONFIG ====================
KEYS_FILE = "keys.json"
USERS_FILE = "users.json"
COUNTER_FILE = "counter.json"
ACCESS_HOURS = 6
ADMIN_USER = "Jitendar"
ADMIN_PASS = "Jitendar"

# Up4ever Config
SESS_ID = "yy2tn7laj2uzm7xa"
SID = "686591040774"
UPLOAD_HOST = "https://s13.up4ever.download"
BASE_URL = "https://www.up-4ever.net"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 15) Chrome/148.0",
    "Origin": BASE_URL,
    "X-Requested-With": "Banna.com",
    "Referer": f"{BASE_URL}/upload/",
}

COOKIES = {
    "xfss": SESS_ID,
    "login": "jitendar123bana",
}

# ==================== FILE HANDLERS ====================
def load_counter():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r') as f:
            return json.load(f)
    return {"count": 0}

def save_counter(counter):
    with open(COUNTER_FILE, 'w') as f:
        json.dump(counter, f)

def get_next_key_number():
    """Get next key number: 1, 2, 3..."""
    counter = load_counter()
    counter["count"] = counter.get("count", 0) + 1
    save_counter(counter)
    return counter["count"]

def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_keys(keys):
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, indent=4)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def generate_random_key():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def upload_to_up4ever(key_content, file_number):
    """Upload key to Up4ever - filename: key1.txt, key2.txt..."""
    session = requests.Session()
    
    # ✅ Fixed filename format: key1.txt, key2.txt, key3.txt...
    filename = f"key{file_number}.txt"
    
    try:
        # Step 1: PUT file
        put_headers = HEADERS.copy()
        put_headers.update({
            "Content-Type": "application/octet-stream",
            "X-Upload-SID": SID,
        })
        
        resp = session.put(
            f"{UPLOAD_HOST}/cgi-bin/put_chunk.cgi",
            data=key_content.encode(),
            headers=put_headers,
            cookies=COOKIES,
            timeout=30
        )
        
        if resp.json().get("status") != "OK":
            print(f"[✗] PUT failed for {filename}: {resp.text}")
            return None
        
        # Step 2: Import file
        post_url = f"{UPLOAD_HOST}/cgi-bin/api.cgi"
        post_data = {
            "op": "import_file",
            "sid": SID,
            "fname": filename,
            "sess_id": SESS_ID,
            "utype": "reg",
            "link_rcpt": "",
            "link_pass": "",
            "to_folder": "",
            "tos": "",
            "file_descr": "",
            "file_public": "1"
        }
        
        post_headers = HEADERS.copy()
        post_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        
        resp = session.post(post_url, data=post_data, headers=post_headers, cookies=COOKIES, timeout=30)
        result = resp.json()
        
        if result.get("status") == "OK":
            file_code = result.get("file_code")
            download_url = f"{BASE_URL}/{file_code}"
            print(f"[✓] {filename} -> {download_url}")
            return download_url
        
        print(f"[✗] Import failed for {filename}: {resp.text}")
        return None
        
    except Exception as e:
        print(f"[✗] Error uploading {filename}: {e}")
        return None

# ==================== MAIN API ====================
@app.route('/')
def home():
    return jsonify({"service": "Key Generator + Up4ever", "status": "running"})

@app.route('/get-key', methods=['GET', 'POST'])
def get_key():
    if request.method == 'GET':
        hwid = request.args.get('hwid')
        script = request.args.get('script', 'default')
    else:
        data = request.json or {}
        hwid = data.get('hwid')
        script = data.get('script', 'default')
    
    if not hwid:
        return jsonify({"status": "error", "message": "HWID required"}), 400
    
    users = load_users()
    keys = load_keys()
    current_time = time.time()
    
    # ===== CHECK IF USER ALREADY HAS ACTIVE ACCESS =====
    if hwid in users:
        user_data = users[hwid]
        if user_data.get("access_until", 0) > current_time:
            current_key = user_data.get("current_key")
            if current_key and current_key in keys:
                key_data = keys[current_key]
                return jsonify({
                    "status": "success",
                    "key_url": key_data.get("url"),
                    "expires_in_hours": round((user_data["access_until"] - current_time) / 3600, 1),
                    "message": "Your current key (still active)"
                })
    
    # ===== FIND EXISTING UNUSED KEY =====
    user_used_keys = users.get(hwid, {}).get("used_keys", [])
    
    for key_id, key_data in keys.items():
        if key_id not in user_used_keys and key_data.get("url"):
            if hwid not in users:
                users[hwid] = {}
            
            users[hwid]["current_key"] = key_id
            users[hwid]["access_until"] = current_time + (ACCESS_HOURS * 3600)
            users[hwid]["used_keys"] = user_used_keys + [key_id]
            users[hwid]["active_script"] = script
            save_users(users)
            
            return jsonify({
                "status": "success",
                "key_url": key_data.get("url"),
                "expires_in_hours": ACCESS_HOURS,
                "message": "Existing key assigned"
            })
    
    # ===== GENERATE NEW KEY + UPLOAD =====
    new_key = generate_random_key()
    file_number = get_next_key_number()  # Auto increment: 1,2,3...
    
    # Upload with filename: key1.txt, key2.txt...
    key_url = upload_to_up4ever(new_key, file_number)
    
    if not key_url:
        return jsonify({"status": "error", "message": "Failed to upload"}), 500
    
    # Save key
    keys[new_key] = {
        "url": key_url,
        "file_number": file_number,
        "filename": f"key{file_number}.txt",
        "created_at": current_time,
        "used_by": []
    }
    save_keys(keys)
    
    # Assign to user
    if hwid not in users:
        users[hwid] = {}
    
    users[hwid]["current_key"] = new_key
    users[hwid]["access_until"] = current_time + (ACCESS_HOURS * 3600)
    users[hwid]["used_keys"] = user_used_keys + [new_key]
    users[hwid]["active_script"] = script
    save_users(users)
    
    return jsonify({
        "status": "success",
        "key_url": key_url,
        "key_number": file_number,
        "expires_in_hours": ACCESS_HOURS,
        "message": f"Key uploaded as key{file_number}.txt"
    })

@app.route('/verify-key', methods=['POST'])
def verify_key():
    data = request.json or {}
    user_key = data.get("key", "").strip()
    hwid = data.get("hwid")
    script = data.get("script", "default")
    
    keys = load_keys()
    users = load_users()
    current_time = time.time()
    
    if user_key not in keys:
        return jsonify({"status": "error", "valid": False, "message": "Invalid key"}), 404
    
    key_data = keys[user_key]
    
    if hwid and hwid not in key_data.get("used_by", []):
        key_data["used_by"].append(hwid)
        save_keys(keys)
    
    if hwid:
        if hwid not in users:
            users[hwid] = {}
        
        if user_key not in users[hwid].get("used_keys", []):
            users[hwid]["used_keys"] = users[hwid].get("used_keys", []) + [user_key]
        
        users[hwid]["access_until"] = current_time + (ACCESS_HOURS * 3600)
        users[hwid]["current_key"] = user_key
        users[hwid]["active_script"] = script
        save_users(users)
    
    return jsonify({"status": "success", "valid": True, "message": "Key verified!"})

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    data = request.json or {}
    hwid = data.get('hwid')
    script = data.get('script', 'unknown')
    
    if not hwid:
        return jsonify({"status": "error", "message": "HWID required"}), 400
    
    users = load_users()
    current_time = time.time()
    
    if hwid not in users:
        users[hwid] = {}
    
    users[hwid]["last_heartbeat"] = current_time
    users[hwid]["active_script"] = script
    users[hwid]["heartbeat_count"] = users[hwid].get("heartbeat_count", 0) + 1
    
    save_users(users)
    
    return jsonify({"status": "success", "timestamp": current_time})

# ==================== ADMIN DASHBOARD ====================
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            background: linear-gradient(135deg, #0a0a1a, #1a1a3a);
            display: flex; justify-content: center; align-items: center;
            height: 100vh; font-family: Arial;
        }
        .login-box {
            background: rgba(255,255,255,0.1); padding: 40px;
            border-radius: 20px; width: 300px;
        }
        input {
            width: 100%; padding: 10px; margin: 10px 0;
            background: rgba(255,255,255,0.2); border: 1px solid #00ff9d;
            color: white; border-radius: 5px;
        }
        button {
            width: 100%; padding: 10px; background: #00ff9d;
            color: black; border: none; border-radius: 5px; cursor: pointer;
        }
        h2 { color: #00ff9d; text-align: center; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🦅 Admin Login</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: linear-gradient(135deg, #0a0a1a, #1a1a3a); color: white; font-family: Arial; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #00ff9d, #00bfff); padding: 20px; border-radius: 15px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { color: black; }
        .logout-btn { background: #ff4444; padding: 10px 20px; border-radius: 10px; text-decoration: none; color: white; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 15px; text-align: center; }
        .stat-card h3 { font-size: 32px; color: #00ff9d; }
        .section { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; margin-bottom: 20px; }
        .section h2 { color: #00ff9d; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { background: rgba(0,255,157,0.2); }
        .btn { background: #00ff9d; color: black; padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer; }
        input { background: rgba(255,255,255,0.1); border: 1px solid #00ff9d; padding: 8px; color: white; border-radius: 5px; width: 100px; }
        .key-list, .user-list { max-height: 400px; overflow-y: auto; }
        .status-active { color: #00ff9d; }
        .status-inactive { color: #ff4444; }
        a { color: #00ff9d; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🦅 Key Generator + Up4ever</h1>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card"><h3>{{ stats.total_keys }}</h3><p>Total Keys</p></div>
            <div class="stat-card"><h3>{{ stats.active_users }}</h3><p>🟢 Active</p></div>
            <div class="stat-card"><h3>{{ stats.total_users }}</h3><p>Users</p></div>
            <div class="stat-card"><h3>{{ stats.heartbeats }}</h3><p>Heartbeats(24h)</p></div>
        </div>
        
        <div class="section">
            <h2>➕ Generate & Upload Keys</h2>
            <form method="POST" action="/admin/generate" style="display: flex; gap: 10px; align-items: center;">
                <input type="number" name="count" value="5" min="1" max="50">
                <span>keys</span>
                <button type="submit" class="btn">Generate & Upload</button>
            </form>
        </div>
        
        <div class="section">
            <h2>📋 All Keys ({{ keys|length }})</h2>
            <div class="key-list">
                <table>
                    <tr><th>Key</th><th>File #</th><th>Filename</th><th>Up4ever URL</th><th>Users</th></tr>
                    {% for key, data in keys.items() %}
                    <tr>
                        <td>{{ key }}</td>
                        <td>#{{ data.get('file_number', '?') }}</td>
                        <td>{{ data.get('filename', '?') }}</td>
                        <td><a href="{{ data.url }}" target="_blank">{{ data.url[:45] }}...</a></td>
                        <td>{{ data.used_by|length }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
        
        <div class="section">
            <h2>👥 Users ({{ users|length }})</h2>
            <div class="user-list">
                <table>
                    <tr><th>HWID</th><th>Key</th><th>Script</th><th>Access Until</th><th>Status</th><th>Heartbeats</th></tr>
                    {% for hwid, data in users.items() %}
                    <tr>
                        <td style="font-size:11px;">{{ hwid[:15] }}...</td>
                        <td>{{ data.get('current_key', '-') }}</td>
                        <td>{{ data.get('active_script', '?') }}</td>
                        <td>{{ data.get('access_until_str', '-') }}</td>
                        <td>{% if data.get('access_until', 0) > current_time %}<span class="status-active">🟢</span>{% else %}<span class="status-inactive">🔴</span>{% endif %}</td>
                        <td>{{ data.get('heartbeat_count', 0) }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect('/dashboard')
        return "Invalid credentials", 403
    return render_template_string(LOGIN_PAGE)

@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    keys = load_keys()
    users = load_users()
    current_time = time.time()
    
    active_users = sum(1 for d in users.values() if d.get("access_until", 0) > current_time)
    heartbeats_24h = sum(1 for d in users.values() if d.get("last_heartbeat", 0) > current_time - 86400)
    
    users_display = {}
    for hwid, data in users.items():
        users_display[hwid] = {
            "current_key": data.get("current_key", "-"),
            "active_script": data.get("active_script", "unknown"),
            "access_until_str": datetime.fromtimestamp(data.get("access_until", 0)).strftime("%Y-%m-%d %H:%M") if data.get("access_until") else "-",
            "access_until": data.get("access_until", 0),
            "heartbeat_count": data.get("heartbeat_count", 0)
        }
    
    stats = {
        "total_keys": len(keys),
        "active_users": active_users,
        "total_users": len(users),
        "heartbeats": heartbeats_24h
    }
    
    return render_template_string(DASHBOARD_HTML, keys=keys, users=users_display, stats=stats, current_time=current_time)

@app.route('/admin/generate', methods=['POST'])
def admin_generate():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    count = int(request.form.get('count', 5))
    keys = load_keys()
    current_time = time.time()
    
    for _ in range(count):
        new_key = generate_random_key()
        file_number = get_next_key_number()
        
        key_url = upload_to_up4ever(new_key, file_number)
        
        if key_url:
            keys[new_key] = {
                "url": key_url,
                "file_number": file_number,
                "filename": f"key{file_number}.txt",
                "created_at": current_time,
                "used_by": []
            }
    
    save_keys(keys)
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/admin')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
