# app.py - FINAL 100% WORKING VERSION (NOV 11, 2025)
from flask import Flask, request, jsonify
import google.generativeai as genai
import requests
import os
import re
from dotenv import load_dotenv

# === FORCE LOAD .env FROM CURRENT DIRECTORY ===
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# === CONFIGURE GEMINI ONLY AFTER .env IS LOADED ===
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file! Check file path and name.")
print(f"Gemini API Key loaded: {api_key[:10]}...{api_key[-4:]}")  # Debug print
genai.configure(api_key=api_key)

app = Flask(__name__)

# === CONFIG ===
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# === AI SUMMARY ===
def get_ai_summary(commits):
    text = "\n".join([f"{c['author']}: {c['message'].splitlines()[0]}" for c in commits])
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            f"Summarize these commits for JIRA in 3 bullet points with bold and emojis:\n\n{text}"
        )
        return "**AI Summary by Gemini 2.5 Flash**\n\n" + response.text.strip()
    except Exception as e:
        return f"Gemini failed: {str(e)}"

# === POST TO JIRA ===
def post_to_jira(key, text):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{key}/comment"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]
        }
    }
    try:
        print(f"Posting to JIRA {key}...")
        r = requests.post(
            url, json=payload,
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        print(f"JIRA Response Code: {r.status_code}")
        print(f"JIRA Response Body: {r.text}")
        if r.status_code == 201:
            print(f"SUCCESS: Posted to {key}")
            return True
        else:
            print(f"FAILED: {key} - {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"JIRA EXCEPTION for {key}: {e}")
        return False

# === WEBHOOK ===
@app.route('/github-webhook', methods=['POST'])
def webhook():
    data = request.get_json() or {}
    commits = data.get('commits', [])
    
    if not commits:
        return jsonify({"status": "no commits"}), 200
    
    commit_list = []
    jira_keys = set()
    
    for c in commits:
        author = c.get('author', {}).get('name', 'Unknown')
        message = c.get('message', '')
        commit_list.append({"author": author, "message": message})
        matches = re.findall(r'[A-Z][A-Z0-9]*-\d+', message.upper())
        jira_keys.update(matches)
    
    if not jira_keys:
        return jsonify({"status": "no JIRA keys found"}), 200
    
    summary = get_ai_summary(commit_list)
    
    success_keys = []
    for key in jira_keys:
        if post_to_jira(key, summary):
            success_keys.append(key)
    
    return jsonify({
        "status": "SUCCESS!",
        "jira_keys": list(jira_keys),
        "posted_to": success_keys,
        "summary_preview": summary[:200]
    }), 200

# === START ===
if __name__ == "__main__":
    print("="*70)
    print("AI JIRA BOT IS LIVE AND READY!")
    print("URL: http://localhost:5000/github-webhook")
    print("TEST WITH CURL BELOW")
    print("="*70)
    app.run(host="0.0.0.0", port=5000, debug=False)