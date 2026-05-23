#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests
import random
import string
import time
import json
import os

app = Flask(__name__)

# ==================== CONFIG ====================
KEYS_FILE = "keys.json"
USERS_FILE = "users.json"
BLOCK_TIME = 10 * 60  # 10 minutes background (user ko nahi pata)
KEY_VALIDITY = 6 * 3600  # 6 hours (user ko show hoga)

# MRN API
MRN_API = "https://mrn-bypass-protect-bot-mrn-official.vercel.app/api"
MRN_KEY = "av_botz_X2vlslxmhYiRej3yOhcacwpEGyGH3"

# NOTES SITE
NOTES_SITE = "https://key-genrater.onrender.com"

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

@app.route('/')
def home():
    return jsonify({"service": "MRN Key Generator", "status": "running"})

@app.route('/get-key', methods=['GET'])
def get_key():
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    
    users = load_users()
    keys = load_keys()
    
    # Check if user has an active key (6 hours validity)
    current_time = time.time()
    
    if user_ip in users:
        user_data = users[user_ip]
        key_assigned = user_data.get("assigned_key")
        
        if key_assigned and key_assigned in keys:
            key_info = keys[key_assigned]
            
            # Check if key is still valid (6 hours) and not used
            if not key_info.get("used") and current_time < key_info.get("expiry", 0):
                # Key still valid, return same key URL
                return jsonify({
                    "status": "success",
                    "key_url": key_info["url"],
                    "expires_in_hours": round((key_info["expiry"] - current_time) / 3600, 1),
                    "message": "Your key is still active"
                })
    
    # Check background block (10 minutes - user ko nahi pata)
    if user_ip in users:
        user_data = users[user_ip]
        if current_time < user_data.get("block_until", 0):
            # Background block active - but user doesn't see this
            # Just generate new key anyway
            pass
    
    # Find unused key
    unused_key = None
    for k, v in keys.items():
        if not v.get("used", False):
            unused_key = k
            break
    
    # Generate new key if needed
    if not unused_key:
        unused_key = generate_random_key()
        
        # Create note on key-genrater site
        note_url = create_note_on_site(unused_key)
        
        if note_url:
            # Shorten with MRN
            final_url = mrn_shorten(note_url)
            if not final_url:
                final_url = note_url
        else:
            final_url = None
        
        keys[unused_key] = {
            "used": False,
            "created_at": current_time,
            "expiry": current_time + KEY_VALIDITY,  # 6 hours expiry
            "url": final_url,
            "note_url": note_url
        }
    
    # Assign key to user
    if user_ip not in users:
        users[user_ip] = {}
    
    users[user_ip]["assigned_key"] = unused_key
    users[user_ip]["block_until"] = current_time + BLOCK_TIME  # Background block
    users[user_ip]["last_assigned"] = current_time
    
    save_keys(keys)
    save_users(users)
    
    return jsonify({
        "status": "success",
        "key_url": keys[unused_key]["url"],
        "expires_in_hours": 6,
        "message": "Key valid for 6 hours"
    })

@app.route('/verify-key', methods=['POST'])
def verify_key():
    data = request.json or {}
    user_key = data.get("key", "").strip()
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    
    keys = load_keys()
    users = load_users()
    
    if user_key not in keys:
        return jsonify({"status": "error", "valid": False, "message": "Invalid key"}), 404
    
    key_data = keys[user_key]
    
    # Check if key already used
    if key_data.get("used", False):
        return jsonify({"status": "error", "valid": False, "message": "Key already used"}), 403
    
    # Check if key expired (6 hours)
    if time.time() > key_data.get("expiry", 0):
        return jsonify({"status": "error", "valid": False, "message": "Key expired (6 hours)"}), 403
    
    # Mark as used
    key_data["used"] = True
    key_data["used_by"] = user_ip
    key_data["used_at"] = time.time()
    
    if user_ip in users:
        users[user_ip]["used_key"] = True
        users[user_ip]["verified_key"] = user_key
    
    save_keys(keys)
    save_users(users)
    
    return jsonify({
        "status": "success",
        "valid": True,
        "message": "Key verified! Access granted."
    })

@app.route('/debug', methods=['GET'])
def debug():
    return jsonify({
        "keys": load_keys(),
        "users": load_users()
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
