"""
inference.py – OpenEnv RL Challenge Submission
Code Review Environment: AI-powered code review agent

Required env vars:
  API_BASE_URL  (default: https://api.openai.com/v1)
  MODEL_NAME    (default: gpt-4.1-mini)
  HF_TOKEN      (mandatory – used as OpenAI API key)

Output format:
  [START] task=<task_name> env=code_review model=<model_name>
  [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
  [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
"""
import os
import sys
import json
import traceback
from typing import Optional

from openai import OpenAI

# ── Environment variables ──────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
HF_TOKEN = os.getenv("HF_TOKEN")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
TASK_NAME = os.getenv("TASK_NAME", "find_bug")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

# ── OpenAI client ──────────────────────────────────────────────────────────────
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN,
)

# ── Environment client (HTTP) ──────────────────────────────────────────────────
import requests


def env_reset(task_name: str) -> dict:
    resp = requests.post(f"{ENV_BASE_URL}/reset", params={"task_name": task_name})
    resp.raise_for_status()
    return resp.json()


def env_step(action: dict, task_name: str) -> dict:
    resp = requests.post(
        f"{ENV_BASE_URL}/step",
        json=action,
        params={"task_name": task_name},
    )
    resp.raise_for_status()
    return resp.json()


# ── Agent prompt ───────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are an expert software engineer performing a code review.
You will be given a code snippet and a task description.
Your job is to identify issues in the code and return a structured JSON review.

RESPONSE FORMAT (return ONLY valid JSON, no markdown):
{
  "issues": [
    {
      "category": "bug|security|style|performance|logic",
      "severity": "low|medium|high|critical",
      "line_number": <int or null>,
      "description": "<clear description of the issue>",
      "suggestion": "<concrete fix or improvement>"
    }
  ],
  "summary": "<1-3 sentence overall review summary>",
  "approved": <true if code is acceptable, false if it needs changes>
}

Be thorough and precise. For security tasks focus only on security vulnerabilities.
For the full review, cover all categories.
"""


def call_llm(observation: dict) -> dict:
    """Call the LLM and return a parsed action dict."""
    snippet = observation["snippet"]
    user_content = f"""
Task: {observation['task_name']}
Instructions: {observation['task_description']}

File: {snippet['filename']}
Context: {snippet.get('context', 'N/A')}

Code:
```{snippet['language']}
{snippet['code']}
```

{f"Previous feedback: {observation['last_feedback']}" if observation.get('last_feedback') else ""}

Return your code review as JSON.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=1500,
        temperature=0.2,
    )

    content = response.choices[0].message.content
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip().rstrip("```").strip()

    parsed = json.loads(content)
    return parsed


def action_to_str(action: dict) -> str:
    """Compact string representation for the [STEP] line."""
    issues = action.get("issues", [])
    categories = [i.get("category", "?") for i in issues]
    return f"review(issues={len(issues)},cats={','.join(categories) or 'none'},approved={action.get('approved', False)})"


# ── Main inference loop ────────────────────────────────────────────────────────
def run_episode(task_name: str) -> None:
    last_action_error: Optional[str] = None
    rewards: list = []
    step = 0
    done = False
    success = False

    print(f"[START] task={task_name} env=code_review model={MODEL_NAME}", flush=True)

    try:
        obs = env_reset(task_name)

        while not done:
            try:
                action = call_llm(obs)
                result = env_step(action, task_name)

                step += 1
                reward = result["reward"]
                done = result["done"]
                obs = result["observation"]
                last_action_error = None
                rewards.append(reward)

                action_str = action_to_str(action)
                done_str = "true" if done else "false"
                print(
                    f"[STEP] step={step} action={action_str} "
                    f"reward={reward:.2f} done={done_str} error=null",
                    flush=True,
                )

                if done and obs["score_so_far"] >= 0.7:
                    success = True

            except json.JSONDecodeError as e:
                last_action_error = f"JSONDecodeError: {str(e)[:80]}"
                step += 1
                rewards.append(0.0)
                print(
                    f"[STEP] step={step} action=parse_error reward=0.00 "
                    f"done=false error={last_action_error}",
                    flush=True,
                )

            except requests.RequestException as e:
                last_action_error = f"EnvError: {str(e)[:80]}"
                step += 1
                rewards.append(0.0)
                done = True
                print(
                    f"[STEP] step={step} action=env_error reward=0.00 "
                    f"done=true error={last_action_error}",
                    flush=True,
                )

    except Exception as e:
        last_action_error = f"FatalError: {str(e)[:80]}"

    rewards_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"
    success_str = "true" if success else "false"
    print(
        f"[END] success={success_str} steps={step} rewards={rewards_str}",
        flush=True,
    )


def run_all_tasks() -> None:
    """Run all three tasks sequentially for a full benchmark."""
    for task in ["find_bug", "security_audit", "full_review"]:
        run_episode(task)


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else TASK_NAME
    if task == "all":
        run_all_tasks()
    else:
        run_episode(task)
