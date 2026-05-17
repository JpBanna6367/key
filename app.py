#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests
import re
import random
import string
import time

app = Flask(__name__)

VALIDITY_SECONDS = 6 * 3600

# APIs
SAFELINKU_TOKEN = "87be54eb038b2b3fc0b240496c5715b69950f8f7"
MRN_API_KEY = "av_botz_X2vlslxmhYiRej3yOhcacwpEGyGH3"
TEXT_SITE = "https://key-genrater.onrender.com"

KEYS_DB = {}

def random_key(length=8):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

def create_text_key(key):
    try:
        resp = requests.post(f"{TEXT_SITE}/", data={"text": key}, timeout=30)
        match = re.search(r'Link:</strong> (https://key-genrater\.onrender\.com/[^<\"]+)', resp.text)
        return match.group(1) if match else None
    except:
        return None

def create_safelinku_url(long_url):
    try:
        headers = {
            "Authorization": f"Bearer {SAFELINKU_TOKEN}",
            "Content-Type": "application/json"
        }
        resp = requests.post("https://safelinku.com/api/v1/links", headers=headers, json={"url": long_url}, timeout=30)
        return resp.json().get("url")
    except:
        return None

def protect_with_mrn(short_url):
    try:
        resp = requests.get(
            "https://mrn-bypass-protect-bot-mrn-official.vercel.app/api",
            params={"api": MRN_API_KEY, "url": short_url},
            timeout=30
        )
        data = resp.json()
        return data.get("shortenedUrl") or data.get("shortlink")
    except:
        return None

def cleanup_expired():
    now = time.time()
    for k in list(KEYS_DB.keys()):
        if now - KEYS_DB[k]["created_at"] > VALIDITY_SECONDS:
            del KEYS_DB[k]

@app.route('/get-key', methods=['GET'])
def get_key():
    cleanup_expired()
    user_ip = get_real_ip()
    
    # Check existing key for this IP
    for key, data in KEYS_DB.items():
        if data.get("assigned_ip") == user_ip:
            expires = round((VALIDITY_SECONDS - (time.time() - data["created_at"])) / 3600, 1)
            return jsonify({"status": "error", "message": "You already have a key", "key": key, "expires_in": expires}), 403
    
    # Find unassigned key
    for key, data in KEYS_DB.items():
        if data.get("assigned_ip") is None:
            KEYS_DB[key]["assigned_ip"] = user_ip
            expires = round((VALIDITY_SECONDS - (time.time() - data["created_at"])) / 3600, 1)
            return jsonify({"status": "success", "key": key, "url": data["url"], "expires_in_hours": expires})
    
    # Create new key
    new_key = random_key()
    
    # Step 1: Text site
    text_url = create_text_key(new_key)
    if not text_url:
        text_url = f"{TEXT_SITE}/note/{new_key}"
    
    # Step 2: SafelinkU
    safelinku_url = create_safelinku_url(text_url)
    if not safelinku_url:
        safelinku_url = text_url
    
    # Step 3: MRN Protect
    final_url = protect_with_mrn(safelinku_url)
    if not final_url:
        final_url = safelinku_url
    
    KEYS_DB[new_key] = {"url": final_url, "created_at": time.time(), "assigned_ip": user_ip}
    
    return jsonify({"status": "success", "key": new_key, "url": final_url, "expires_in_hours": 6})

@app.route('/verify-key', methods=['POST'])
def verify_key():
    cleanup_expired()
    data = request.json or {}
    key = data.get("key", "").strip()
    
    if key not in KEYS_DB:
        return jsonify({"status": "error", "valid": False, "message": "Invalid or expired key"})
    
    key_data = KEYS_DB[key]
    expires_in = round((VALIDITY_SECONDS - (time.time() - key_data["created_at"])) / 3600, 1)
    
    return jsonify({"status": "success", "valid": True, "expires_in_hours": expires_in, "url": key_data["url"]})

@app.route('/')
def home():
    return jsonify({"service": "Key Generator API v3", "validity_hours": 6, "flow": "SafelinkU → MRN Protect"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
