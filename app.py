%pip install -q google-generativeai

# Secrets + widgets
GITHUB_TOKEN = dbutils.secrets.get("mysecrets", "github_token")
JIRA_API_TOKEN = dbutils.secrets.get("mysecrets", "jira_api_token")
GEMINI_API_KEY = dbutils.secrets.get("mysecrets", "gemini_api_key")
JIRA_EMAIL = dbutils.secrets.get("mysecrets", "jira_email")
JIRA_ISSUE_KEY = dbutils.secrets.get("mysecrets", "jira_issue_key")
try:
    JIRA_BASE_URL = dbutils.secrets.get("mysecrets", "jira_base_url")
except:
    JIRA_BASE_URL = "https://your-domain.atlassian.net"

dbutils.widgets.text("repo", "Sammy-sr/ai_jira_bot", "Repo (owner/repo)")
dbutils.widgets.text("commit_sha", "", "Commit SHA (empty = latest)")
dbutils.widgets.text("branch", "main", "Branch")

REPO = dbutils.widgets.get("repo")
COMMIT_SHA = dbutils.widgets.get("commit_sha").strip()
BRANCH = dbutils.widgets.get("branch")

print(f"✓ Ready on serverless | Repo: {REPO} | Commit: {COMMIT_SHA or 'latest on ' + BRANCH}")

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1)))

# GitHub helpers
def get_commit(owner_repo: str, sha: str):
    owner, repo = owner_repo.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    r = session.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    j = r.json()
    return {
        "sha": j["sha"][:7],
        "author": j["commit"]["author"].get("name") or "Unknown",
        "message": j["commit"]["message"],
        "url": j.get("html_url"),
        "files": [f"{f.get('status','?')}:{f.get('filename','?')}" for f in j.get("files", [])]
    }

def get_latest_commit_for_branch(owner_repo: str, branch: str):
    owner, repo = owner_repo.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = session.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    j = r.json()
    return {
        "sha": j["sha"][:7],
        "author": j["commit"]["author"].get("name") or "Unknown",
        "message": j["commit"]["message"],
        "url": j.get("html_url"),
        "files": []
    }

# Gemini summarizer — uses pre-installed library + current model (Nov 2025)
def summarize_with_gemini(text: str) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")   # ← works perfectly on serverless
        response = model.generate_content(
            f"""You are a senior developer. Summarize this Git commit for a Jira ticket comment in exactly 3 short bullet points.
Bold the main action and add one relevant emoji per bullet.

Commit details:
{text}

Summary:"""
        )
        return "**AI Summary by Gemini** 🚀\n\n" + response.text.strip()
    except Exception as e:
        print("Gemini error:", e)
        first = text.strip().splitlines()[0] if text else "(none)"
        return f"**Fallback Summary** ⚠️\n- **Commit**: {first}\n- Please review manually"

# Post to Jira
def post_to_jira(comment: str):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{JIRA_ISSUE_KEY}/comment"
    payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}}
    r = session.post(url, json=payload, auth=(JIRA_EMAIL, JIRA_API_TOKEN), timeout=20)
    r.raise_for_status()
    return r.status_code

# Main flow
commit = get_commit(REPO, COMMIT_SHA) if COMMIT_SHA else get_latest_commit_for_branch(REPO, BRANCH)

commit_text = f"Commit {commit['sha']} by {commit['author']}\n{commit['url']}\n\nMessage:\n{commit['message']}\n\nFiles changed: {'; '.join(commit['files'][:30]) or 'none'}"

print("✓ Commit fetched")

summary = summarize_with_gemini(commit_text)
print("\nGemini Summary:\n", summary)

status = post_to_jira(summary)
print(f"\n🎉 Posted to Jira! Status: {status} → All done on serverless!")
