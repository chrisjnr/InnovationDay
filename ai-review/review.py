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
    sections: List[str] = []
    patches: Dict[str, str] = {}

    for f in pr.get_files():
        patch = getattr(f, "patch", None)
        if not patch:
            # Binary or too large; skip but log in main()
            patches[f.filename] = None
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
        print("[WARN] GITHUB_OUTPUT not set; cannot expose outputs to later steps.")
        return
    with open(GITHUB_OUTPUT_PATH, "a") as f:
        f.write(f"{name}={value}\n")


# ---------------------------
# MAIN
# ---------------------------
def main():
    print("==== AI PR Review: START ====")
    # Show essential env (do NOT print secrets)
    print(f"[ENV] Model: {MODEL}")
    print(f"[ENV] Repo: {REPO_NAME}")
    print(f"[ENV] PR number: {PR_NUMBER}")

    # Load templates
    print("[STEP] Loading templates...")
    pr_template_path = "ai-review/pr_review_template.md"
    arch_rules_path = "ai-review/architecture_rules.md"
    print(f"  - PR template path: {pr_template_path}")
    print(f"  - Architecture rules path: {arch_rules_path}")
    pr_template = load_text(pr_template_path)
    arch_rules = load_text(arch_rules_path)
    print("  ✓ Templates loaded.")

    # GitHub setup
    print("[STEP] Connecting to GitHub...")
    gh = Github(GH_TOKEN)
    repo = gh.get_repo(REPO_NAME)
    print(f"  ✓ Repository resolved: {repo.full_name}")
    pr: PullRequest = repo.get_pull(PR_NUMBER)
    print(f"  ✓ Pull Request title: {pr.title}")
    print(f"  ✓ Head: {pr.head.ref} @ {pr.head.sha}")
    print(f"  ✓ Base: {pr.base.ref} @ {pr.base.sha}")

    # Build diff
    print("[STEP] Building diff from PR files (GitHub API patches)...")
    diff_text, patches = build_diff(pr)

    # Per-file diagnostics
    no_textual = []
    with_textual = []
    for fname, patch in patches.items():
        if patch:
            with_textual.append(fname)
        else:
            no_textual.append(fname)

    if with_textual:
        print("  ✓ Textual patch files:")
        for fn in with_textual:
            print(f"    - {fn}")
    if no_textual:
        print("  ℹ️ Non-textual or large files (no patch available):")
        for fn in no_textual:
            print(f"    - {fn}")

    if not diff_text.strip():
        print("  ⚠️ No textual diff detected. Posting skip note.")
        pr.create_issue_comment("ℹ️ AI Review: No textual diff available (binary or very large files). Skipping automated review.")
        write_output("fail", "false")
        print("==== AI PR Review: END (skipped) ====")
        return
    else:
        print(f"  ✓ Diff prepared (length: {len(diff_text)} chars)")

    # Prompt
    print("[STEP] Preparing prompt for LLM...")
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
    print("  ✓ Prompt ready.")

    # Call LLM
    print("[STEP] Calling LLM for review...")
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
    print(f"  ✓ Raw response received (length: {len(raw)} chars)")

    # Parse JSON
    print("[STEP] Parsing model JSON...")
    try:
        result = safe_json_from_text(raw)
        print("  ✓ JSON parsed successfully.")
    except Exception as e:
        print(f"  ❌ JSON parse failed: {e}")
        pr.create_issue_comment(
            "⚠️ AI review could not parse JSON output. Raw response:\n\n"
            f"```\n{raw}\n```"
        )
        write_output("fail", "false")
        print("==== AI PR Review: END (parse failure) ====")
        return

    # Extract parts
    summary = (result.get("summary") or "").strip()
    inline = result.get("inline_comments", []) or []
    critical = result.get("critical_issues", []) or []
    print(f"  ✓ Parsed sections -> summary: {len(summary)} chars, inline_comments: {len(inline)}, critical_issues: {len(critical)}")

    # POST SUMMARY
    print("[STEP] Posting summary comment...")
    pr.create_issue_comment(f"### 🧠 AI Review Summary\n\n{summary or '(no summary)'}")
    print("  ✓ Summary posted.")

    # INLINE COMMENTS
    print("[STEP] Posting inline comments...")
    head_sha = pr.head.sha
    posted = 0
    fallback_posted = 0

    for idx, c in enumerate(inline, start=1):
        file = c.get("file")
        line = c.get("line")
        text = (c.get("comment") or "").strip()
        sev = (c.get("severity") or "info").upper()

        print(f"  -> [{idx}/{len(inline)}] file={file}, line={line}, severity={sev}")
        if not file or not isinstance(line, int) or not text:
            print("     skipped: missing file/line/comment")
            continue

        patch = patches.get(file)
        if patch is None:
            print("     note: no patch for this file (likely binary/large). Using fallback.")
        pos = map_new_line_to_position(patch, line) if patch else None
        print(f"     computed diff position: {pos}")

        if pos:
            try:
                pr.create_review_comment(
                    body=f"[{sev}] {text}",
                    commit_id=head_sha,
                    path=file,
                    position=pos
                )
                posted += 1
                print("     ✓ inline review_comment posted.")
                continue
            except Exception as ex:
                print(f"     ⚠️ inline post failed: {ex}. Falling back to issue comment.")

        # Fallback if we can't map a position
        pr.create_issue_comment(
            f"**Inline (fallback)** — `{file}`: L{line}\n\n[{sev}] {text}"
        )
        fallback_posted += 1
        print("     ✓ fallback issue_comment posted.")

    print(f"  ✓ Inline posting complete. review_comments={posted}, fallbacks={fallback_posted}")

    # AUTO‑FAIL
    print("[STEP] Evaluating critical issues...")
    crit_from_inline = sum(1 for c in inline if (c.get("severity") or "").lower() == "critical")
    crit_total = crit_from_inline + len(critical)
    print(f"  -> critical_from_inline={crit_from_inline}, critical_list={len(critical)}, total={crit_total}")

    if crit_total > 0:
        pr.create_issue_comment(f"❌ Critical architecture/security issues found: {crit_total}")
        write_output("fail", "true")
        print("  ❌ Marking job to FAIL.")
    else:
        write_output("fail", "false")
        print("  ✓ No critical issues. Job will PASS.")

    print("==== AI PR Review: END ====")


if __name__ == "__main__":
    main()
