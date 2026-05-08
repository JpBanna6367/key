#!/usr/bin/env python3
# KEY GENERATOR + VERIFICATION SERVER - RENDER READY (CUSTOM VALIDITY)

from flask import Flask, request, jsonify
import requests
import re
import random
import string
import json
import os
import time
from urllib.parse import quote

app = Flask(__name__)

# ======================= CONFIG =======================
TEXT_SITE = "https://key-genrater.onrender.com"
SHORTENER = "https://url-shortner-3jy6.onrender.com"

EZ4_USER = "Banna123"
EZ4_PASS = "Jitendar"

DEFAULT_VALIDITY_HOURS = 6

# ======================= GLOBALS =======================
EZ4_SESSION = None
EZ4_SESSION_TIME = 0

KEYS_DB = {}  # {key: {"url": "...", "created": ts, "validity_hours": 6, "ips": ["ip1"]}}
IP_DB = {}    # {"ip": {"key": "abc", "request_count": 1, "last_request": ts}}

# ======================= HELPERS =======================
def random_key(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def clean_expired_keys():
    now = time.time()
    expired = []
    for k, v in KEYS_DB.items():
        validity = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
        if now - v["created"] > validity:
            expired.append(k)
    for k in expired:
        del KEYS_DB[k]

# ==================== EZ4 SESSION MANAGER ====================
def get_ez4_session():
    global EZ4_SESSION, EZ4_SESSION_TIME
    
    # Use cached if under 25 minutes
    if EZ4_SESSION and (time.time() - EZ4_SESSION_TIME) < 1500:
        return EZ4_SESSION
    
    session = requests.Session()
    
    try:
        resp = session.get("https://ez4short.com/auth/signin", timeout=30)
        html = resp.text
        
        csrf = re.search(r'name="_csrfToken"[^>]*value="([^"]+)"', html)
        tf = re.search(r'name="_Token\[fields\]"[^>]*value="([^"]+)"', html)
        tu = re.search(r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"', html)
        
        if not csrf:
            return None
        
        login_data = (
            f"_method=POST&_csrfToken={csrf.group(1)}&username={EZ4_USER}&password={EZ4_PASS}"
            f"&remember_me=0&_Token%5Bfields%5D={quote(tf.group(1) if tf else '', safe='')}"
            f"&_Token%5Bunlocked%5D={quote(tu.group(1) if tu else '', safe='')}"
        )
        
        session.post("https://ez4short.com/auth/signin", data=login_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://ez4short.com"})
        
        EZ4_SESSION = session
        EZ4_SESSION_TIME = time.time()
        return session
    except:
        return EZ4_SESSION  # Return old session if login fails

def shorten_ez4(long_url):
    session = get_ez4_session()
    if not session:
        return None
    
    try:
        resp = session.get("https://ez4short.com/member/dashboard", timeout=30)
        html = resp.text
        
        csrf = re.search(r'name="_csrfToken"[^>]*value="([^"]+)"', html)
        tf = re.search(r'name="_Token\[fields\]"[^>]*value="([^"]+)"', html)
        tu = re.search(r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"', html)
        
        if not csrf:
            return None
        
        data = (
            f"_method=POST&_csrfToken={csrf.group(1)}&url={quote(long_url)}&alias=&ad_type=2"
            f"&_Token%5Bfields%5D={quote(tf.group(1) if tf else '', safe='')}"
            f"&_Token%5Bunlocked%5D={quote(tu.group(1) if tu else '', safe='')}"
        )
        
        resp = session.post("https://ez4short.com/links/shorten", data=data,
                           headers={"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest"})
        
        result = resp.json()
        if result.get("status") == "success":
            return result.get("url")
    except:
        pass
    
    return None

# ==================== CREATE TEXT KEY ====================
def create_text_key(key):
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

# ==================== CREATE FINAL URL ====================
def create_final_url(long_url):
    try:
        resp = requests.post(
            f"{SHORTENER}/",
            data={"url": long_url},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )
        match = re.search(r'Link:</strong> (https://url-shortner-3jy6\.onrender\.com/go/[^<\"]+)', resp.text)
        return match.group(1) if match else None
    except:
        return None

# ======================= API =======================
@app.route('/get-key', methods=['GET'])
def get_key():
    """Generate new key + URL for user"""
    clean_expired_keys()
    
    user_ip = request.remote_addr
    now = time.time()
    
    # 🔥 Custom validity from query param
    try:
        validity_hours = float(request.args.get('hours', DEFAULT_VALIDITY_HOURS))
        if validity_hours < 0.5: validity_hours = 0.5
        if validity_hours > 48: validity_hours = 48
    except:
        validity_hours = DEFAULT_VALIDITY_HOURS
    
    # 🔥 IP LIMIT: Same IP can request max 2 times, then return same key
    if user_ip in IP_DB:
        ip_data = IP_DB[user_ip]
        # Within last 10 minutes
        if now - ip_data["last_request"] < 600:
            if ip_data["request_count"] >= 2:
                # Return existing key for this IP
                existing_key = ip_data.get("key")
                if existing_key and existing_key in KEYS_DB:
                    v = KEYS_DB[existing_key]
                    validity_sec = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
                    if now - v["created"] < validity_sec:
                        return jsonify({
                            "status": "success",
                            "key": existing_key,
                            "url": v["url"],
                            "validity_hours": v.get("validity_hours", DEFAULT_VALIDITY_HOURS),
                            "expires_in": round((validity_sec - (now - v["created"])) / 3600, 1),
                            "message": "Existing key returned (request limit reached)"
                        })
            ip_data["request_count"] += 1
            ip_data["last_request"] = now
        else:
            ip_data["request_count"] = 1
            ip_data["last_request"] = now
    else:
        IP_DB[user_ip] = {"key": "", "request_count": 1, "last_request": now}
    
    # 🔥 Check if IP already has a valid key assigned
    for k, v in KEYS_DB.items():
        if user_ip in v.get("ips", []):
            validity_sec = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
            if now - v["created"] < validity_sec:
                IP_DB[user_ip]["key"] = k
                return jsonify({
                    "status": "success",
                    "key": k,
                    "url": v["url"],
                    "validity_hours": v.get("validity_hours", DEFAULT_VALIDITY_HOURS),
                    "expires_in": round((validity_sec - (now - v["created"])) / 3600, 1),
                    "message": "Your existing key is still valid!"
                })
    
    try:
        # 1. Generate random key
        key = random_key()
        
        # 2. Create text key URL
        text_url = create_text_key(key)
        if not text_url:
            return jsonify({"error": "Text site failed"}), 500
        
        # 3. EZ4 Shorten
        ez4_url = shorten_ez4(text_url)
        if ez4_url:
            final_long = ez4_url
        else:
            final_long = text_url
        
        # 4. Final URL
        final_url = create_final_url(final_long)
        if not final_url:
            return jsonify({"error": "Final shorten failed"}), 500
        
        # 5. Save to DB
        KEYS_DB[key] = {
            "url": final_url,
            "created": now,
            "validity_hours": validity_hours,
            "ips": [user_ip]
        }
        IP_DB[user_ip]["key"] = key
        
        return jsonify({
            "status": "success",
            "key": key,
            "url": final_url,
            "validity_hours": validity_hours,
            "expires_in": validity_hours
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify-key', methods=['POST'])
def verify_key():
    """Verify if key is valid"""
    clean_expired_keys()
    
    data = request.json or {}
    key = data.get('key', '')
    
    if key in KEYS_DB:
        v = KEYS_DB[key]
        validity_sec = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
        
        if time.time() - v["created"] < validity_sec:
            return jsonify({
                "status": "success",
                "valid": True,
                "expires_in": round((validity_sec - (time.time() - v["created"])) / 3600, 1)
            })
    
    return jsonify({"status": "error", "valid": False, "message": "Key expired or invalid!"})

@app.route('/')
def home():
    return jsonify({
        "service": "Key Generator API",
        "endpoints": {
            "/get-key": "Generate new key (optional: ?hours=6)",
            "/verify-key": "Verify key (POST: {key: 'abc'})"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
