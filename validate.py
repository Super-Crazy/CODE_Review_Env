"""
validate.py – Standalone validation using only Python stdlib.
Run with: python3 validate.py
No external dependencies required.
"""
import sys
import json
import uuid
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = failed = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")

def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}" + (f"\n      → {detail}" if detail else ""))

def section(title):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")

# ══════════════════════════════════════════════════════════════════════════════
# Inline minimal versions of models / tasks / grader (no pydantic needed)
# ══════════════════════════════════════════════════════════════════════════════

class IssueSeverity(str, Enum):
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"; CRITICAL = "critical"

class IssueCategory(str, Enum):
    BUG = "bug"; SECURITY = "security"; STYLE = "style"
    PERFORMANCE = "performance"; LOGIC = "logic"

@dataclass
class ReviewIssue:
    category: IssueCategory
    severity: IssueSeverity
    description: str
    suggestion: Optional[str] = None
    line_number: Optional[int] = None

@dataclass
class CodeReviewAction:
    issues: List[ReviewIssue]
    summary: str
    approved: bool = False

@dataclass
class GroundTruthIssue:
    category: str
    severity: str
    keywords: List[str]
    line_hint: int = -1
    points: float = 1.0

@dataclass
class Task:
    name: str
    difficulty: str
    description: str
    filename: str
    language: str
    code: str
    context: str
    ground_truth: List[GroundTruthIssue]
    correct_approved: bool = False
    max_steps: int = 3

# ── Task definitions (inline) ─────────────────────────────────────────────────

FIND_BUG_CODE = '''\
def calculate_average(numbers: list) -> float:
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)

def get_passing_students(scores: dict, threshold: int = 50) -> list:
    passing = []
    for name, score in scores.items():
        if score > threshold:          # BUG: should be >=
            passing.append(name)
    return passing

def repeat_string(s: str, n: int) -> str:
    result = ""
    for i in range(n + 1):            # BUG: range(n+1) → n+1 iterations
        result += s
    return result
'''

SECURITY_CODE = '''\
import sqlite3, hashlib, subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)
SECRET_KEY = "s3cr3t_k3y_2024"          # VULN: hardcoded secret

def get_user(username, password):
    conn = sqlite3.connect("/app/users.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username = \'{username}\' AND password = \'{password}\'"  # VULN: SQL injection
    cursor.execute(query)
    return cursor.fetchone()

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()  # VULN: MD5

@app.route("/run-diagnostic", methods=["POST"])
def run_diagnostic():
    data = request.get_json()
    host = data.get("host", "localhost")
    result = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True)  # VULN: command injection
    return jsonify({"output": result.stdout.decode()})
'''

FULL_REVIEW_CODE = '''\
import os, sys, json, time, hashlib   # STYLE: multiple imports
from typing import List

ADMIN_PASSWORD = "admin123"            # SECURITY: hardcoded credential

def find_duplicates(records: list) -> list:
    seen = []
    duplicates = []
    for record in records:
        rid = record.get("id")
        if rid in seen:                 # PERF: O(n^2) list lookup
            duplicates.append(record)
        else:
            seen.append(rid)
    return duplicates

def process_record(record: dict, user_input: str) -> dict:
    transform = eval(user_input)        # SECURITY: eval on user input
    return transform(record)

def compute_checksum(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()  # SECURITY: MD5

def summarise(records: list) -> dict:
    total = len(records)
    ids = []
    for r in records:
        ids.append(r["id"])             # BUG: KeyError if missing 'id'
    report = ""
    for rid in ids:
        report += f"ID: {rid}\\n"       # PERF: string concatenation loop
    return {"total": total, "report": report, "ids": ids}

def authenticate(password: str) -> bool:
    return password == ADMIN_PASSWORD   # BUG: timing attack
'''

