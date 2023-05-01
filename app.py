import os
from dotenv import load_dotenv
import openai
from flask import Flask, redirect, render_template, request, url_for, session
import tiktoken
import markdown2
from jinja2 import evalcontextfilter, Markup
import re
import pyperclip
import base64


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or "Puzzle Enemy Start Breathe 0"
openai.api_key = os.getenv("OPENAI_API_KEY")


def count_tokens(text_arr):
    num_tokens = 0
    for x in text_arr:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        message_with_role = f'{x["role"]}: {x["content"]}'
        num_tokens += len(encoding.encode(message_with_role))
    print(f'Debug: Token count: {num_tokens}')
    return num_tokens

@app.template_filter()
@evalcontextfilter
def wrap_code(eval_ctx, value):
    code_pattern = re.compile(r'(^```[a-z]*\n[\s\S]*?\n```$)', re.MULTILINE)
    result = code_pattern.sub(r'<pre><code>\1</code></pre>', value)
    return Markup(result)


@app.route("/", methods=["GET"])
def index():
    if "messages" not in session:
        session["messages"] = []
    
    str_to_encode = str(session['messages'])
    print(f"[Debug] String to Encode: {str_to_encode}")
    print(f"\n[Debug] Type of Variable: {type(str_to_encode)}")
    encoded_str = base64.b64encode(str_to_encode.encode('utf-8'))

    pyperclip.copy(str(encoded_str))

    return render_template("index.html", messages=session["messages"])

@app.route("/", methods=["POST"])
def process_form():
    if request.form["action"] == "Send":
        p = request.form["prompt"]
        m = session["messages"] + [{"role": "user", "content": p}]
        max_tokens = 4097 - count_tokens(m) - 1

        # Adds a saftey buffer to avoid over-generating tokens
        safety_buffer = 50
        max_tokens = max(1, max_tokens - safety_buffer)

        print(f"Debug: {m}")
        print(f"Debug: Max Token count {max_tokens}")
        print(f"Debug: Messages: {m}, Max Tokens: {max_tokens}")

        # Adds a loader
        session["messages"].append({"role": "assistant", "content": "<div class='loader'></div> Bot is typing..."})
        session.modified = True

        res = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=m,
            temperature=0.6,
            max_tokens=max_tokens,
        )

        result = markdown2.markdown(
            res["choices"][0]["message"]["content"], extras=["fenced-code-blocks"])
        session["messages"].append({"role": "user", "content": p})
        session["messages"].append(
            {"role": "assistant", "content": result})
        session.modified = True
        print(session)

    elif request.form["action"] == "Clear":
        session.clear()

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run()
