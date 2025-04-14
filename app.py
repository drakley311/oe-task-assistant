import os
from datetime import datetime
from dateutil import parser as dateparser
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
SCOPE = ["https://graph.microsoft.com/Tasks.ReadWrite", "offline_access", "User.Read"]

PLAN_ID = "_npgkc4RPUydQZTi2F6T2mUABa7d"
GROUP_ID = "51bc2ed3-a2b0-4930-aa2a-a87e76fcb55e"

BUCKET_MAP = {
    "ICQA": "digBrtTP-0qe3SFx1LYKOWUAHwfJ",
    "Network Strategy & Expansion": "3QLs64V7Y06T9DqNnGYUbWUAPutF",
    "Business Insights": "f4AH9hLvqE2W2hwZ-fR0LWUAE9kJ",
    "Facilities": "9SHeUNHAFUeJk-DmiEjqI2UAIGuP",
    "CI & Learning": "DEkMb2XvVUy7FkgafKliGGUAOm16",
    "EHS": "8PzOtLw06UO65thZZT3MumUALJTX"
}

LABEL_MAP = {
    "Just Do It": "category20",
    "PROJECT": "category21",
    "LSW/Routine": "category5",
    "#SameDayDelivery": "category1",
    "#AllFCs": "category2",
    "#SEA01": "category7",
    "#TOP3!": "category13",
    "#IND01": "category9",
    "#LNK02": "category15",
    "#AVP01": "category23"
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

    today = datetime.utcnow().strftime("%B %d, %Y")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Microsoft Planner assistant for the OE Action Review board.\n"
                        "Today is April 14, 2025.\n\n"
                        "Return your response ONLY in this structured format:\n"
                        "🪪 Title: <short, clear task title>\n"
                        "🗂️ Bucket: <choose exactly one from: EHS (Safety), CI & Learning (Variable Cost), Facilities (Fixed Cost), Business Insights, Network Strategy & Expansion, ICQA (Quality & Delivery)>\n"
                        "🏷️ Labels: <REQUIRED: Just Do It, PROJECT, or LSW/Routine> plus any optional like #SEA01, #AVP01, #TOP3!>\n"
                        "📝 Notes: Expected Outcome: <clear success criteria>\n"
                        "📅 Start Date: <calendar date, always include — use today if not provided>\n"
                        "📅 Due Date: <calendar date, inferred from phrasing like 'by next Friday'>\n"
                        "✅ Checklist:\n"
                        "- Subtask name – Owner – Due: Month Day, Year"
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=800
        )

        task_output = response.choices[0].message.content.strip()
        lines = task_output.splitlines()

        title = notes = bucket_label = start_date = due_date = ""
        labels = []
        checklist = []

        for line in lines:
            if line.startswith("🪪 Title:"):
                title = line.replace("🪪 Title:", "").strip()
            elif line.startswith("🗂️ Bucket:"):
                bucket_label = line.replace("🗂️ Bucket:", "").strip()
            elif line.startswith("🏷️ Labels:"):
                labels = [l.strip().strip(",") for l in line.replace("🏷️ Labels:", "").split()]
            elif line.startswith("📝 Notes:"):
                notes = line.replace("📝 Notes:", "").strip()
            elif line.startswith("📅 Start Date:"):
                start_date = line.replace("📅 Start Date:", "").strip()
            elif line.startswith("📅 Due Date:"):
                due_date = line.replace("📅 Due Date:", "").strip()
            elif line.startswith("- "):
                checklist.append(line.replace("- ", "").strip())

        matched_bucket_id = None
        for key, value in BUCKET_MAP.items():
            if key.lower() in bucket_label.lower():
                matched_bucket_id = value
                break

        categories = {}
        for label in labels:
            mapped = LABEL_MAP.get(label)
            if mapped:
                categories[mapped] = True

        def to_iso(date_str):
            try:
                dt = dateparser.parse(date_str)
                return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            except:
                return None

        start_iso = to_iso(start_date)
        due_iso = to_iso(due_date)

        payload = {
            "planId": PLAN_ID,
            "title": title,
            "assignments": {},
            "startDateTime": start_iso,
            "dueDateTime": due_iso,
            "bucketId": matched_bucket_id,
            "appliedCategories": categories
        }

        task_resp = requests.post(
            "https://graph.microsoft.com/v1.0/planner/tasks",
            headers={
                "Authorization": f"Bearer {session['ms_token']['access_token']}",
                "Content-Type": "application/json"
            },
            json=payload
        )

        if task_resp.status_code >= 400:
            raise Exception(f"Task failed: {task_resp.text}")

        task_id = task_resp.json().get("id")

        # Retrieve ETag for PATCH
        details_resp = requests.get(
            f"https://graph.microsoft.com/v1.0/planner/tasks/{task_id}/details",
            headers={
                "Authorization": f"Bearer {session['ms_token']['access_token']}"
            }
        )

        if details_resp.status_code >= 400:
            raise Exception(f"Failed to retrieve task details: {details_resp.text}")

        etag = details_resp.headers.get("ETag")

        patch_payload = {}
        if notes:
            patch_payload["description"] = notes

        if checklist:
            checklist_dict = {}
            for idx, item in enumerate(checklist):
                parts = item.split("–")
                title = parts[0].strip() if len(parts) > 0 else f"Subtask {idx+1}"
                checklist_dict[f"item{idx}"] = {"title": title, "isChecked": False}
            patch_payload["checklist"] = checklist_dict

        if patch_payload:
            patch_resp = requests.patch(
                f"https://graph.microsoft.com/v1.0/planner/tasks/{task_id}/details",
                headers={
                    "Authorization": f"Bearer {session['ms_token']['access_token']}",
                    "Content-Type": "application/json",
                    "If-Match": etag
                },
                json=patch_payload
            )

            if patch_resp.status_code >= 400:
                raise Exception(f"Failed to patch task details: {patch_resp.text}")

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