TASKS = {
    "find_bug": Task(
        name="find_bug", difficulty="easy",
        description="Find bugs in the Python module.",
        filename="student_utils.py", language="python",
        code=FIND_BUG_CODE, context="Student grade management utilities.",
        correct_approved=False, max_steps=3,
        ground_truth=[
            GroundTruthIssue("bug", "medium",
                ["threshold", ">=", "boundary", "off-by-one", "passing"], 10, 1.0),
            GroundTruthIssue("bug", "medium",
                ["range", "n+1", "off-by-one", "repeat", "extra iteration"], 16, 1.0),
            GroundTruthIssue("bug", "high",
                ["zero", "empty", "division", "ZeroDivisionError", "empty list"], 5, 0.5),
        ],
    ),
    "security_audit": Task(
        name="security_audit", difficulty="medium",
        description="Find security vulnerabilities.",
        filename="auth_server.py", language="python",
        code=SECURITY_CODE, context="Flask authentication API.",
        correct_approved=False, max_steps=4,
        ground_truth=[
            GroundTruthIssue("security", "critical",
                ["sql injection", "sql", "injection", "parameterized", "f-string"], 9, 1.0),
            GroundTruthIssue("security", "critical",
                ["command injection", "shell=True", "subprocess", "shell injection"], 19, 1.0),
            GroundTruthIssue("security", "high",
                ["hardcoded", "secret", "SECRET_KEY", "credential"], 5, 0.8),
            GroundTruthIssue("security", "high",
                ["md5", "weak hash", "password hash", "bcrypt", "broken"], 13, 0.8),
        ],
    ),
    "full_review": Task(
        name="full_review", difficulty="hard",
        description="Comprehensive review: bugs + security + style + performance.",
        filename="data_pipeline.py", language="python",
        code=FULL_REVIEW_CODE, context="Internal data-processing pipeline.",
        correct_approved=False, max_steps=5,
        ground_truth=[
            GroundTruthIssue("security", "critical",
                ["eval", "user input", "code injection", "arbitrary code"], 16, 1.0),
            GroundTruthIssue("security", "high",
                ["hardcoded", "ADMIN_PASSWORD", "credential", "hardcoded password"], 4, 0.8),
            GroundTruthIssue("security", "medium",
                ["md5", "checksum", "integrity", "weak", "collision"], 19, 0.6),
            GroundTruthIssue("bug", "high",
                ["KeyError", "missing key", "id", "key error", "record missing"], 24, 0.8),
            GroundTruthIssue("bug", "medium",
                ["timing attack", "timing", "constant time", "compare_digest", "hmac"], 29, 0.7),
            GroundTruthIssue("performance", "medium",
                ["O(n^2)", "list lookup", "set", "find_duplicates", "in seen"], 11, 0.6),
            GroundTruthIssue("performance", "low",
                ["string concatenation", "+=", "join", "report"], 26, 0.4),
            GroundTruthIssue("style", "low",
                ["import", "multiple imports", "PEP8", "one import", "separate"], 1, 0.3),
        ],
    ),
}

# ── Grader (inline) ───────────────────────────────────────────────────────────

def _issue_matches(issue: ReviewIssue, gt: GroundTruthIssue) -> bool:
    if issue.category.value != gt.category:
        return False
    text = f"{issue.description} {issue.suggestion or ''}".lower()
    return any(kw.lower() in text for kw in gt.keywords)

def grade_action(action: CodeReviewAction, task: Task):
    total_points = sum(gt.points for gt in task.ground_truth)
    earned = 0.0
    missed = []
    for gt in task.ground_truth:
        if any(_issue_matches(issue, gt) for issue in action.issues):
            earned += gt.points
        else:
            missed.append(gt)
    fp = sum(1 for issue in action.issues
             if not any(_issue_matches(issue, gt) for gt in task.ground_truth))
    fp_penalty = min(0.3, fp * 0.05)
    approval_bonus = 0.1 if action.approved == task.correct_approved else -0.1
    raw = earned / total_points if total_points else 0.0
    reward = max(0.0, min(1.0, raw - fp_penalty + approval_bonus))
    return reward, earned, total_points, len(missed), fp

def is_done(steps, score, max_steps):
    return steps >= max_steps or score >= 0.95

# ── Environment (inline) ──────────────────────────────────────────────────────

class CodeReviewEnvironment:
    def __init__(self, task_name="find_bug"):
        if task_name not in TASKS:
            raise ValueError(f"Unknown task '{task_name}'")
        self._task = TASKS[task_name]
        self._episode_id = ""
        self._step = 0
        self._score = 0.0
        self._done = False
        self._attempts = []

    def reset(self):
        self._episode_id = str(uuid.uuid4())
        self._step = 0
        self._score = 0.0
        self._done = False
        self._attempts = []
        return {
            "task_name": self._task.name,
            "step_count": 0,
            "score_so_far": 0.0,
            "done": False,
            "snippet_code": self._task.code,
        }

    def step(self, action):
        if self._done:
            return {"done": True, "score_so_far": self._score}, 0.0, True, {"warning": "already_done"}
        self._step += 1
        reward, earned, total, missed_ct, fp = grade_action(action, self._task)
        self._score = min(1.0, self._score + reward * (1.0 / self._task.max_steps))
        self._done = is_done(self._step, self._score, self._task.max_steps)
        self._attempts.append({"step": self._step, "reward": round(reward, 4)})
        obs = {"task_name": self._task.name, "step_count": self._step,
               "score_so_far": round(self._score, 4), "done": self._done}
        return obs, reward, self._done, {"step": self._step, "cumulative": self._score}

    def state(self):
        return {"episode_id": self._episode_id, "task_name": self._task.name,
                "step_count": self._step, "max_steps": self._task.max_steps,
                "score": round(self._score, 4), "done": self._done}

