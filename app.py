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

# Hardcoded plan for OE Action Review board
PLAN_ID = "_npgkc4RPUydQZTi2F6T2mUABa7d"  # Your Plan ID
GROUP_ID = "51bc2ed3-a2b0-4930-aa2a-a87e76fcb55e"  # Your Group ID

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
        # Prompt GPT to return fully structured OE task
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a Microsoft Planner task assistant for the OE Action Review board.\n"
                        f"Today is {today}.\n\n"
                        "Respond in this exact format:\n"
                        "🪪 Title: <title>\n"
                        "🗂️ Bucket: <one of: EHS (Safety), CI & Learning, Facilities, Business Insights, Network Strategy & Expansion, ICQA>\n"
                        "🏷️ Labels: <REQUIRED: Just Do It, PROJECT, or LSW/Routine> + optional tags like #SEA01, #TOP3!>\n"
                        "📝 Notes: Expected Outcome: <clear success criteria>\n"
                        "📅 Start Date: <today or inferred>\n"
                        "📅 Due Date: <only if specified or implied>\n"
                        "✅ Checklist (only if label is PROJECT):\n"
                        "- Task name – Owner – Due: Month Day, Year\n\n"
                        "If the user did not provide a bucket, label, or due date, say so clearly and ask them to clarify.\n"
                        "Use today's date as Start Date if none is given.\n"
                        "If PROJECT is selected but subtasks aren't provided, include checklist with placeholder items and owners.\n"
                        "Respond with only the formatted card."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=700
        )

        task_text = response.choices[0].message.content.strip()

        # Extract title and notes from the response (simple line-by-line parse)
        lines = task_text.splitlines()
        title = ""
        notes = ""
        label_line = ""
        for line in lines:
            if line.startswith("🪪 Title:"):
                title = line.replace("🪪 Title:", "").strip()
            elif line.startswith("📝 Notes:"):
                notes = line.replace("📝 Notes:", "").strip()
            elif line.startswith("🏷️ Labels:"):
                label_line = line.lower()

        # If "project" is in the labels line, post with checklist
        is_project = "project" in label_line

        # Create task in Planner
        task_payload = {
            "planId": PLAN_ID,
            "title": title,
            "assignments": {},  # You can add user assignment here
        }

        # Include notes as a "preview" (optional metadata block)
        if notes:
            task_payload["details"] = {"description": notes}

        task_resp = requests.post(
            "https://graph.microsoft.com/v1.0/planner/tasks",
            headers={
                "Authorization": f"Bearer {session['ms_token']['access_token']}",
                "Content-Type": "application/json"
            },
            json=task_payload
        )

        if task_resp.status_code >= 400:
            raise Exception(f"Planner task create failed: {task_resp.text}")

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
