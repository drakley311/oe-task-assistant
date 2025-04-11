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

# Environment vars
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET")
MS_TENANT_ID = os.environ.get("MS_TENANT_ID")
MS_REDIRECT_URI = os.environ.get("MS_REDIRECT_URI")

# OpenAI setup
client = OpenAI(api_key=OPENAI_API_KEY)

# OAuth config
AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
AUTH_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/authorize"
TOKEN_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/token"
SCOPE = [
    "https://graph.microsoft.com/Tasks.ReadWrite",
    "offline_access",
    "User.Read"
]

# Group and Plan Names
TARGET_GROUP_NAME = "OE Action Review"
TARGET_PLAN_NAME = "OE Action Review"

def get_ms_headers():
    return {
        "Authorization": f"Bearer {session['ms_token']['access_token']}",
        "Content-Type": "application/json"
    }

def get_group_and_plan_ids():
    # 1. Get Group ID
    group_resp = requests.get(
        "https://graph.microsoft.com/v1.0/groups",
        headers=get_ms_headers()
    )
    groups = group_resp.json().get("value", [])
    group_id = next((g["id"] for g in groups if g["displayName"] == TARGET_GROUP_NAME), None)

    if not group_id:
        raise Exception(f"Group '{TARGET_GROUP_NAME}' not found")

    # 2. Get Plan ID
    plan_resp = requests.get(
        f"https://graph.microsoft.com/v1.0/groups/{group_id}/planner/plans",
        headers=get_ms_headers()
    )
    plans = plan_resp.json().get("value", [])
    plan_id = next((p["id"] for p in plans if p["title"] == TARGET_PLAN_NAME), None)

    if not plan_id:
        raise Exception(f"Plan '{TARGET_PLAN_NAME}' not found in group '{TARGET_GROUP_NAME}'")

    return group_id, plan_id

def create_planner_task(plan_id, title, notes):
    task_payload = {
        "planId": plan_id,
        "title": title,
        "details": {
            "description": notes
        }
    }

    # Create task (must POST to /tasks, then PATCH details)
    task_resp = requests.post(
        "https://graph.microsoft.com/v1.0/planner/tasks",
        headers=get_ms_headers(),
        json={
            "planId": plan_id,
            "title": title,
            "bucketId": None  # Optional: Fill if needed
        }
    )

    if task_resp.status_code >= 400:
        raise Exception(f"Failed to create task: {task_resp.text}")

@app.route("/")
def home():
    return render_template("form.html")

@app.route("/", methods=["POST"])
def process_prompt():
    if "ms_token" not in session:
        return redirect(url_for("login"))

    prompt = request.form.get("prompt", "")
    today = datetime.now().strftime("%B %d, %Y")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a Microsoft Planner task assistant for the OE Action Review board.\n"
                        f"Today’s date is {today}.\n"
                        "Every output must follow this format:\n\n"
                        "🪪 Title: <title>\n"
                        "📝 Notes: Expected Outcome: <clear outcome>\n"
                        "Respond only with those 2 fields."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=300
        )
        task_text = response.choices[0].message.content.strip()

        # Extract title and notes from response
        title = task_text.split("🪪 Title:")[1].split("📝 Notes:")[0].strip()
        notes = task_text.split("📝 Notes:")[1].strip()

        group_id, plan_id = get_group_and_plan_ids()
        create_planner_task(plan_id, title,_
