import os
import json
import requests
from flask import Flask, Response, request, jsonify

app = Flask(__name__)

# Jadoo API Configuration
API_LOGIN_URL = "https://api.jadoodigital.com/api/v2.1/user/auth/login"
API_REFRESH_URL = "https://api.jadoodigital.com/api/v2.1/user/auth/refresh"
API_CHANNEL_URL = "https://api.jadoodigital.com/api/v2.1/user/channel/"

# Credentials (you can store them in environment variables)
USERNAME = os.getenv("JADOO_USERNAME", "jadoo6000")
PASSWORD = os.getenv("JADOO_PASSWORD", "jadoo6000")
DOMAIN = os.getenv("JADOO_DOMAIN", "af1dd86c3fb8448e87bb7770000c930c")

# Token Cache File
TOKEN_CACHE = "token.json"


# Function to save the refresh token
def save_token(token_data):
    with open(TOKEN_CACHE, 'w') as f:
        json.dump(token_data, f)


# Function to read the refresh token
def read_token():
    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE, 'r') as f:
            return json.load(f)
    return None


# Function to get the refresh token
def get_refresh_token():
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "domain": DOMAIN
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(API_LOGIN_URL, json=payload, headers=headers)
        if response.status_code == 200 and response.json().get("data"):
            refresh_token = response.json()["data"]["refresh_token"]
            save_token({"refreshToken": refresh_token})
            return refresh_token
    except Exception as e:
        print(f"Error: {e}")
    return None


# Function to get the access token
def get_access_token():
    token_data = read_token()
    refresh_token = token_data["refreshToken"] if token_data else get_refresh_token()

    if not refresh_token:
        return None

    headers = {"Authorization": f"Bearer {refresh_token}"}

    try:
        response = requests.get(API_REFRESH_URL, headers=headers)
        if response.status_code == 200 and response.json().get("data"):
            return response.json()["data"]["access_token"]
    except Exception as e:
        print(f"Error: {e}")
    
    return None


# Function to extract chunks.m3u8 URL
def extract_chunks_url(m3u8_content, base_url):
    for line in m3u8_content.split("\n"):
        if "chunks.m3u8" in line:
            return base_url + line.strip()
    return None


# Function to process TS segments
def process_chunks(m3u8_content, base_url):
    result = []
    for line in m3u8_content.split("\n"):
        if ".ts" in line:
            line = base_url + line.strip()
        result.append(line)
    return "\n".join(result)


@app.route('/stream/<channel_id>', methods=['GET'])
def stream(channel_id):
    if not channel_id:
        return jsonify({"error": "Channel ID is required!"}), 400
    
    access_token = get_access_token()
    if not access_token:
        return jsonify({"error": "Unauthorized!"}), 401
    
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        channel_url = f"{API_CHANNEL_URL}{channel_id}"
        response = requests.get(channel_url, headers=headers)
        if response.status_code != 200 or not response.json().get("url"):
            return jsonify({"error": "M3U8 URL not found!"}), 404

        stream_url = response.json()["url"]
        stream_response = requests.get(stream_url, headers=headers)

        base_url = f"https://edge01.iptv.digijadoo.net/live/{channel_id}/"
        chunks_url = extract_chunks_url(stream_response.text, base_url)

        if not chunks_url:
            return jsonify({"error": "chunks.m3u8 not found!"}), 500

        chunks_response = requests.get(chunks_url, headers=headers)
        final_output = process_chunks(chunks_response.text, base_url)

        return Response(final_output, content_type="application/vnd.apple.mpegurl")

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to fetch stream!"}), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
