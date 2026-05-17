#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests
import re
import random
import string
import time
from datetime import datetime
import os

app = Flask(__name__)

# ================= CONFIG =================
VALIDITY_SECONDS = 6 * 3600  # 6 hours

# APIs
MRN_API_URL = "https://mrn-bypass-protect-bot-mrn-official.vercel.app/api"
MRN_API_KEY = "av_botz_X2vlslxmhYiRej3yOhcacwpEGyGH3"

SAFELINKU_URL = "https://safelinku.com/api/v1/links"
SAFELINKU_TOKEN = "87be54eb038b2b3fc0b240496c5715b69950f8f7"

TEXT_SITE = "https://key-genrater.onrender.com"

# Database
KEYS_DB = {}

# ================= HELPERS =================
def random_key(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

def create_safelinku_url(long_url):
    """Step 1: Create short link using SafelinkU"""
    try:
        headers = {
            "Authorization": f"Bearer {SAFELINKU_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {"url": long_url}
        
        resp = requests.post(SAFELINKU_URL, headers=headers, json=data, timeout=30)
        result = resp.json()
        
        # Response: {"url": "https://sfl.gl/FrAXODR"}
        return result.get("url")
    except Exception as e:
        print(f"SafelinkU error: {e}")
        return None

def protect_with_mrn(short_url):
    """Step 2: Protect the short link using MRN API"""
    try:
        params = {
            "api": MRN_API_KEY,
            "url": short_url
        }
        resp = requests.get(MRN_API_URL, params=params, timeout=30)
        result = resp.json()
        
        # Response: {"status": "success", "shortenedUrl": "https://ez4short.com/xyz"}
        return result.get("shortenedUrl") or result.get("shortlink")
    except Exception as e:
        print(f"MRN error: {e}")
        return None

def create_text_key(key):
    """Store key on text site"""
    try:
        resp = requests.post(
            f"{TEXT_SITE}/",
            data={"text": key},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )
        match = re.search(r'Link:</strong> (https://key-genrater\.onrender\.com/[^<\"]+)', resp.text)
        return match.group(1) if match else None
    except:
        return None

def cleanup_expired():
    now = time.time()
    expired = [k for k, v in KEYS_DB.items() if now - v["created_at"] > VALIDITY_SECONDS]
    for k in expired:
        del KEYS_DB[k]

# ================= MAIN API =================
@app.route('/get-key', methods=['GET'])
def get_key():
    cleanup_expired()
    
    user_ip = get_real_ip()
    
    # Check if IP already has a key
    for key, data in KEYS_DB.items():
        if data.get("assigned_ip") == user_ip:
            expires = round((VALIDITY_SECONDS - (time.time() - data["created_at"])) / 3600, 1)
            return jsonify({
                "status": "error",
                "message": "You already have an active key",
                "key": key,
                "url": data["url"],
                "expires_in_hours": expires
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
    try:
        new_key = random_key()
        
        # Step 1: Create text site URL
        text_url = create_text_key(new_key)
        if not text_url:
            text_url = f"{TEXT_SITE}/note/{new_key}"
        
        # Step 2: Create SafelinkU short link
        safelinku_url = create_safelinku_url(text_url)
        if not safelinku_url:
            safelinku_url = text_url
        
        # Step 3: Protect with MRN API
        final_url = protect_with_mrn(safelinku_url)
        if not final_url:
            final_url = safelinku_url
        
        # Store in database
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
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ================= VERIFY KEY =================
@app.route('/verify-key', methods=['POST'])
def verify_key():
    cleanup_expired()
    
    data = request.json or {}
    key = data.get("key", "").strip()
    user_ip = get_real_ip()
    
    if key not in KEYS_DB:
        return jsonify({"status": "error", "valid": False, "message": "Invalid or expired key"})
    
    key_data = KEYS_DB[key]
    expires_in = round((VALIDITY_SECONDS - (time.time() - key_data["created_at"])) / 3600, 1)
    
    if key_data.get("assigned_ip") and key_data["assigned_ip"] != user_ip:
        return jsonify({
            "status": "error",
            "valid": False,
            "message": "This key is assigned to another IP"
        }), 403
    
    if key_data.get("assigned_ip") is None:
        KEYS_DB[key]["assigned_ip"] = user_ip
    
    return jsonify({
        "status": "success",
        "valid": True,
        "expires_in_hours": expires_in,
        "url": key_data["url"]
    })

@app.route('/')
def home():
    return jsonify({
        "service": "Key Generator API v3",
        "validity_hours": 6,
        "flow": "SafelinkU → MRN Protect"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