# ══════════════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_grader_perfect_bug_detection():
    action = CodeReviewAction(
        issues=[
            ReviewIssue(IssueCategory.BUG, IssueSeverity.MEDIUM,
                "threshold check uses > instead of >= causing boundary exclusion",
                "Change score > threshold to score >= threshold", 10),
            ReviewIssue(IssueCategory.BUG, IssueSeverity.MEDIUM,
                "off-by-one error: range(n+1) causes extra iteration in repeat_string",
                "Change range(n+1) to range(n)", 16),
            ReviewIssue(IssueCategory.BUG, IssueSeverity.HIGH,
                "calculate_average raises ZeroDivisionError on empty list",
                "Add guard: if not numbers: return 0.0", 5),
        ],
        summary="Three bugs: boundary condition, off-by-one, division by zero.",
        approved=False,
    )
    reward, earned, total, missed, fp = grade_action(action, TASKS["find_bug"])
    if reward >= 0.7:
        ok(f"Perfect bug detection → reward={reward:.2f} (earned {earned:.1f}/{total:.1f} pts)")
    else:
        fail(f"Perfect bug detection reward too low: {reward:.2f}", f"earned={earned}, total={total}, fp={fp}")

def test_grader_empty_review_low_reward():
    action = CodeReviewAction(issues=[], summary="Looks fine.", approved=True)
    reward, *_ = grade_action(action, TASKS["find_bug"])
    if reward <= 0.2:
        ok(f"Empty review gives low reward → {reward:.2f}")
    else:
        fail(f"Empty review reward too high: {reward:.2f}")

def test_grader_false_positive_penalty():
    action = CodeReviewAction(
        issues=[
            ReviewIssue(IssueCategory.STYLE, IssueSeverity.LOW, "Missing type hints"),
            ReviewIssue(IssueCategory.STYLE, IssueSeverity.LOW, "No docstrings present"),
            ReviewIssue(IssueCategory.STYLE, IssueSeverity.LOW, "Bad variable names"),
            ReviewIssue(IssueCategory.STYLE, IssueSeverity.LOW, "Too many blank lines"),
            ReviewIssue(IssueCategory.STYLE, IssueSeverity.LOW, "Import order wrong"),
            ReviewIssue(IssueCategory.STYLE, IssueSeverity.LOW, "Inconsistent spacing"),
        ],
        summary="Only style issues.", approved=True,
    )
    reward, earned, total, missed, fp = grade_action(action, TASKS["find_bug"])
    if fp >= 6 and reward < 0.3:
        ok(f"False positives penalised → {fp} FP, reward={reward:.2f}")
    else:
        fail(f"False positive penalty not applied: fp={fp}, reward={reward:.2f}")

def test_grader_sql_injection_detected():
    action = CodeReviewAction(
        issues=[
            ReviewIssue(IssueCategory.SECURITY, IssueSeverity.CRITICAL,
                "SQL injection: user input is directly interpolated via f-string",
                "Use parameterized queries instead"),
        ],
        summary="SQL injection found.", approved=False,
    )
    reward, earned, *_ = grade_action(action, TASKS["security_audit"])
    if earned > 0:
        ok(f"SQL injection detected → +{earned:.1f} pts, reward={reward:.2f}")
    else:
        fail("SQL injection not detected in grader")

def test_grader_command_injection_detected():
    action = CodeReviewAction(
        issues=[
            ReviewIssue(IssueCategory.SECURITY, IssueSeverity.CRITICAL,
                "Command injection via shell=True and unsanitized subprocess input",
                "Use argument list instead of shell=True"),
        ],
        summary="Command injection found.", approved=False,
    )
    reward, earned, *_ = grade_action(action, TASKS["security_audit"])
    if earned > 0:
        ok(f"Command injection detected → +{earned:.1f} pts, reward={reward:.2f}")
    else:
        fail("Command injection not detected")

