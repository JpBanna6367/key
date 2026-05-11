#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests
import re
import random
import string
import time
from urllib.parse import quote

app = Flask(__name__)

# ================= CONFIG =================
TEXT_SITE = "https://key-genrater.onrender.com"
SHORTENER = "https://url-shortner-3jy6.onrender.com"

EZ4_USER = "Banna123"
EZ4_PASS = "Jitendar"

# FIXED VALIDITY = 7 HOURS
VALIDITY_SECONDS = 7 * 3600

# ================= GLOBALS =================
EZ4_SESSION = None
EZ4_SESSION_TIME = 0

# {
#   key: {
#       "url": "...",
#       "created": timestamp,
#       "used_ips": []
#   }
# }
KEYS_DB = {}

# ================= HELPERS =================
def random_key(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_real_ip():
    return request.headers.get(
        'X-Forwarded-For',
        request.remote_addr
    ).split(',')[0].strip()

# ================= EZ4 LOGIN =================
def get_ez4_session():

    global EZ4_SESSION
    global EZ4_SESSION_TIME

    # reuse session
    if EZ4_SESSION and (time.time() - EZ4_SESSION_TIME) < 1500:
        return EZ4_SESSION

    session = requests.Session()

    try:
        resp = session.get(
            "https://ez4short.com/auth/signin",
            timeout=30
        )

        html = resp.text

        csrf = re.search(
            r'name="_csrfToken"[^>]*value="([^"]+)"',
            html
        )

        tf = re.search(
            r'name="_Token\[fields\]"[^>]*value="([^"]+)"',
            html
        )

        tu = re.search(
            r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"',
            html
        )

        if not csrf:
            return EZ4_SESSION

        login_data = (
            f"_method=POST"
            f"&_csrfToken={csrf.group(1)}"
            f"&username={EZ4_USER}"
            f"&password={EZ4_PASS}"
            f"&remember_me=0"
            f"&_Token%5Bfields%5D={quote(tf.group(1) if tf else '', safe='')}"
            f"&_Token%5Bunlocked%5D={quote(tu.group(1) if tu else '', safe='')}"
        )

        session.post(
            "https://ez4short.com/auth/signin",
            data=login_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://ez4short.com"
            }
        )

        EZ4_SESSION = session
        EZ4_SESSION_TIME = time.time()

        return session

    except:
        return EZ4_SESSION

# ================= SHORTEN =================
def shorten_ez4(long_url):

    session = get_ez4_session()

    if not session:
        return None

    try:
        resp = session.get(
            "https://ez4short.com/member/dashboard",
            timeout=30
        )

        html = resp.text

        csrf = re.search(
            r'name="_csrfToken"[^>]*value="([^"]+)"',
            html
        )

        tf = re.search(
            r'name="_Token\[fields\]"[^>]*value="([^"]+)"',
            html
        )

        tu = re.search(
            r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"',
            html
        )

        if not csrf:
            return None

        data = (
            f"_method=POST"
            f"&_csrfToken={csrf.group(1)}"
            f"&url={quote(long_url)}"
            f"&alias="
            f"&ad_type=2"
            f"&_Token%5Bfields%5D={quote(tf.group(1) if tf else '', safe='')}"
            f"&_Token%5Bunlocked%5D={quote(tu.group(1) if tu else '', safe='')}"
        )

        resp = session.post(
            "https://ez4short.com/links/shorten",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest"
            }
        )

        result = resp.json()

        if result.get("status") == "success":
            return result.get("url")

    except:
        pass

    return None

# ================= TEXT KEY =================
def create_text_key(key):

    try:
        resp = requests.post(
            f"{TEXT_SITE}/",
            data={"text": key},
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=30
        )

        match = re.search(
            r'Link:</strong> (https://key-genrater\.onrender\.com/[^<\"]+)',
            resp.text
        )

        return match.group(1) if match else None

    except:
        return None

# ================= FINAL SHORTENER =================
def create_final_url(long_url):

    try:
        resp = requests.post(
            f"{SHORTENER}/",
            data={"url": long_url},
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=30
        )

        match = re.search(
            r'Link:</strong> (https://url-shortner-3jy6\.onrender\.com/go/[^<\"]+)',
            resp.text
        )

        return match.group(1) if match else None

    except:
        return None

# ================= CLEAN EXPIRED =================
def cleanup_expired():

    now = time.time()

    remove_keys = []

    for k, v in KEYS_DB.items():

        if now - v["created"] > VALIDITY_SECONDS:
            remove_keys.append(k)

    for k in remove_keys:
        del KEYS_DB[k]

# ================= GET KEY =================
@app.route('/get-key', methods=['GET'])
def get_key():

    cleanup_expired()

    user_ip = get_real_ip()

    # ================= EXISTING VALID KEY =================
    for k, v in KEYS_DB.items():

        # same IP ko same key kabhi nahi
        if user_ip in v["used_ips"]:
            continue

        # assign existing key
        KEYS_DB[k]["used_ips"].append(user_ip)

        expires = round(
            (VALIDITY_SECONDS - (time.time() - v["created"])) / 3600,
            1
        )

        return jsonify({
            "status": "success",
            "key": k,
            "url": v["url"],
            "expires_in_hours": expires,
            "message": "Existing key assigned"
        })

    # ================= CREATE NEW KEY =================
    try:

        key = random_key()

        text_url = create_text_key(key)

        if not text_url:
            return jsonify({
                "error": "Text site failed"
            }), 500

        ez4_url = shorten_ez4(text_url)

        final_long = ez4_url if ez4_url else text_url

        final_url = create_final_url(final_long)

        if not final_url:
            return jsonify({
                "error": "Final shortener failed"
            }), 500

        KEYS_DB[key] = {
            "url": final_url,
            "created": time.time(),
            "used_ips": [user_ip]
        }

        return jsonify({
            "status": "success",
            "key": key,
            "url": final_url,
            "expires_in_hours": 7
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

# ================= VERIFY =================
@app.route('/verify-key', methods=['POST'])
def verify_key():

    cleanup_expired()

    data = request.json or {}

    key = data.get("key", "").strip()

    if key not in KEYS_DB:

        return jsonify({
            "status": "error",
            "valid": False,
            "message": "Invalid or expired key"
        })

    return jsonify({
        "status": "success",
        "valid": True,
        "expires_in_hours": round(
            (VALIDITY_SECONDS - (
                time.time() - KEYS_DB[key]["created"]
            )) / 3600,
            1
        )
    })

# ================= HOME =================
@app.route('/')
def home():

    return jsonify({
        "service": "Key Generator API",
        "validity_hours": 7
    })

# ================= START =================
if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=10000
        )
