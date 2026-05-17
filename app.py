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
URLSHORTX_API = "https://urlshortx.io/api"
URLSHORTX_KEY = "f0b3839cf7c964bb1970cec6437ef2157f503a67"
MRN_API_URL = "https://mrn-bypass-protect-bot-mrn-official.vercel.app/api"
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
    except Exception as e:
        print(f"Text site error: {e}")
        return None

def create_urlshortx_link(long_url):
    """Step 1: Shorten using UrlShortx"""
    try:
        resp = requests.get(f"{URLSHORTX_API}", params={
            "api": URLSHORTX_KEY,
            "url": long_url
        }, timeout=30)
        data = resp.json()
        url = data.get("shortenedUrl")
        if url:
            # Remove backslashes if any
            return url.replace("\\", "")
        return None
    except Exception as e:
        print(f"UrlShortx error: {e}")
        return None

def protect_with_mrn(short_url):
    """Step 2: Protect with MRN API"""
    try:
        resp = requests.get(MRN_API_URL, params={
            "api": MRN_API_KEY,
            "url": short_url
        }, timeout=30)
        data = resp.json()
        return data.get("shortenedUrl") or data.get("shortlink")
    except Exception as e:
        print(f"MRN error: {e}")
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
            return jsonify({
                "status": "error",
                "message": "You already have a key",
                "key": key,
                "expires_in": expires
            }), 403
    
    # Find unassigned key
    for key, data in KEYS_DB.items():
        if data.get("assigned_ip") is None:
            KEYS_DB[key]["assigned_ip"] = user_ip
            expires = round((VALIDITY_SECONDS - (time.time() - data["created_at"])) / 3600, 1)
            return jsonify({
                "status": "success",
                "key": key,
                "url": data["url"],
                "expires_in_hours": expires
            })
    
    # Create new key
    new_key = random_key()
    
    # Step 1: Text site
    text_url = create_text_key(new_key)
    if not text_url:
        text_url = f"{TEXT_SITE}/note/{new_key}"
    
    # Step 2: UrlShortx — REQUIRED
    short_url = create_urlshortx_link(text_url)
    if not short_url:
        return jsonify({"error": "UrlShortx failed"}), 500
    
    # Step 3: MRN Protect — REQUIRED
    final_url = protect_with_mrn(short_url)
    if not final_url:
        return jsonify({"error": "MRN failed"}), 500
    
    KEYS_DB[new_key] = {
        "url": final_url,
        "created_at": time.time(),
        "assigned_ip": user_ip
    }
    
    return jsonify({
        "status": "success",
        "key": new_key,
        "url": final_url,
        "expires_in_hours": 6
    })

@app.route('/verify-key', methods=['POST'])
def verify_key():
    cleanup_expired()
    data = request.json or {}
    key = data.get("key", "").strip()
    
    if key not in KEYS_DB:
        return jsonify({"status": "error", "valid": False, "message": "Invalid or expired key"})
    
    key_data = KEYS_DB[key]
    expires_in = round((VALIDITY_SECONDS - (time.time() - key_data["created_at"])) / 3600, 1)
    
    return jsonify({
        "status": "success",
        "valid": True,
        "expires_in_hours": expires_in,
        "url": key_data["url"]
    })

@app.route('/')
def home():
    return jsonify({
        "service": "Key Generator API v4",
        "validity_hours": 6,
        "flow": "Text Site → UrlShortx → MRN Protect"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