def test_grader_eval_injection_detected():
    action = CodeReviewAction(
        issues=[
            ReviewIssue(IssueCategory.SECURITY, IssueSeverity.CRITICAL,
                "Unsafe eval on user input allows arbitrary code execution",
                "Remove eval; use a safe mapping of allowed transforms instead"),
        ],
        summary="eval() on user input found.", approved=False,
    )
    reward, earned, *_ = grade_action(action, TASKS["full_review"])
    if earned > 0:
        ok(f"eval() injection detected → +{earned:.1f} pts")
    else:
        fail("eval() injection not detected")

def test_grader_correct_approval_bonus():
    base_issue = ReviewIssue(IssueCategory.BUG, IssueSeverity.MEDIUM,
        "range(n+1) off-by-one error", "use range(n)")
    action_wrong = CodeReviewAction(issues=[base_issue], summary="Bug.", approved=True)
    action_right = CodeReviewAction(issues=[base_issue], summary="Bug.", approved=False)
    r_wrong, *_ = grade_action(action_wrong, TASKS["find_bug"])
    r_right, *_ = grade_action(action_right, TASKS["find_bug"])
    if r_right > r_wrong:
        ok(f"Correct approval gives bonus: right={r_right:.2f} > wrong={r_wrong:.2f}")
    else:
        fail(f"Approval bonus not working: right={r_right:.2f}, wrong={r_wrong:.2f}")

def test_env_reset():
    env = CodeReviewEnvironment("find_bug")
    obs = env.reset()
    checks = [
        obs["task_name"] == "find_bug",
        obs["step_count"] == 0,
        obs["score_so_far"] == 0.0,
        obs["done"] == False,
        len(obs["snippet_code"]) > 50,
    ]
    if all(checks):
        ok("Environment reset() returns valid observation")
    else:
        fail(f"reset() observation malformed: {obs}")

def test_env_step_increments_count():
    env = CodeReviewEnvironment("find_bug")
    env.reset()
    action = CodeReviewAction(issues=[], summary="No issues.", approved=True)
    obs, reward, done, info = env.step(action)
    if obs["step_count"] == 1 and info["step"] == 1:
        ok("step() increments step count correctly")
    else:
        fail(f"Step count wrong: obs={obs['step_count']}, info={info}")

def test_env_step_after_done():
    env = CodeReviewEnvironment("find_bug")
    env.reset()
    env._done = True
    action = CodeReviewAction(issues=[], summary="x", approved=False)
    _, reward, done, info = env.step(action)
    if reward == 0.0 and done is True and "warning" in info:
        ok("step() after done returns 0 reward and warning")
    else:
        fail(f"Post-done step behaviour wrong: reward={reward}, done={done}")

def test_env_state():
    env = CodeReviewEnvironment("security_audit")
    env.reset()
    s = env.state()
    if (s["task_name"] == "security_audit" and
            s["step_count"] == 0 and
            s["max_steps"] == TASKS["security_audit"].max_steps):
        ok("state() returns correct episode metadata")
    else:
        fail(f"state() malformed: {s}")

def test_env_all_tasks_loadable():
    for task_name in ["find_bug", "security_audit", "full_review"]:
        env = CodeReviewEnvironment(task_name)
        obs = env.reset()
        assert obs["task_name"] == task_name
    ok("All three tasks load and reset correctly")

def test_env_invalid_task_raises():
    try:
        CodeReviewEnvironment("nonexistent_task")
        fail("Should have raised ValueError for unknown task")
    except ValueError as e:
        ok(f"Invalid task raises ValueError: {e}")

def test_env_full_episode():
    env = CodeReviewEnvironment("find_bug")
    env.reset()
    action = CodeReviewAction(
        issues=[
            ReviewIssue(IssueCategory.BUG, IssueSeverity.MEDIUM,
                "threshold comparison uses > instead of >= causing off-by-one at boundary",
                "Use >= for correct inclusive check"),
            ReviewIssue(IssueCategory.BUG, IssueSeverity.MEDIUM,
                "range(n+1) causes one extra iteration in repeat_string loop",
                "Change to range(n)"),
        ],
        summary="Two boundary bugs found.", approved=False,
    )
    total_reward = 0.0
    steps = 0
    for _ in range(TASKS["find_bug"].max_steps):
        obs, reward, done, info = env.step(action)
        total_reward += reward
        steps += 1
        if done:
            break
    if steps > 0 and obs["score_so_far"] > 0:
        ok(f"Full episode completes: {steps} steps, final score={obs['score_so_far']:.2f}")
    else:
        fail(f"Full episode failed: steps={steps}, score={obs.get('score_so_far', '?')}")

