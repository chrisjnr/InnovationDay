import os
import json
import re
from typing import Optional, Dict, Any, List

from openai import OpenAI
from github import Github
from github.PullRequest import PullRequest


# ---------------------------
# Env & configuration
# ---------------------------
MODEL = os.environ["LLM_MODEL"]
OPENAI_KEY = "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"
GH_TOKEN = os.environ["GITHUB_TOKEN"]
PR_NUMBER = int(os.environ["PR_NUMBER"])
REPO_NAME = os.environ["GITHUB_REPOSITORY"]

GITHUB_OUTPUT_PATH = os.environ.get("GITHUB_OUTPUT")  # For step outputs


# ---------------------------
# Helpers
# ---------------------------
def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def safe_json_from_text(text: str) -> Dict[str, Any]:
    """
    Tries to extract a JSON object from the model response.
    Accepts:
      - raw JSON
      - JSON fenced in ```json ... ```
      - JSON embedded in text (extracts the first {...} block)
    """
    text = text.strip()

    # Fenced code block
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # Direct JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # Extract first { ... } block
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        candidate = text[brace_start: brace_end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

