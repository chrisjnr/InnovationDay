import os
import json
import re
from typing import Optional, Dict, Any, List

from openai import OpenAI
from github import Github
from github.PullRequest import PullRequest

# ---------------------------
# Environment
# ---------------------------
MODEL = os.environ["LLM_MODEL"]
OPENAI_KEY = "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"
GH_TOKEN = os.environ["GITHUB_TOKEN"]
PR_NUMBER = int(os.environ["PR_NUMBER"])
REPO_NAME = os.environ["GITHUB_REPOSITORY"]
GITHUB_OUTPUT_PATH = os.environ.get("GITHUB_OUTPUT")

# ---------------------------
# Helpers
# ---------------------------

def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def safe_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()

    # Try fenced block
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except Exception:
            pass

    # Try direct JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # Extract first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass

    raise ValueError("Model did not return valid JSON.")

def build_diff(pr: PullRequest):
    """
    Use GitHub patch (not local git) — safe for CI
    """
    sections = []
    patches = {}

    for f in pr.get_files():
        patch = getattr(f, "patch", None)
        if not patch:
            continue

        patches[f.filename] = patch
        sections.append(f"### FILE: {f.filename}\n```\n{patch}\n```")

    return "\n\n".join(sections), patches


def map_new_line_to_position(patch: str, target: int) -> Optional[int]:
    if not patch:
        return None

    position = 0
    new_line = None

    for raw in patch.splitlines():
        line = raw.rstrip("\n")
        position += 1

        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                new_line = int(m.group(1))
            continue

        if new_line is None:
            continue

        if line.startswith("+"):
            if new_line == target:
                return position
            new_line += 1

        elif line.startswith("-"):
            continue  # old file only

        else:  # context line
            if new_line == target:
                return position
            new_line += 1

    return None


def write_output(name: str, value: str):
    if not GITHUB_OUTPUT_PATH:
        print("WARN: GITHUB_OUTPUT not set")
        return
    with open(GITHUB_OUTPUT_PATH, "a") as f:
        f.write(f"{name}={value}\n")


# ---------------------------
# MAIN
# ---------------------------
def main():
    # Load templates
    pr_template = load_text("ai-review/pr_review_template.md")
    arch_rules = load_text("ai-review/architecture_rules.md")

    # GitHub setup
    gh = Github(GH_TOKEN)
    repo = gh.get_repo(REPO_NAME)
    pr = repo.get_pull(PR_NUMBER)

    # Build diff
    diff_text, patches = build_diff(pr)

    if not diff_text.strip():
        pr.create_issue_comment("ℹ️ No text diff found. Skipping AI review.")
        write_output("fail", "false")
        return

    # Prompt
    system_prompt = """
You are a senior principal engineer performing a Pull Request review.

You MUST output valid JSON shaped like:

{
  "summary": "<text>",
  "inline_comments": [
    {"file": "...", "line": 123, "comment": "...", "severity": "info|warning|critical"}
  ],
  "critical_issues": ["<description>", ...]
}

Rules:
- Apply PR Review Template + Architecture Rules exactly.
- Only comment on changed lines (new file side).
- Do not invent files or line numbers.
- Mark security + architecture issues as critical.
"""

    # Call LLM
    client = OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": pr_template},
            {"role": "system", "content": arch_rules},
            {"role": "user", "content": diff_text},
        ]
    )

    raw = response.choices[0].message.content
    result = safe_json_from_text(raw)

    summary = result.get("summary", "")
    inline = result.get("inline_comments", [])
    critical = result.get("critical_issues", [])

    # ---------------------------
    # POST SUMMARY COMMENT  ⭐
    # ---------------------------
    pr.create_issue_comment(f"### 🧠 AI Review Summary\n\n{summary}")

    # ---------------------------
    # INLINE COMMENTS
    # ---------------------------
    head_sha = pr.head.sha