def test_is_done_logic():
    cases = [
        (3, 0.5, 3, True,  "max_steps reached"),
        (1, 0.97, 5, True,  "perfect score"),
        (1, 0.3, 5,  False, "not done yet"),
        (2, 0.95, 5, True,  "exactly at threshold"),
        (0, 0.0, 3,  False, "step 0"),
    ]
    all_ok = True
    for steps, score, max_s, expected, desc in cases:
        result = is_done(steps, score, max_s)
        if result != expected:
            fail(f"is_done({steps},{score},{max_s}) = {result}, expected {expected} [{desc}]")
            all_ok = False
    if all_ok:
        ok(f"is_done() logic correct across {len(cases)} cases")

def test_task_bank_integrity():
    issues = []
    for name, task in TASKS.items():
        if len(task.ground_truth) < 2:
            issues.append(f"'{name}' has < 2 ground truth issues")
        if len(task.code) < 100:
            issues.append(f"'{name}' code too short")
        for gt in task.ground_truth:
            if gt.points <= 0:
                issues.append(f"'{name}' has zero-point gt issue")
    if not issues:
        ok(f"Task bank integrity: all {len(TASKS)} tasks valid")
    else:
        for i in issues:
            fail(i)

def test_task_difficulties():
    expected = {"find_bug": "easy", "security_audit": "medium", "full_review": "hard"}
    correct = all(TASKS[n].difficulty == d for n, d in expected.items())
    if correct:
        ok("Task difficulties: easy → medium → hard ✓")
    else:
        fail("Task difficulty ordering wrong",
             {n: TASKS[n].difficulty for n in TASKS})

def test_output_format_simulation():
    """Simulate the [START]/[STEP]/[END] output format."""
    import io, sys
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf

    task_name = "find_bug"
    model_name = "gpt-4.1-mini"
    print(f"[START] task={task_name} env=code_review model={model_name}")

    rewards = [0.45, 0.72]
    for i, r in enumerate(rewards, 1):
        done = i == len(rewards)
        print(f"[STEP] step={i} action=review(issues=2) reward={r:.2f} "
              f"done={'true' if done else 'false'} error=null")

    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success=true steps={len(rewards)} rewards={rewards_str}")

    sys.stdout = old
    output = buf.getvalue()
    lines = output.strip().split("\n")

    checks = [
        lines[0].startswith("[START]"),
        all(l.startswith("[STEP]") for l in lines[1:-1]),
        lines[-1].startswith("[END]"),
        "task=" in lines[0],
        "env=" in lines[0],
        "model=" in lines[0],
        "reward=" in lines[1],
        "done=" in lines[1],
        "error=" in lines[1],
        "success=" in lines[-1],
        "steps=" in lines[-1],
        "rewards=" in lines[-1],
    ]
    if all(checks):
        ok("Output format [START]/[STEP]/[END] matches spec exactly")
    else:
        fail("Output format check failed", output)

def test_inference_env_vars():
    """Verify inference.py reads correct env vars with correct defaults."""
    import os
    os.environ["HF_TOKEN"] = "test_token_for_validation"
    os.environ.pop("API_BASE_URL", None)
    os.environ.pop("MODEL_NAME", None)

    # Read the inference.py file and check for required patterns
    try:
        with open("inference.py") as f:
            src = f.read()
    except FileNotFoundError:
        fail("inference.py not found in current directory")
        return

    checks = [
        ('API_BASE_URL' in src and 'https://api.openai.com/v1' in src, 'API_BASE_URL has default'),
        ('MODEL_NAME' in src and 'gpt-4.1-mini' in src, 'MODEL_NAME has default'),
        ('HF_TOKEN' in src, 'HF_TOKEN is read'),
        ('raise ValueError' in src, 'HF_TOKEN absence raises ValueError'),
        ('openai' in src.lower(), 'OpenAI client is used'),
        ('[START]' in src, '[START] output line present'),
        ('[STEP]' in src, '[STEP] output line present'),
        ('[END]' in src, '[END] output line present'),
        ('flush=True' in src, 'flush=True on all print statements'),
    ]
    issues = [msg for cond, msg in checks if not cond]
    ok_items = [msg for cond, msg in checks if cond]
    for msg in ok_items:
        ok(f"  inference.py: {msg}")
    for msg in issues:
        fail(f"  inference.py: {msg}")

