import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Needed for OAuth callback on Render

import openai
import requests
from flask import Flask, request, redirect, session, url_for, render_template
from requests_oauthlib import OAuth2Session
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET")
MS_TENANT_ID = os.environ.get("MS_TENANT_ID")
MS_REDIRECT_URI = os.environ.get("MS_REDIRECT_URI")

# OpenAI setup
client = OpenAI(api_key=OPENAI_API_KEY)

# OAuth config (Group.Read.All removed)
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
    return render_template("form.html")

@app.route("/", methods=["POST"])
def process_prompt():
    if "ms_token" not in session:
        return redirect(url_for("login"))

    prompt = request.form.get("prompt", "")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Microsoft Planner task assistant for the OE Action Review board.\n"
                        "Every output must follow this exact format:\n\n"
                        "🪪 Title: <short, action-based title>\n"
                        "🗂️ Bucket: <one of: EHS (Safety), CI & Learning, Facilities, Business Insights, Network Strategy & Expansion, ICQA>\n"
                        "🏷️ Labels: <REQUIRED: Just Do It, PROJECT, or LSW/Routine> + any optional hashtags like #SEA01, #TOP3!, etc.\n"
                        "📝 Notes: Expected Outcome: <clear description of success>\n"
                        "📅 Start Date: <today’s date or provided>\n"
                        "📅 Due Date: <if included or inferred>\n"
                        "✅ Checklist (if PROJECT):\n- Task name – Owner – Due: <date>\n\n"
                        "Respond ONLY in that format. Do not explain or include any commentary."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        task_output = response.choices[0].message.content.strip()
    except Exception as e:
        task_output = f"Error: {str(e)}"

    return f"<h2>Formatted Planner Task:</h2><pre>{task_output}</pre><br><a href='/'>Back</a>"

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
    return redirect(url_for("home"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
