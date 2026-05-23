#!/usr/bin/env python3

from flask import Flask, request, jsonify, render_template_string, session, redirect
import requests
import random
import string
import time
import json
import os
import hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = "6367824530"

# ==================== CONFIG ====================
KEYS_FILE = "keys.json"
USERS_FILE = "users.json"
ACCESS_HOURS = 6
ADMIN_USER = "Jitendar"
ADMIN_PASS = "Jitendar"

# exe.io API
EXE_API = "https://exe.io/api"
EXE_TOKEN = "b71208faade6ab1d34e6f60a5b6f13230b629fb6"
NOTES_SITE = "https://key-genrater.onrender.com"

# ==================== FILE HANDLERS ====================
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

def create_note_on_site(key):
    try:
        resp = requests.post(f"{NOTES_SITE}/api/create", 
                            json={"text": key}, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("url")
    except:
        pass
    return None

def exe_shorten(url):
    try:
        api_url = f"{EXE_API}?api={EXE_TOKEN}&url={url}"
        resp = requests.get(api_url, timeout=30)
        result = resp.json()
        if result.get("status") == "error":
            return None
        else:
            return result.get("shortenedUrl") or result.get("shortlink")
    except:
        return None

# ==================== MAIN API ====================
@app.route('/')
def home():
    return jsonify({"service": "Key Generator", "status": "running"})

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
    
    # ===== STEP 1: Check if user already has ACTIVE access =====
    if hwid in users:
        user_data = users[hwid]
        if user_data.get("access_until", 0) > current_time:
            # User still has access, return same key
            current_key = user_data.get("current_key")
            if current_key and current_key in keys:
                key_data = keys[current_key]
                return jsonify({
                    "status": "success",
                    "key_url": key_data.get("url"),
                    "expires_in": round((user_data["access_until"] - current_time) / 3600, 1),
                    "message": "Your current key (still active)"
                })
    
    # ===== STEP 2: Find key that this user has NOT used =====
    user_used_keys = users.get(hwid, {}).get("used_keys", [])
    
    for key_id, key_data in keys.items():
        if key_id not in user_used_keys:
            # This key is available for this user
            # Assign to user
            if hwid not in users:
                users[hwid] = {}
            
            users[hwid]["current_key"] = key_id
            users[hwid]["access_until"] = current_time + (ACCESS_HOURS * 3600)
            users[hwid]["used_keys"] = user_used_keys + [key_id]
            save_users(users)
            
            return jsonify({
                "status": "success",
                "key_url": key_data.get("url"),
                "expires_in_hours": ACCESS_HOURS,
                "message": "Existing key assigned"
            })
    
    # ===== STEP 3: User has used ALL keys, generate new =====
    new_key = generate_random_key()
    
    # Create note
    note_url = create_note_on_site(new_key)
    if not note_url:
        note_url = f"{NOTES_SITE}/note/{new_key}"
    
    # Shorten with exe.io
    final_url = exe_shorten(note_url)
    if not final_url:
        final_url = note_url
    
    # Save key
    keys[new_key] = {
        "url": final_url,
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
    save_users(users)
    
    return jsonify({
        "status": "success",
        "key_url": final_url,
        "expires_in_hours": ACCESS_HOURS,
        "message": "New key generated"
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
    
    # Mark this key as used by this user
    if hwid not in key_data.get("used_by", []):
        key_data["used_by"].append(hwid)
        save_keys(keys)
    
    # Update user's used keys
    if hwid not in users:
        users[hwid] = {}
    
    if user_key not in users[hwid].get("used_keys", []):
        users[hwid]["used_keys"] = users[hwid].get("used_keys", []) + [user_key]
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

# ==================== ADMIN ROUTES ====================
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <style>
        body {
            background: linear-gradient(135deg, #0a0a1a, #1a1a3a);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-family: Arial;
        }
        .login-box {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 20px;
            width: 300px;
        }
        input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            background: rgba(255,255,255,0.2);
            border: 1px solid #00ff9d;
            color: white;
            border-radius: 5px;
        }
        button {
            width: 100%;
            padding: 10px;
            background: #00ff9d;
            color: black;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        h2 { color: #00ff9d; text-align: center; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>Admin Login</h2>
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
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0a1a, #1a1a3a);
            color: white;
            font-family: 'Segoe UI', Arial;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: linear-gradient(135deg, #00ff9d, #00bfff);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { color: black; }
        .logout-btn {
            background: #ff4444;
            padding: 10px 20px;
            border-radius: 10px;
            text-decoration: none;
            color: white;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
        }
        .stat-card h3 { font-size: 32px; color: #00ff9d; }
        .section {
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
        }
        .section h2 { color: #00ff9d; margin-bottom: 15px; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th { background: rgba(0,255,157,0.2); }
        .btn {
            background: #00ff9d;
            color: black;
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        input {
            background: rgba(255,255,255,0.1);
            border: 1px solid #00ff9d;
            padding: 8px;
            color: white;
            border-radius: 5px;
        }
        .key-list { max-height: 400px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔑 Key Generator Admin</h1>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card"><h3>{{ stats.total_keys }}</h3><p>Total Keys</p></div>
            <div class="stat-card"><h3>{{ stats.active_users }}</h3><p>Active Users</p></div>
            <div class="stat-card"><h3>{{ stats.total_users }}</h3><p>Total Users</p></div>
            <div class="stat-card"><h3>{{ stats.heartbeats }}</h3><p>Heartbeats (24h)</p></div>
        </div>
        
        <div class="section">
            <h2>➕ Generate New Keys</h2>
            <form method="POST" action="/admin/generate" style="display: flex; gap: 10px;">
                <input type="number" name="count" value="5" style="width: 100px;">
                <button type="submit" class="btn">Generate Keys</button>
            </form>
        </div>
        
        <div class="section">
            <h2>📋 All Keys</h2>
            <div class="key-list">
                <table>
                    <tr><th>Key</th><th>URL</th><th>Used By (HWID)</th><th>Users Count</th></tr>
                    {% for key, data in keys.items() %}
                    <tr>
                        <td>{{ key }}</td>
                        <td><a href="{{ data.url }}" target="_blank" style="color:#00ff9d;">Link</a></td>
                        <td style="font-size:11px;">{{ data.used_by|join(', ') }}</td>
                        <td>{{ data.used_by|length }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
        
        <div class="section">
            <h2>👥 Active Users</h2>
            <table>
                <tr><th>HWID</th><th>Current Key</th><th>Access Until</th><th>Script</th><th>Heartbeats</th></tr>
                {% for hwid, data in users.items() %}
                <tr>
                    <td>{{ hwid[:16] }}...</td>
                    <td>{{ data.get('current_key', '-') }}</td>
                    <td>{{ data.get('access_until_str', '-') }}</td>
                    <td>{{ data.get('active_script', '-') }}</td>
                    <td>{{ data.get('heartbeat_count', 0) }}</td>
                </tr>
                {% endfor %}
            </table>
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
    
    # Calculate stats
    active_users = 0
    heartbeats_24h = 0
    
    for hwid, data in users.items():
        if data.get("access_until", 0) > current_time:
            active_users += 1
        if data.get("last_heartbeat", 0) > current_time - 86400:
            heartbeats_24h += 1
    
    # Format keys for display
    keys_display = {}
    for k, v in keys.items():
        keys_display[k] = {
            "url": v.get("url", ""),
            "used_by": v.get("used_by", [])
        }
    
    # Format users for display
    users_display = {}
    for hwid, data in users.items():
        users_display[hwid] = {
            "current_key": data.get("current_key", "-"),
            "access_until_str": datetime.fromtimestamp(data.get("access_until", 0)).strftime("%Y-%m-%d %H:%M") if data.get("access_until") else "-",
            "active_script": data.get("active_script", "-"),
            "heartbeat_count": data.get("heartbeat_count", 0)
        }
    
    stats = {
        "total_keys": len(keys),
        "active_users": active_users,
        "total_users": len(users),
        "heartbeats": heartbeats_24h
    }
    
    return render_template_string(DASHBOARD_HTML, keys=keys_display, users=users_display, stats=stats)

@app.route('/admin/generate', methods=['POST'])
def admin_generate():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    count = int(request.form.get('count', 5))
    keys = load_keys()
    current_time = time.time()
    
    for _ in range(count):
        new_key = generate_random_key()
        note_url = create_note_on_site(new_key)
        final_url = exe_shorten(note_url) if note_url else None
        
        keys[new_key] = {
            "url": final_url,
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
