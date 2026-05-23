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
BLOCK_TIME = 10 * 60

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
    """Create note on key-genrater site"""
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
    
    # Check if user is blocked
    if user_ip in users:
        user_data = users[user_ip]
        if time.time() < user_data.get("block_until", 0):
            return jsonify({
                "status": "error",
                "message": f"Wait {int((user_data['block_until'] - time.time()) / 60)} minutes"
            }), 403
    
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
            "created_at": time.time(),
            "url": final_url,
            "note_url": note_url
        }
    
    # Check if key has URL
    if not keys[unused_key].get("url"):
        return jsonify({"status": "error", "message": "Failed to generate key URL"}), 500
    
    # Update user
    if user_ip not in users:
        users[user_ip] = {}
    
    users[user_ip]["last_key"] = unused_key
    users[user_ip]["block_until"] = time.time() + BLOCK_TIME
    
    save_keys(keys)
    save_users(users)
    
    return jsonify({
        "status": "success",
        "key_url": keys[unused_key]["url"],
        "message": "Open this URL to get your key"
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
    
    if key_data.get("used", False):
        return jsonify({"status": "error", "valid": False, "message": "Key already used"}), 403
    
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
