#!/usr/bin/env python3

from flask import Flask, request, jsonify, render_template_string, session, redirect
import requests
import random
import string
import time
import json
import os
import hashlib
import uuid
import platform
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "6367824530"

# ==================== CONFIG ====================
KEYS_FILE = "keys.json"
USERS_FILE = "users.json"
KEY_VALIDITY = 6 * 3600
ADMIN_USER = "Jitendar"
ADMIN_PASS = "Jitendar"

# MRN API
MRN_API = "https://mrn-bypass-protect-bot-mrn-official.vercel.app/api"
MRN_KEY = "av_botz_3e8xS90YUZXlSCaLCrXREz9MQgwrt"
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

def mrn_shorten(url):
    try:
        resp = requests.get(MRN_API, params={"api": MRN_KEY, "url": url}, timeout=30)
        data = resp.json()
        return data.get("shortenedUrl") or data.get("shortlink")
    except:
        return None

# ==================== DEVICE LIST FUNCTIONS ====================
def get_device_list():
    """Get all devices with their status"""
    users = load_users()
    current_time = time.time()
    device_list = []
    
    for hwid, data in users.items():
        last_hb = data.get("last_heartbeat", 0)
        is_active = (current_time - last_hb) < 600  # 10 minutes = 600 seconds
        
        # Format HWID for display
        display_hwid = hwid[:16] + "..." if len(hwid) > 16 else hwid
        
        device_list.append({
            "hwid": display_hwid,
            "full_hwid": hwid,
            "script": data.get("active_script", "unknown"),
            "last_seen": datetime.fromtimestamp(last_hb).strftime("%Y-%m-%d %H:%M:%S") if last_hb else "Never",
            "is_active": is_active,
            "first_seen": datetime.fromtimestamp(data.get("first_seen", 0)).strftime("%Y-%m-%d %H:%M") if data.get("first_seen") else "Unknown",
            "heartbeat_count": data.get("heartbeat_count", 0),
            "key_used": data.get("used_key", False)
        })
    
    # Sort: active devices first, then by last seen
    device_list.sort(key=lambda x: (not x["is_active"], x["last_seen"]), reverse=False)
    return device_list

def get_stats():
    keys = load_keys()
    users = load_users()
    current_time = time.time()
    
    total_keys = len(keys)
    used_keys = sum(1 for k in keys.values() if k.get("used", False))
    unused_keys = total_keys - used_keys
    
    # Active devices (last 10 minutes)
    active_count = 0
    for hwid, data in users.items():
        if current_time - data.get("last_heartbeat", 0) < 600:
            active_count += 1
    
    # Keys generated today
    today_keys = 0
    for k, v in keys.items():
        if v.get("created_at", 0) > current_time - 86400:
            today_keys += 1
    
    # Keys generated last 7 days
    week_keys = 0
    for k, v in keys.items():
        if v.get("created_at", 0) > current_time - (7 * 86400):
            week_keys += 1
    
    # Total devices
    total_devices = len(users)
    
    return {
        "total_keys": total_keys,
        "used_keys": used_keys,
        "unused_keys": unused_keys,
        "active_devices": active_count,
        "total_devices": total_devices,
        "today_keys": today_keys,
        "week_keys": week_keys
    }

