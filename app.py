#!/usr/bin/env python3
# KEY GENERATOR + VERIFICATION SERVER - FINAL RULES

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

# Key DB: {key: {"url": "...", "created": ts, "validity_hours": 6, "used_ips": ["ip1"], "verified_by": ["ip1"]}}
KEYS_DB = {}

# IP tracking: {"ip": {"keys_taken": 0, "first_request": ts, "last_key": "abc"}}
IP_DB = {}

# ======================= HELPERS =======================
def random_key(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

# ==================== EZ4 ====================
def get_ez4_session():
    global EZ4_SESSION, EZ4_SESSION_TIME
    if EZ4_SESSION and (time.time() - EZ4_SESSION_TIME) < 1500:
        return EZ4_SESSION
    
    session = requests.Session()
    try:
        resp = session.get("https://ez4short.com/auth/signin", timeout=30)
        html = resp.text
        csrf = re.search(r'name="_csrfToken"[^>]*value="([^"]+)"', html)
        tf = re.search(r'name="_Token\[fields\]"[^>]*value="([^"]+)"', html)
        tu = re.search(r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"', html)
        if not csrf: return EZ4_SESSION
        
        login_data = f"_method=POST&_csrfToken={csrf.group(1)}&username={EZ4_USER}&password={EZ4_PASS}&remember_me=0&_Token%5Bfields%5D={quote(tf.group(1) if tf else '', safe='')}&_Token%5Bunlocked%5D={quote(tu.group(1) if tu else '', safe='')}"
        session.post("https://ez4short.com/auth/signin", data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://ez4short.com"})
        EZ4_SESSION = session
        EZ4_SESSION_TIME = time.time()
        return session
    except:
        return EZ4_SESSION

def shorten_ez4(long_url):
    session = get_ez4_session()
    if not session: return None
    try:
        resp = session.get("https://ez4short.com/member/dashboard", timeout=30)
        html = resp.text
        csrf = re.search(r'name="_csrfToken"[^>]*value="([^"]+)"', html)
        tf = re.search(r'name="_Token\[fields\]"[^>]*value="([^"]+)"', html)
        tu = re.search(r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"', html)
        if not csrf: return None
        data = f"_method=POST&_csrfToken={csrf.group(1)}&url={quote(long_url)}&alias=&ad_type=2&_Token%5Bfields%5D={quote(tf.group(1) if tf else '', safe='')}&_Token%5Bunlocked%5D={quote(tu.group(1) if tu else '', safe='')}"
        resp = session.post("https://ez4short.com/links/shorten", data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest"})
        result = resp.json()
        if result.get("status") == "success": return result.get("url")
    except: pass
    return None

def create_text_key(key):
    try:
        resp = requests.post(f"{TEXT_SITE}/", data={"text": key}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        match = re.search(r'Link:</strong> (https://key-genrater\.onrender\.com/[^<\"]+)', resp.text)
        return match.group(1) if match else None
    except: return None

def create_final_url(long_url):
    try:
        resp = requests.post(f"{SHORTENER}/", data={"url": long_url}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        match = re.search(r'Link:</strong> (https://url-shortner-3jy6\.onrender\.com/go/[^<\"]+)', resp.text)
        return match.group(1) if match else None
    except: return None

# ======================= API =======================
@app.route('/get-key', methods=['GET'])
def get_key():
    user_ip = get_real_ip()
    now = time.time()
    
    try:
        validity_hours = float(request.args.get('hours', DEFAULT_VALIDITY_HOURS))
        if validity_hours < 0.5: validity_hours = 0.5
        if validity_hours > 48: validity_hours = 48
    except:
        validity_hours = DEFAULT_VALIDITY_HOURS
    
    # ==================== RULE 3: RATE LIMIT ====================
    if user_ip in IP_DB:
        ip_data = IP_DB[user_ip]
        
        # 5 MINUTE WINDOW
        if now - ip_data["first_request"] < 300:
            if ip_data["keys_taken"] >= 2:
                # Rate limit — return last key
                last_key = ip_data.get("last_key")
                if last_key and last_key in KEYS_DB:
                    v = KEYS_DB[last_key]
                    validity_sec = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
                    if now - v["created"] < validity_sec:
                        return jsonify({
                            "status": "success", "key": last_key, "url": v["url"],
                            "validity_hours": v.get("validity_hours", DEFAULT_VALIDITY_HOURS),
                            "expires_in": round((validity_sec - (now - v["created"])) / 3600, 1),
                            "message": "Rate limit! Returning your last key."
                        })
            else:
                ip_data["keys_taken"] += 1
        else:
            # 5 min passed — reset
            ip_data["keys_taken"] = 1
            ip_data["first_request"] = now
    else:
        IP_DB[user_ip] = {"keys_taken": 1, "first_request": now, "last_key": ""}
    
    # ==================== RULE 1: Check if IP already verified some key ====================
    for k, v in KEYS_DB.items():
        validity_sec = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
        if now - v["created"] < validity_sec:  # Key valid
            if user_ip in v.get("verified_by", []):
                # Ye IP already verify kar chuki hai ye key
                if user_ip in v.get("used_ips", []):
                    # Ye key isi IP ki thi — MAT DO (skip)
                    continue
                else:
                    # Ye key kisi aur ki thi — bhi MAT DO (already verified)
                    continue
    
    # ==================== RULE 2: IP ko wahi key na do jo usne verify ki ya li thi ====================
    for k, v in KEYS_DB.items():
        validity_sec = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
        if now - v["created"] < validity_sec:  # Key valid
            if user_ip in v.get("used_ips", []):
                # Ye IP ye key le chuka hai — MAT DO
                continue
            if user_ip in v.get("verified_by", []):
                # Ye IP ye key verify kar chuka — MAT DO
                continue
            
            # 🔥 Ye key is IP ko nahi di gayi, na hi verify ki — DE DO
            KEYS_DB[k]["used_ips"].append(user_ip)
            IP_DB[user_ip]["last_key"] = k
            return jsonify({
                "status": "success", "key": k, "url": v["url"],
                "validity_hours": v.get("validity_hours", DEFAULT_VALIDITY_HOURS),
                "expires_in": round((validity_sec - (now - v["created"])) / 3600, 1),
                "message": "Existing key assigned to your IP"
            })
    
    # ==================== NO KEY FOUND — CREATE NEW ====================
    try:
        key = random_key()
        text_url = create_text_key(key)
        if not text_url: return jsonify({"error": "Text site failed"}), 500
        
        ez4_url = shorten_ez4(text_url)
        final_long = ez4_url if ez4_url else text_url
        
        final_url = create_final_url(final_long)
        if not final_url: return jsonify({"error": "Final shorten failed"}), 500
        
        KEYS_DB[key] = {
            "url": final_url, "created": now, "validity_hours": validity_hours,
            "used_ips": [user_ip], "verified_by": []
        }
        IP_DB[user_ip]["last_key"] = key
        
        return jsonify({
            "status": "success", "key": key, "url": final_url,
            "validity_hours": validity_hours, "expires_in": validity_hours
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verify-key', methods=['POST'])
def verify_key():
    data = request.json or {}
    key = data.get('key', '')
    user_ip = get_real_ip()
    
    if key in KEYS_DB:
        v = KEYS_DB[key]
        validity_sec = v.get("validity_hours", DEFAULT_VALIDITY_HOURS) * 3600
        
        if time.time() - v["created"] < validity_sec:
            # 🔥 ONLY ONE VERIFY PER IP
            if user_ip not in v.get("verified_by", []):
                KEYS_DB[key]["verified_by"].append(user_ip)
            
            return jsonify({
                "status": "success", "valid": True,
                "expires_in": round((validity_sec - (time.time() - v["created"])) / 3600, 1)
            })
    
    return jsonify({"status": "error", "valid": False, "message": "Key expired or invalid!"})

@app.route('/')
def home():
    return jsonify({"service": "Key Generator API"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
