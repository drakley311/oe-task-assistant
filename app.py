import os
from openai import OpenAI
from flask import Flask, request, render_template

app = Flask(__name__)

# Set up the OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        prompt = request.form.get('prompt', '')

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an assistant that converts user prompts into formatted Microsoft Planner tasks for the OE Action Review board. Follow the MS Planner Card Standard."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500
            )
            task_output = response.choices[0].message.content.strip()
        except Exception as e:
            task_output = f"Error: {str(e)}"

        return f"<h2>Formatted Planner Task:</h2><pre>{task_output}</pre><br><a href='/'>Back</a>"

    return render_template('form.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
