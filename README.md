# 📝 OE Task Assistant

The OE Task Assistant transforms freeform team prompts into fully formatted Microsoft Planner tasks following the **OE Action Review** card standard.

Example prompt:
Set OE Action: Launch Q3 inventory accuracy protocol at LNK02

Produces:
🪪 Title: Launch Q3 inventory accuracy protocol at LNK02 
🗂️ Bucket: ICQA 
🏷️ Labels: PROJECT #LNK02 
📝 Notes: Expected Outcome: All inventory accuracy audits completed before Q3 cutoff. 
📅 Start Date: April 11, 2025 
📅 Due Date: April 19, 2025 
✅ Checklist:
- Train audit team – S. Lopez – Due: April 15, 2025
- Deploy audit tools – Ops Lead – Due: April 17, 2025
- Complete audits – ICQA Manager – Due: April 19, 2025

---

## 🔧 Setup Instructions

1. Deploy on [Render](https://render.com) as a **Web Service**
2. Use Python 3.11 and install requirements: pip install -r requirements.txt
3. Start command: python app.py

---

## 🔐 Required Environment Variables

Add these in Render → Environment → Add Environment Variables:

| Name               | Description                        |
|--------------------|------------------------------------|
| `OPENAI_API_KEY`   | Your OpenAI key                    |
| `MS_CLIENT_ID`     | Microsoft app client ID            |
| `MS_CLIENT_SECRET` | Microsoft app client secret        |
| `MS_TENANT_ID`     | Your Microsoft tenant ID           |
| `MS_REDIRECT_URI`  | e.g. `https://yourapp.onrender.com/oauth-callback` |

---

## ✅ How to Use

1. Visit your deployed app
2. Type: Set OE Action: Audit safety protocols at IND01 by Friday
3. Click **Submit**
4. Copy the formatted Planner card and paste it into your Microsoft Planner board

---

Built for the Spreetail Supply Chain OE team. Maintained by @bretnaugle.

