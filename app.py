import os
from dotenv import load_dotenv
import openai
from flask import Flask, redirect, render_template, request, url_for, session
import tiktoken
import markdown2
from jinja2 import evalcontextfilter, Markup
import re
import uuid
import ast
from github import Github
import requests

load_dotenv()
conversations = {}


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or "Puzzle Enemy Start Breathe 0"
openai.api_key = os.getenv("OPENAI_API_KEY")
GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
github_instance = Github(GITHUB_ACCESS_TOKEN)

def get_files_from_repo(user, repo_name):
    def get_files_recursive(repo, path):
        file_list = []
        contents = repo.get_contents(path)
        for item in contents:
            if item.type == "file":
                file_content = requests.get(item.download_url).text
                file_list.append({"name": item.name, "content": file_content})
            elif item.type == "dir":
                file_list.extend(get_files_recursive(repo, item.path))
        return file_list

    repo = github_instance.get_user(user).get_repo(repo_name)
    return get_files_recursive(repo, "")



def count_tokens(text_arr):
    num_tokens = 0
    for x in text_arr:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        message_with_role = f'{x["role"]}: {x["content"]}'
        num_tokens += len(encoding.encode(message_with_role))
    print(f'Debug: Token count: {num_tokens}')
    return num_tokens

def gptinstance(prompt, filename):
    instance_id = str(uuid.uuid1())
    session[instance_id] = []
    m = session[instance_id]

    print(f'[Debug] Prompt: {prompt}\nFile Name: {filename}\n')

    github_user = "xXenithx"
    repo_name = "aichatbot"
    files = get_files_from_repo(github_user, repo_name)
    print(f'[Debug] Files: {files}')

    contents = ""

    for file in files:
        if file['name'] == filename:
            contents = file['content']
            print(f"[Debug] Found {filename}:\n{contents}")


    # print(f"[Debug] Contents: {contents}")
    m.append({"role": "system", "content": "As a GPT instance, you'll assist the main instance by answering its queries. The format is:User: PromptUser: <code>Keep responses brief to avoid token limits."})
    m.append({"role": "user", "content": prompt})
    m.append({"role": "user", "content": contents})

    # print(f"[Debug] Session: {m}")
    max_tokens = 8192 - count_tokens(m) - 1
    session.modified = True
    max_tokens = max(1, max_tokens - 50)
    print(f'[Debug] Instance ID: {instance_id}')
    print(f'Max Tokens: {max_tokens}')

    res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=m,
            temperature=0.6,
            max_tokens=max_tokens,
        )
    
    result = markdown2.markdown(
            res["choices"][0]["message"]["content"], extras=["fenced-code-blocks"])
    
    print(f"\n[Debug] RESULT:{result}\n")
    session.modified = True
    
    session.pop(instance_id)

    return instance_id, result


class FunctionCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.function_calls = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.function_calls.append((node.func.id, [self._arg_value(arg) for arg in node.args]))
        elif isinstance(node.func, ast.Attribute):
            self.function_calls.append((f"{node.func.value.id}_{node.func.attr}", [self._arg_value(arg) for arg in node.args]))

    def _arg_value(self, arg):
        if isinstance(arg, ast.Constant):
            return arg.value
        elif isinstance(arg, ast.Name):
            return arg.id
        else:
            return None

def parse_and_call_function(gpt_response):
    print(f'[Debug] GPT Response: \n{gpt_response}')
    # Use AST to parse GPT response
    try:
        gpt_ast = ast.parse(gpt_response)
    except SyntaxError:
        print("[Warning] Unable to parse GPT response as valid Python code")
        return

    # Extract function calls using AST
    visitor = FunctionCallVisitor()
    visitor.visit(gpt_ast)

    if visitor.function_calls:
        for function_call, arguments in visitor.function_calls:
            print(f"[Debug] Function Call: {function_call}, Arguments: {arguments}")
            if function_call == "gptinstance":
                intsance_id,res = gptinstance(arguments[0], arguments[1])
                return intsance_id,res
            else:
                print(f"[Error] Function {function_call} not found")
    else:
        print("[Warning] No function call found in GPT response")


@app.template_filter()
@evalcontextfilter
def wrap_code(eval_ctx, value):
    code_pattern = re.compile(r'(^```[a-z]*\n[\s\S]*?\n```$)', re.MULTILINE)
    result = code_pattern.sub(r'<pre><code>\1</code></pre>', value)
    return Markup(result)

def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


@app.route("/", methods=["GET", "POST"], defaults={"conversation_id": None})
@app.route("/<conversation_id>", methods=["GET", "POST"])
def index(conversation_id):
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    if conversation_id not in conversations:
        conversations[conversation_id] = []


    #If it's a POST request, process the form data
    if request.method == "POST":
        action = request.form.get("action")

        if action == "Send":
            p = request.form["prompt"]
            instances = []
            sys = [{"role": "system", "content":"Assist with code-related questions. You know filenames but not the code to avoid token limit. You'll receive a list of filenames. For queries about a specific file, call an internal function gptinstance(prompt, filename). The prompt is your question for another GPT instance, and the filename is the name of the file being requested. The next message is the other GPT instance's response. Example: User: 'Help needed for filename1 to make code efficient.'Assistant: gptinstance('Make code efficient', filename1) User: GPT Response: 'GPT model response...'"}]
            m = conversations[conversation_id] + [{"role": "user", "content": p}]
            max_tokens = 8192 - count_tokens(m+sys) - 1

            # Adds a saftey buffer to avoid over-generating tokens
            safety_buffer = 50
            max_tokens = max(1, max_tokens - safety_buffer)

            print(f"Debug: {m}")
            print(f"Debug: Max Token count {max_tokens}")
            print(f"Debug: Messages: {m}, Max Tokens: {max_tokens}")

            res = openai.ChatCompletion.create(
                model="gpt-4",
                messages=sys+m,
                temperature=0.6,
                max_tokens=max_tokens,
            )

            result = markdown2.markdown(
                res["choices"][0]["message"]["content"], extras=["fenced-code-blocks"])
            
            result_without_tags = remove_html_tags(result)
            id,response = parse_and_call_function(result_without_tags)

            instances.append(id)
            print(f"[Debug] Instance Tracker: {instances}\nResponse:{response}")

            conversations[conversation_id].append({"role": "user", "content": p})
            conversations[conversation_id].append({"role": "assistant", "content": response})
        
        elif action == "Clear":
            popped_data = conversations.pop(conversation_id)
            print(f'[Debug] Popping Data from session: \n{popped_data}')

    return render_template("index.html", messages=conversations[conversation_id], conversation_id=conversation_id)

if __name__ == "__main__":
    app.run()
