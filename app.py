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

# MRN API
MRN_API = "https://mrn-bypass-protect-bot-mrn-official.vercel.app/api"
MRN_KEY = "av_botz_X2vlslxmhYiRej3yOhcacwpEGyGH3"

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
    
    # Check if user already used ANY key
    user_has_used = False
    user_last_key = None
    
    if user_ip in users:
        user_data = users[user_ip]
        if user_data.get("used_key"):
            user_has_used = True
            user_last_key = user_data.get("last_key")
    
    # Find an unused key (used=False)
    unused_key = None
    for k, v in keys.items():
        if not v.get("used", False):
            unused_key = k
            break
    
    # Generate new key if no unused exists
    if not unused_key:
        unused_key = generate_random_key()
        text_url = f"https://key-server.onrender.com/note/{unused_key}"
        final_url = mrn_shorten(text_url) or text_url
        
        keys[unused_key] = {
            "used": False,
            "created_at": time.time(),
            "url": final_url
        }
    
    # If user has already used a key, give them a NEW key (not the unused one)
    if user_has_used:
        # Mark unused key as used? No, keep for others
        # Generate brand new key for this user
        new_key = generate_random_key()
        text_url = f"https://key-server.onrender.com/note/{new_key}"
        final_url = mrn_shorten(text_url) or text_url
        
        keys[new_key] = {
            "used": False,
            "created_at": time.time(),
            "url": final_url
        }
        
        # Update user record
        users[user_ip]["last_key"] = new_key
        users[user_ip]["last_assigned"] = time.time()
        users[user_ip]["used_key"] = True
        
        save_keys(keys)
        save_users(users)
        
        return jsonify({
            "status": "success",
            "key_url": final_url,
            "message": "New key for returning user"
        })
    
    # New user - give unused key
    # Store in user record
    if user_ip not in users:
        users[user_ip] = {}
    
    users[user_ip]["last_key"] = unused_key
    users[user_ip]["last_assigned"] = time.time()
    users[user_ip]["used_key"] = False
    
    save_keys(keys)
    save_users(users)
    
    return jsonify({
        "status": "success",
        "key_url": keys[unused_key]["url"],
        "message": "Use this URL to get your key"
    })

@app.route('/verify-key', methods=['POST'])
def verify_key():
    data = request.json or {}
    user_key = data.get("key", "").strip()
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    
    keys = load_keys()
    users = load_users()
    
    # Check if key exists
    if user_key not in keys:
        return jsonify({"status": "error", "valid": False, "message": "Invalid key"}), 404
    
    key_data = keys[user_key]
    
    # If key already used
    if key_data.get("used", False):
        # Mark this user as "used a key"
        if user_ip in users:
            users[user_ip]["used_key"] = True
            save_users(users)
        return jsonify({"status": "error", "valid": False, "message": "Key already used"}), 403
    
    # Valid key - mark as used
    key_data["used"] = True
    key_data["used_by"] = user_ip
    key_data["used_at"] = time.time()
    
    # Mark user as used
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
