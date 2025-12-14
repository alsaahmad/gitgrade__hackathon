from flask import Flask, request, jsonify, send_from_directory
import requests
import os

# ---------- OPTIONAL OPENAI (SAFE) ----------
try:
    from openai import OpenAI
    client = OpenAI()
    OPENAI_ENABLED = True
except Exception as e:
    print("OpenAI disabled:", e)
    OPENAI_ENABLED = False

app = Flask(__name__)

GITHUB_API = "https://api.github.com/repos"

# ---------- FRONTEND ----------
@app.route("/")
def home():
    return send_from_directory(os.getcwd(), "index.html")


# ---------- CORE ANALYSIS ----------
def analyze_repo(repo_url):
    try:
        owner, repo = repo_url.replace("https://github.com/", "").split("/")
    except:
        return None

    repo_data = requests.get(f"{GITHUB_API}/{owner}/{repo}").json()
    contents = requests.get(f"{GITHUB_API}/{owner}/{repo}/contents").json()
    commits = requests.get(f"{GITHUB_API}/{owner}/{repo}/commits").json()

    if "message" in repo_data:
        return None

    files = [c["name"].lower() for c in contents if c["type"] == "file"]
    folders = [c["name"].lower() for c in contents if c["type"] == "dir"]

    return {
        "has_readme": any("readme" in f for f in files),
        "has_tests": "test" in folders or "tests" in folders,
        "has_ci": ".github" in folders,
        "commit_count": len(commits),
        "file_count": len(files),
        "folder_count": len(folders)
    }


def calculate_score(data):
    breakdown = {
        "README": 15 if data["has_readme"] else 0,
        "Tests": 15 if data["has_tests"] else 0,
        "CI": 10 if data["has_ci"] else 0,
        "Commits": 10 if data["commit_count"] >= 10 else 5 if data["commit_count"] >= 5 else 0,
        "Structure": 30 if data["folder_count"] >= 3 and data["file_count"] >= 8 else 15
    }

    score = sum(breakdown.values())
    level = "Beginner" if score < 40 else "Intermediate" if score < 70 else "Advanced"

    return score, level, breakdown


# ---------- AI REVIEW (CLEAN BULLET POINTS) ----------
def ai_code_review(data):
    if not OPENAI_ENABLED:
        return "- AI review unavailable (OpenAI not configured)."

    try:
        prompt = f"""
You are a senior software engineer reviewing a GitHub repository.

Return a SHORT review in BULLET POINTS.
Rules:
- 4 to 5 bullets only
- One clear point per bullet
- No paragraphs
- No extra explanations

Analysis:
- README present: {data['has_readme']}
- Tests present: {data['has_tests']}
- CI present: {data['has_ci']}
- Commit count: {data['commit_count']}
- Folder count: {data['folder_count']}
- File count: {data['file_count']}

Focus on strengths and improvements.
"""

        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt
        )

        return response.output_text.strip()

    except Exception as e:
        print("OPENAI ERROR:", e)
        return "- AI review temporarily unavailable."


# ---------- API ----------
@app.route("/analyze", methods=["POST"])
def analyze():
    print(">>> /analyze HIT")

    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400

    repo_url = request.json.get("repo_url")
    if not repo_url:
        return jsonify({"error": "repo_url missing"}), 400

    data = analyze_repo(repo_url)
    if not data:
        return jsonify({"error": "Invalid or inaccessible repository"}), 400

    score, level, breakdown = calculate_score(data)
    ai_review = ai_code_review(data)

    return jsonify({
        "score": score,
        "level": level,
        "breakdown": breakdown,
        "ai_review": ai_review
    })


if __name__ == "__main__":
    app.run(debug=True)
