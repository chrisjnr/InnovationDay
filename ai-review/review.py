import os
import json
import subprocess
from openai import OpenAI
import re
from github import Github



# === ENV VARS ===
MODEL = os.environ["LLM_MODEL"]
OPENAI_KEY = os.environ["OPENAI_API_KEY"]
GH_TOKEN = os.environ["GITHUB_TOKEN"]
PR_NUMBER = int(os.environ["PR_NUMBER"])
REPO_NAME = os.environ["GITHUB_REPOSITORY"]

# === LOAD TEMPLATES ===
with open("ai-review/pr_review_template.md") as f:
    pr_template = f.read()

with open("ai-review/architecture_rules.md") as f:
    arch_rules = f.read()

# === GET DIFF ===
diff = subprocess.check_output(["git", "diff", "origin/main...HEAD"]).decode()

# === PREPARE PROMPT ===
system_prompt = """
You are a senior principal engineer performing a Pull Request review.

You MUST output valid JSON with this structure:

{
  "summary": "<text>",
  "inline_comments": [
    {
      "file": "path/to/file",
      "line": 123,
      "comment": "<your comment>",
      "severity": "info | warning | critical"
    }
  ],
  "critical_issues": [
    "<description>"
  ]
}

Rules:
- Apply the PR Review Template AND Architecture Rules.
- Comment only on changed files/lines found in the diff.
- Do NOT invent lines or files.
- Mark architecture violations as severity=critical.
"""

client = OpenAI(api_key=OPENAI_KEY)

response = client.chat.completions.create(
    model=MODEL,
    temperature=0,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": pr_template},
        {"role": "system", "content": arch_rules},
        {"role": "user", "content": diff}
    ]
)

result = json.loads(response.choices[0].message["content"])

summary = result["summary"]
inline_comments = result["inline_comments"]
critical_issues = result["critical_issues"]

g = Github(GH_TOKEN)
repo = g.get_repo(REPO_NAME)
pr = repo.get_pull(PR_NUMBER)

# === POST SUMMARY COMMENT ===
pr.create_issue_comment(f"### 🧠 AI Review Summary\n\n{summary}")

# === POST INLINE COMMENTS ===
for c in inline_comments:
    pr.create_review_comment(
        body=c["comment"],
        commit_id=pr.head.sha,
        path=c["file"],
        position=c["line"]
    )

# === OUTPUT FAIL FLAG ===
if len(critical_issues) > 0:
    print("::set-output name=fail::true")
else:
    print("::set-output name=fail::false")