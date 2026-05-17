#!/usr/bin/env python3

from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

ADURL_API = "https://adurl.io/api"
ADURL_KEY = "430ab4a2b2258b5591d5dcd460e47350f4329e0c"

@app.route('/short', methods=['GET', 'POST'])
def short_url():
    if request.method == 'GET':
        long_url = request.args.get('url')
    else:
        long_url = request.json.get('url') if request.is_json else request.form.get('url')
    
    if not long_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    
    try:
        resp = requests.get(ADURL_API, params={
            "api": ADURL_KEY,
            "url": long_url
        }, timeout=30)
        
        data = resp.json()
        
        if data.get("status") == "success":
            return jsonify({
                "status": "success",
                "shortenedUrl": data.get("shortenedUrl"),
                "originalUrl": long_url
            })
        else:
            return jsonify({
                "status": "error",
                "message": data.get("message", "Unknown error")
            }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return jsonify({
        "service": "AdURL.io Shortener Wrapper",
        "endpoint": "/short?url=YOUR_URL"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