# ==================== ADMIN DASHBOARD HTML ====================
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
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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
        .stat-card p { color: #888; font-size: 14px; }
        .section {
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
        }
        .section h2 { color: #00ff9d; margin-bottom: 15px; border-left: 3px solid #00ff9d; padding-left: 15px; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th { background: rgba(0,255,157,0.2); color: #00ff9d; }
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
        .used { color: #ff4444; }
        .unused { color: #00ff9d; }
        .active { color: #00ff9d; font-weight: bold; }
        .inactive { color: #888; }
        .status-active { color: #00ff9d; }
        .status-inactive { color: #ff4444; }
        .key-list { max-height: 400px; overflow-y: auto; }
        .device-list { max-height: 400px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔑 Key Generator Admin</h1>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>{{ stats.total_keys }}</h3>
                <p>Total Keys</p>
            </div>
            <div class="stat-card">
                <h3>{{ stats.used_keys }}</h3>
                <p>Used Keys</p>
            </div>
            <div class="stat-card">
                <h3>{{ stats.unused_keys }}</h3>
                <p>Unused Keys</p>
            </div>
            <div class="stat-card">
                <h3>{{ stats.active_devices }}</h3>
                <p>🟢 Active Now (10 min)</p>
            </div>
            <div class="stat-card">
                <h3>{{ stats.total_devices }}</h3>
                <p>Total Devices</p>
            </div>
            <div class="stat-card">
                <h3>{{ stats.today_keys }}</h3>
                <p>Keys Today</p>
            </div>
            <div class="stat-card">
                <h3>{{ stats.week_keys }}</h3>
                <p>Keys This Week</p>
            </div>
        </div>
        
        <div class="section">
            <h2>📱 Device List ({{ device_list|length }} devices)</h2>
            <div class="device-list">
                <table>
                    <tr>
                        <th>Device ID</th>
                        <th>Script</th>
                        <th>Status</th>
                        <th>Last Seen</th>
                        <th>First Seen</th>
                        <th>Heartbeats</th>
                    </tr>
                    {% for device in device_list %}
                    <tr>
                        <td title="{{ device.full_hwid }}">{{ device.hwid }}</td>
                        <td>{{ device.script }}</td>
                        <td>{% if device.is_active %}<span class="status-active">🟢 Active</span>{% else %}<span class="status-inactive">🔴 Offline</span>{% endif %}</td>
                        <td>{{ device.last_seen }}</td>
                        <td>{{ device.first_seen }}</td>
                        <td>{{ device.heartbeat_count }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
        
        <div class="section">
            <h2>➕ Generate New Keys</h2>
            <form method="POST" action="/admin/generate" style="display: flex; gap: 10px; align-items: center;">
                <input type="number" name="count" value="5" style="width: 100px;">
                <button type="submit" class="btn">Generate Keys</button>
            </form>
        </div>
        
        <div class="section">
            <h2>📋 All Keys</h2>
            <div class="key-list">
                <table>
                    <tr>
                        <th>Key</th>
                        <th>URL</th>
                        <th>Status</th>
                        <th>Expiry</th>
                        <th>Used By</th>
                    </tr>
                    {% for key, data in keys.items() %}
                    <tr>
                        <td class="key-cell">{{ key }}</td>
                        <td><a href="{{ data.url }}" target="_blank" style="color:#00ff9d;">Link</a></td>
                        <td class="{% if data.used %}used{% else %}unused{% endif %}">{% if data.used %}USED{% else %}UNUSED{% endif %}</td>
                        <td>{{ data.expiry_date }}</td>
                        <td>{{ data.used_by_hwid or '-' }}</td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==================== API ROUTES ====================
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
    
    # Update user first_seen
    if hwid not in users:
        users[hwid] = {"first_seen": current_time}
    
    # Check existing key for this HWID + Script
    if script in users[hwid]:
        existing_key = users[hwid][script].get("key")
        if existing_key and existing_key in keys:
            key_info = keys[existing_key]
            if current_time < key_info.get("expiry", 0) and not key_info.get("used", False):
                return jsonify({
                    "status": "success",
                    "key_url": key_info.get("url"),
                    "expires_in": round((key_info["expiry"] - current_time) / 3600, 1)
                })
    
    # Find unused key
    unused_key = None
    for k, v in keys.items():
        if not v.get("used", False):
            unused_key = k
            break
    
    # Generate new if needed
    if not unused_key:
        unused_key = generate_random_key()
        note_url = create_note_on_site(unused_key)
        if not note_url:
            note_url = f"{NOTES_SITE}/note/{unused_key}"
        
        final_url = mrn_shorten(note_url)
        if not final_url:
            final_url = note_url
        
        keys[unused_key] = {
            "used": False,
            "created_at": current_time,
            "expiry": current_time + KEY_VALIDITY,
            "url": final_url
        }
        save_keys(keys)
    
    # Assign key to this HWID + Script
    if script not in users[hwid]:
        users[hwid][script] = {}
    
    users[hwid][script]["key"] = unused_key
    users[hwid][script]["assigned_at"] = current_time
    
    save_users(users)
    
    return jsonify({
        "status": "success",
        "key_url": keys[unused_key]["url"],
        "expires_in_hours": 6
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
    
    if key_data.get("used", False):
        return jsonify({"status": "error", "valid": False, "message": "Key already used"}), 403
    
    if current_time > key_data.get("expiry", 0):
        return jsonify({"status": "error", "valid": False, "message": "Key expired"}), 403
    
    # Mark as used
    key_data["used"] = True
    key_data["used_by_hwid"] = hwid
    key_data["used_by_script"] = script
    key_data["used_at"] = current_time
    
    # Update user record
    if hwid in users:
        users[hwid]["used_key"] = True
        users[hwid]["used_key_value"] = user_key
    
    save_keys(keys)
    save_users(users)
    
    return jsonify({"status": "success", "valid": True})

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Receive heartbeat from bot every 10 minutes"""
    data = request.json or {}
    hwid = data.get('hwid')
    script = data.get('script', 'unknown')
    
    if not hwid:
        return jsonify({"status": "error", "message": "HWID required"}), 400
    
    users = load_users()
    current_time = time.time()
    
    if hwid not in users:
        users[hwid] = {
            "first_seen": current_time,
            "heartbeat_count": 0
        }
    
    users[hwid]["last_heartbeat"] = current_time
    users[hwid]["active_script"] = script
    users[hwid]["heartbeat_count"] = users[hwid].get("heartbeat_count", 0) + 1
    
    save_users(users)
    
    return jsonify({"status": "success", "timestamp": current_time})

# ==================== ADMIN ROUTES ====================
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
    stats = get_stats()
    device_list = get_device_list()
    
    # Format keys for display
    keys_display = {}
    for k, v in keys.items():
        expiry_date = datetime.fromtimestamp(v.get("expiry", 0)).strftime("%Y-%m-%d %H:%M") if v.get("expiry") else "N/A"
        keys_display[k] = {
            "url": v.get("url", ""),
            "used": v.get("used", False),
            "expiry_date": expiry_date,
            "used_by_hwid": v.get("used_by_hwid", "")
        }
    
    return render_template_string(DASHBOARD_HTML, keys=keys_display, stats=stats, device_list=device_list)

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
        final_url = mrn_shorten(note_url) if note_url else None
        
        keys[new_key] = {
            "used": False,
            "created_at": current_time,
            "expiry": current_time + KEY_VALIDITY,
            "url": final_url
        }
    
    save_keys(keys)
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/admin')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
