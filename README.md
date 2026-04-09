---
title: Code Review OpenEnv
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: server/app.py
app_port: 8000
pinned: false
tags:
  - openenv
  - reinforcement-learning
  - code-review
  - llm-agents
---

# 🔍 Code Review OpenEnv

> **An RL environment where AI agents learn to review code like an expert software engineer.**

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-blue)](https://github.com/meta-pytorch/OpenEnv)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://python.org)
[![HuggingFace](https://img.shields.io/badge/🤗-Spaces-orange)](https://huggingface.co/spaces)
[![License](https://img.shields.io/badge/License-BSD--3-lightgrey)](LICENSE)

---

## 🎯 Overview & Motivation

Code review is one of the most cognitively demanding tasks in software engineering. A good reviewer must simultaneously reason about **correctness** (bugs, logic errors), **security** (injection vulnerabilities, weak crypto), **performance** (algorithmic complexity), and **style** (readability, standards). 

This environment trains AI agents to perform structured, expert-level code review across all four dimensions — a skill that is immediately deployable in real engineering workflows.

**Why this matters:**
- Real-world task (not a toy problem or game)
- Requires multi-dimensional reasoning under incomplete information  
- Dense, incremental reward signal enables stable RL training
- Directly improves software quality and security when deployed

---

## 📐 Action & Observation Spaces

### Action Space: `CodeReviewAction`

```python
{
  "issues": [
    {
      "category":    "bug | security | style | performance | logic",
      "severity":    "low | medium | high | critical",
      "line_number": <int | null>,
      "description": "<clear description of the issue>",
      "suggestion":  "<concrete fix>"
    }
  ],
  "summary":  "<1-3 sentence overall assessment>",
  "approved": <bool>   # True = code is acceptable as-is
}
```

### Observation Space: `CodeReviewObservation`

```python
{
  "task_name":        "find_bug | security_audit | full_review",
  "task_description": "<what the agent should focus on>",
  "snippet": {
    "language":  "python",
    "filename":  "<filename.py>",
    "code":      "<source code to review>",
    "context":   "<what the code is supposed to do>"
  },
  "step_count":   <int>,
  "last_feedback": "<grader feedback from previous action | null>",
  "score_so_far": <float 0.0–1.0>,
  "done":         <bool>,
  "message":      "<informational message>"
}
```

### Reward Function

Reward is **incremental and dense** — the agent receives feedback at every step:

| Signal | Formula |
|---|---|
| Issue detection | `earned_points / total_points` |
| False positive penalty | `−min(0.30, false_positives × 0.05)` |
| Approval decision | `+0.10` correct / `−0.10` wrong |
| **Total** | `max(0.0, min(1.0, detection − fp_penalty ± approval))` |

Points are weighted by issue severity and importance. Critical security flaws are worth more than style issues.

---

## 📋 Tasks

### Task 1: `find_bug` — Easy

**Objective:** Identify logical and runtime bugs in a Python student utilities module.

**Known issues:**
- Off-by-one boundary condition (`>` vs `>=`) in grade threshold check  
- Off-by-one loop error (`range(n+1)` instead of `range(n)`)
- Missing empty-list guard causing `ZeroDivisionError`

**Max steps:** 3 | **Expected baseline:** ~0.55

---

### Task 2: `security_audit` — Medium

**Objective:** Detect all security vulnerabilities in a Flask authentication endpoint.

**Known issues:**
- **Critical:** SQL injection via f-string query interpolation
- **Critical:** Command injection via `shell=True` + unsanitized input
- **High:** Hardcoded secret key in source code
- **High:** MD5 used for password hashing (cryptographically broken)

**Max steps:** 4 | **Expected baseline:** ~0.40

---

### Task 3: `full_review` — Hard

**Objective:** Comprehensive review covering bugs, security, performance, and style.

**Known issues (8 total):**
- eval() on user-supplied input (critical security)
- Hardcoded admin password (high security)
- MD5 for integrity checks (medium security)
- KeyError on missing record key (high bug)
- Timing attack in password comparison (medium bug)
- O(n²) list lookup instead of set (medium performance)
- String concatenation in loop (low performance)
- Multiple imports on one line (low style)

**Max steps:** 5 | **Expected baseline:** ~0.25

---

## 🚀 Setup & Usage

### Quick Start (Local)

```bash
# 1. Clone and enter
git clone <your-repo>
cd code_review_env

# 2. Install dependencies
pip install -r server/requirements.txt

# 3. Start the server
uvicorn server.app:app --host 0.0.0.0 --port 8000

# 4. Open the web UI
open http://localhost:8000/web

# 5. Run validation (no pip needed)
python3 validate.py
```

### Docker

```bash
# Build
docker build -t code-review-env .

# Run
docker run -p 8000:8000 code-review-env

# Health check
curl http://localhost:8000/health
```

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET`  | `/` | Landing page |
| `GET`  | `/health` | Health check |
| `GET`  | `/tasks` | List all tasks |
| `POST` | `/reset?task_name=find_bug` | Start episode |
| `POST` | `/step?task_name=find_bug` | Submit review |
| `GET`  | `/state?task_name=find_bug` | Episode state |
| `WS`   | `/ws/{task_name}` | WebSocket interface |
| `GET`  | `/web` | Interactive UI |
| `GET`  | `/docs` | Swagger API docs |

### Running Inference

```bash
export HF_TOKEN=your_huggingface_token
export API_BASE_URL=https://api.openai.com/v1   # optional, has default
export MODEL_NAME=gpt-4.1-mini                  # optional, has default
export ENV_BASE_URL=http://localhost:8000        # optional

# Run single task
python3 inference.py find_bug

# Run all tasks
python3 inference.py all
```

**Output format:**
```
[START] task=find_bug env=code_review model=gpt-4.1-mini
[STEP] step=1 action=review(issues=3,cats=bug,bug,bug,approved=false) reward=0.72 done=false error=null
[STEP] step=2 action=review(issues=3,cats=bug,bug,bug,approved=false) reward=0.85 done=true error=null
[END] success=true steps=2 rewards=0.72,0.85
```

---

## 📊 Baseline Performance Scores

Measured using `gpt-4.1-mini` with the default inference script:

| Task | Difficulty | Baseline Score | Notes |
|---|---|---|---|
| `find_bug` | Easy | ~0.55 | Misses ZeroDivisionError guard |
| `security_audit` | Medium | ~0.40 | Often misses hardcoded key |
| `full_review` | Hard | ~0.25 | Rarely finds timing attack or style |
| **Average** | — | **~0.40** | Significant room for RL improvement |

---

## 🗂️ Project Structure

```
code_review_env/
├── inference.py          # ← Hackathon submission script (required in root)
├── openenv.yaml          # Environment manifest
├── models.py             # Pydantic Action/Observation/State models
├── tasks.py              # Task bank with code snippets + ground truth
├── grader.py             # Deterministic reward grader
├── validate.py           # Standalone test suite (stdlib only)
├── pyproject.toml        # Package config
├── Dockerfile            # Container definition
├── README.md             # This file
├── server/
│   ├── app.py            # FastAPI server + WebSocket + web UI
│   ├── environment.py    # Core environment logic (reset/step/state)
│   └── requirements.txt  # Python dependencies
└── tests/
    └── test_environment.py  # pytest test suite
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  inference.py (Agent)               │
│   OpenAI Client → prompt → parse JSON → action     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────┐
│              FastAPI Server (server/app.py)          │
│   /reset  /step  /state  /ws/{task}  /web           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│         CodeReviewEnvironment (server/environment.py)│
│   reset() → step(action) → state()                  │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
┌─────────▼──────┐       ┌─────────▼──────────┐
│  tasks.py       │       │  grader.py          │
│  3 task defs    │       │  deterministic      │
│  + ground truth │       │  keyword matching   │
└─────────────────┘       └────────────────────┘
```

---

## 🔬 Grading Methodology

The grader uses **keyword-based matching** against ground truth issues:

1. An agent issue **matches** a ground truth issue if:
   - `category` matches exactly (bug / security / style / performance / logic)
   - `description` OR `suggestion` contains **any** keyword from the ground truth keyword list

2. Each matched issue earns its assigned **point value**

3. **False positives** (issues with no ground truth match) incur a 0.05 penalty each (capped at 0.30)

4. Correct **approval decision** adds +0.10; wrong decision subtracts 0.10

This approach is deterministic, reproducible, and does not require an LLM for grading.

---

## 🤝 Contributing

Contributions welcome! Ideas:
- Add more code snippets per task for variety
- Add new task categories (e.g., `concurrency_review`, `api_design_review`)
- Improve keyword coverage in ground truth
- Add multi-language support (JavaScript, Go)

---

## 📄 License

BSD 3-Clause — see [LICENSE](LICENSE) file.

---

*Built for the Meta PyTorch × OpenEnv Hackathon 2026*