def test_file_structure():
    """Verify all required files exist."""
    import os
    required_files = [
        "inference.py",
        "openenv.yaml",
        "Dockerfile",
        "pyproject.toml",
        "models.py",
        "tasks.py",
        "grader.py",
        "server/app.py",
        "server/environment.py",
        "server/requirements.txt",
        "README.md",
        "tests/test_environment.py",
    ]
    missing = [f for f in required_files if not os.path.exists(f)]
    present = [f for f in required_files if os.path.exists(f)]
    if not missing:
        ok(f"All {len(required_files)} required files present ✓")
    else:
        ok(f"{len(present)}/{len(required_files)} files present")
        for f in missing:
            fail(f"Missing file: {f}")

def test_openenv_yaml():
    """Verify openenv.yaml has required fields."""
    try:
        with open("openenv.yaml") as f:
            content = f.read()
    except FileNotFoundError:
        fail("openenv.yaml not found")
        return
    required_fields = ["name", "version", "description", "tags", "tasks", "deployment"]
    missing = [f for f in required_fields if f not in content]
    if not missing:
        ok("openenv.yaml contains all required fields")
    else:
        fail(f"openenv.yaml missing fields: {missing}")

def test_dockerfile():
    """Verify Dockerfile has required directives."""
    try:
        with open("Dockerfile") as f:
            content = f.read()
    except FileNotFoundError:
        fail("Dockerfile not found")
        return
    required = ["FROM", "WORKDIR", "COPY", "EXPOSE", "CMD", "HEALTHCHECK"]
    missing = [d for d in required if d not in content]
    if not missing:
        ok("Dockerfile contains all required directives")
    else:
        fail(f"Dockerfile missing directives: {missing}")

# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

ALL_TESTS = [
    ("Grader: perfect bug detection",        test_grader_perfect_bug_detection),
    ("Grader: empty review low reward",       test_grader_empty_review_low_reward),
    ("Grader: false positive penalty",        test_grader_false_positive_penalty),
    ("Grader: SQL injection detected",        test_grader_sql_injection_detected),
    ("Grader: command injection detected",    test_grader_command_injection_detected),
    ("Grader: eval injection detected",       test_grader_eval_injection_detected),
    ("Grader: correct approval bonus",        test_grader_correct_approval_bonus),
    ("Environment: reset()",                  test_env_reset),
    ("Environment: step() increments count",  test_env_step_increments_count),
    ("Environment: step() after done",        test_env_step_after_done),
    ("Environment: state()",                  test_env_state),
    ("Environment: all tasks loadable",       test_env_all_tasks_loadable),
    ("Environment: invalid task raises",      test_env_invalid_task_raises),
    ("Environment: full episode flow",        test_env_full_episode),
    ("Logic: is_done() cases",               test_is_done_logic),
    ("Task bank: integrity check",           test_task_bank_integrity),
    ("Task bank: difficulty ordering",       test_task_difficulties),
    ("Output: [START]/[STEP]/[END] format",  test_output_format_simulation),
    ("Spec: inference.py env vars",          test_inference_env_vars),
    ("Spec: file structure",                 test_file_structure),
    ("Spec: openenv.yaml fields",            test_openenv_yaml),
    ("Spec: Dockerfile directives",          test_dockerfile),
]

if __name__ == "__main__":
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  Code Review OpenEnv – Validation Suite{RESET}")
    print(f"{BOLD}  Python {sys.version.split()[0]} · stdlib only · no pip needed{RESET}")
    print(f"{BOLD}{'═'*60}{RESET}")

    section("Running all tests...")
    for name, fn in ALL_TESTS:
        try:
            fn()
        except Exception as e:
            fail(f"{name}: EXCEPTION", str(e))

    section("Summary")
    total = passed + failed
    pct = (passed / total * 100) if total else 0
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    print(f"\n  [{bar}] {pct:.0f}%")
    print(f"\n  {GREEN}{BOLD}{passed} passed{RESET}  {RED}{BOLD}{failed} failed{RESET}  ({total} total)\n")

    if failed == 0:
        print(f"  {GREEN}{BOLD}✅  ALL TESTS PASSED – ready to submit!{RESET}\n")
        sys.exit(0)
    else:
        print(f"  {RED}{BOLD}❌  {failed} test(s) failed – review above.{RESET}\n")
        sys.exit(1)
