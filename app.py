import os
from datetime import datetime
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import openai
import requests
from flask import Flask, request, redirect, session, url_for, render_template
from requests_oauthlib import OAuth2Session
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ENV variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET")
MS_TENANT_ID = os.environ.get("MS_TENANT_ID")
MS_REDIRECT_URI = os.environ.get("MS_REDIRECT_URI")

client = OpenAI(api_key=OPENAI_API_KEY)

AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
AUTH_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/authorize"
TOKEN_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/token"
SCOPE = [
    "https://graph.microsoft.com/Tasks.ReadWrite",
    "offline_access",
    "User.Read"
]

PLAN_ID = "_npgkc4RPUydQZTi2F6T2mUABa7d"
GROUP_ID = "51bc2ed3-a2b0-4930-aa2a-a87e76fcb55e"

# Mapping: GPT bucket label → Planner bucket ID
BUCKET_MAP = {
    "ICQA": "digBrtTP-0qe3SFx1LYKOWUAHwfJ",
    "Network Strategy & Expansion": "3QLs64V7Y06T9DqNnGYUbWUAPutF",
    "Business Insights": "f4AH9hLvqE2W2hwZ-fR0LWUAE9kJ",
    "Facilities": "9SHeUNHAFUeJk-DmiEjqI2UAIGuP",
    "CI & Learning": "DEkMb2XvVUy7FkgafKliGGUAOm16",
    "EHS": "8PzOtLw06UO65thZZT3MumUALJTX"
}

@app.route("/")
def home():
    return render_template("form.html", task_output=None)

@app.route("/", methods=["POST"])
def process_prompt():
    prompt = request.form.get("prompt", "")
    session["pending_prompt"] = prompt

    if "ms_token" not in session:
        return redirect(url_for("login"))

    return redirect(url_for("process_after_login"))

@app.route("/process-after-login")
def process_after_login():
    prompt = session.pop("pending_prompt", None)
    task_output = ""

    if not prompt:
        return redirect(url_for("home"))

    today = datetime.now().strftime("%B %d, %Y")

    try:
        # Ask GPT for structured planner card with improved formatting
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a Microsoft Planner assistant for the OE Action Review board.\n"
                        f"Today’s date is {today}.\n\n"
                        "Respond ONLY using this format:\n"
                        "🪪 Title: <short title>\n"
                        "🗂️ Bucket: <must match one of: EHS, CI & Learning, Facilities, Business Insights, Network Strategy & Expansion, ICQA>\n"
                        "🏷️ Labels: <REQUIRED: Just Do It, PROJECT, or LSW/Routine; optional: #SEA01, #TOP3!, etc.>\n"
                        "📝 Notes: Expected Outcome: <clear, concise success criteria>\n"
                        "📅 Start Date: <always include, use today if not stated>\n"
                        "📅 Due Date: <convert phrases like 'next Friday' to full date>\n"
                        "✅ Checklist:\n"
                        "- Task – Owner – Due: Month Day, Year\n\n"
                        "🛑 Do not leave any section blank. If unknown, provide a reasonable placeholder.\n"
                        "✅ Always infer the most likely bucket based on keywords (e.g., 'safety' → EHS).\n"
                        "✅ Always return all fields — do NOT say 'unspecified' or 'not provided'.\n"
                        "✅ Return this output and nothing else."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=700
        )

        task_text = response.choices[0].message.content.strip()

        # Parse key fields
        lines = task_text.splitlines()
        title, notes, bucket_label = "", "", ""
        for line in lines:
            if line.startswith("🪪 Title:"):
                title = line.replace("🪪 Title:", "").strip()
            elif line.startswith("📝 Notes:"):
                notes = line.replace("📝 Notes:", "").strip()
            elif line.startswith("🗂️ Bucket:"):
                bucket_label = line.replace("🗂️ Bucket:", "").strip()

        # Match GPT bucket label to Planner ID
        matched_bucket_id = None
        for key, value in BUCKET_MAP.items():
            if key.lower() in bucket_label.lower():
                matched_bucket_id = value
                break

        if not title:
            raise Exception("Title missing from GPT response.")

        task_payload = {
            "planId": PLAN_ID,
            "title": title,
            "assignments": {}
        }

        if matched_bucket_id:
            task_payload["bucketId"] = matched_bucket_id

        create_task_resp = requests.post(
            "https://graph.microsoft.com/v1.0/planner/tasks",
            headers={
                "Authorization": f"Bearer {session['ms_token']['access_token']}",
                "Content-Type": "application/json"
            },
            json=task_payload
        )

        if create_task_resp.status_code >= 400:
            raise Exception(f"Planner task creation failed: {create_task_resp.text}")

    except Exception as e:
        task_text = f"Error: {str(e)}"

    return render_template("form.html", task_output=task_text)

@app.route("/login")
def login():
    oauth = OAuth2Session(MS_CLIENT_ID, scope=SCOPE, redirect_uri=MS_REDIRECT_URI)
    auth_url, state = oauth.authorization_url(AUTH_ENDPOINT)
    session["oauth_state"] = state
    return redirect(auth_url)

@app.route("/oauth-callback")
def oauth_callback():
    oauth = OAuth2Session(MS_CLIENT_ID, state=session.get("oauth_state"), redirect_uri=MS_REDIRECT_URI)
    token = oauth.fetch_token(
        TOKEN_ENDPOINT,
        client_secret=MS_CLIENT_SECRET,
        authorization_response=request.url
    )
    session["ms_token"] = token

    if "pending_prompt" in session:
        return redirect(url_for("process_after_login"))

    return redirect(url_for("home"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
