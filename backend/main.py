from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from typing import List
import os
from dotenv import load_dotenv
import subprocess
import json
import re

# ================= LOAD ENV =================
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=GROQ_API_KEY)

# ================= APP =================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_NAME = "llama-3.3-70b-versatile"
SUPPORTED_LANGUAGES = ["python", "javascript"]

# ================= REQUEST MODEL =================
class CodeRequest(BaseModel):
    code: str
    language: str
    focus_areas: List[str] = []

# ================= UTILITIES =================
def calculate_complexity(code: str):
    lines = code.splitlines()
    return {
        "lines_of_code": len(lines),
        "functions": code.count("def "),
        "loops": code.count("for ") + code.count("while "),
        "conditionals": code.count("if ")
    }

def validate_language(language: str):
    lang = language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported language")
    return lang

def safe_json_parse(text: str):
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*", "", text)
    text = re.sub(r"```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except:
        return {"message": text}

# ================= REVIEW =================
@app.post("/api/review")
async def review_code(request: CodeRequest):

    if not request.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")

    language = validate_language(request.language)

    prompt = f"""
You are a professional code reviewer.

Return STRICT JSON only.

{{
  "bugs": "...",
  "security": "...",
  "performance": "...",
  "readability": "...",
  "rating": 1-10
}}

Code:
{request.code}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500
    )

    parsed = safe_json_parse(response.choices[0].message.content)

    return {
        "review": parsed,
        "complexity": calculate_complexity(request.code)
    }

# ================= REWRITE =================
@app.post("/api/rewrite")
async def rewrite_code(request: CodeRequest):

    language = validate_language(request.language)

    prompt = f"""
Refactor this {language} code.
Fix syntax errors, improve formatting and naming.
Do NOT change algorithm.
Return ONLY final code.

Code:
{request.code}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500
    )

    return {"rewritten_code": response.choices[0].message.content}

# ================= OPTIMIZE =================
@app.post("/api/optimize")
async def optimize_code(request: CodeRequest):

    language = validate_language(request.language)

    prompt = f"""
Optimize this {language} code.
Improve efficiency and memory usage.
May change algorithm.
Return ONLY final optimized code.

Code:
{request.code}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500
    )

    return {"optimized_code": response.choices[0].message.content}

# ================= SAFE EXECUTION =================
@app.post("/api/output")
async def run_code(request: CodeRequest):

    lang = validate_language(request.language)

    temp_file = f"temp_script.{ 'py' if lang=='python' else 'js' }"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(request.code)

        if lang == "python":
            result = subprocess.run(["python", temp_file],
                                    capture_output=True,
                                    text=True,
                                    timeout=5)
        else:
            result = subprocess.run(["node", temp_file],
                                    capture_output=True,
                                    text=True,
                                    timeout=5)

        return {"output": result.stdout or result.stderr}

    except subprocess.TimeoutExpired:
        return {"output": "Execution timeout"}
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)