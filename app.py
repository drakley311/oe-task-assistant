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
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a Microsoft Planner assistant for the OE Action Review board.\n"
                        f"Today is {today}.\n"
                        "Respond using this exact format, no exceptions. Here is an example:\n\n"
                        "🪪 Title: Launch Q3 training at LNK02\n"
                        "🗂️ Bucket: CI & Learning\n"
                        "🏷️ Labels: PROJECT #LNK02 #TOP3!\n"
                        "📝 Notes: Expected Outcome: All associates trained on new scanning SOP before July 1.\n"
                        "📅 Start Date: June 24, 2025\n"
                        "📅 Due Date: June 30, 2025\n"
                        "✅ Checklist:\n"
                        "- Finalize materials – J. Smith – Due: June 25, 2025\n"
                        "- Schedule sessions – L. West – Due: June 26, 2025\n"
                        "- Deliver training – Area Managers – Due: June 28, 2025\n\n"
                        "Now respond with your own version in the same format. Do not use ⏬, ⬜, ☑️, or other symbols."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=600
        )
        task_output = response.choices[0].message.content.strip()

    except Exception as e:
        task_output = f"Error: {str(e)}"

    return render_template("form.html", task_output=task_output)

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
