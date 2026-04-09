"""
Code Review Environment – Task Bank
Contains code snippets with known issues for deterministic grading.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Set


@dataclass
class GroundTruthIssue:
    """Represents a known issue in a code snippet."""
    category: str          # bug | security | style | performance | logic
    severity: str          # low | medium | high | critical
    keywords: List[str]    # keywords that a valid detection must contain (ANY match)
    line_hint: int = -1    # approximate line number (-1 = not line-specific)
    points: float = 1.0    # reward points for correct detection


@dataclass
class Task:
    """A complete task definition."""
    name: str
    difficulty: str
    description: str
    filename: str
    language: str
    code: str
    context: str
    ground_truth: List[GroundTruthIssue]
    correct_approved: bool = False  # should agent approve or reject?
    max_steps: int = 3


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 – EASY: find_bug
# A simple user-registration function with an obvious off-by-one / logic bug
# ─────────────────────────────────────────────────────────────────────────────
FIND_BUG_CODE = '''\
def calculate_average(numbers: list) -> float:
    """Return the average of a list of numbers."""
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)


def get_passing_students(scores: dict, threshold: int = 50) -> list:
    """Return names of students who scored >= threshold."""
    passing = []
    for name, score in scores.items():
        if score > threshold:          # BUG: should be >= not >
            passing.append(name)
    return passing


def repeat_string(s: str, n: int) -> str:
    """Repeat string s exactly n times."""
    result = ""
    for i in range(n + 1):            # BUG: range(n+1) loops n+1 times, not n
        result += s
    return result
'''

FIND_BUG_TASK = Task(
    name="find_bug",
    difficulty="easy",
    description=(
        "Review the following Python module and identify any logical or runtime bugs. "
        "Focus on correctness issues—does the code do what the docstring says it should do?"
    ),
    filename="student_utils.py",
    language="python",
    code=FIND_BUG_CODE,
    context="Utility functions used in a student grade management system.",
    correct_approved=False,
    max_steps=3,
    ground_truth=[
        GroundTruthIssue(
            category="bug",
            severity="medium",
            keywords=["threshold", ">=", "greater than or equal", "boundary", "off-by-one", "passing"],
            line_hint=13,
            points=1.0,
        ),
        GroundTruthIssue(
            category="bug",
            severity="medium",
            keywords=["range", "n+1", "off-by-one", "repeat", "extra iteration", "one extra"],
            line_hint=20,
            points=1.0,
        ),
        GroundTruthIssue(
            category="bug",
            severity="high",
            keywords=["zero", "empty", "division", "ZeroDivisionError", "empty list"],
            line_hint=6,
            points=0.5,
        ),
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 – MEDIUM: security_audit
# A Flask login endpoint with multiple classic security vulnerabilities
# ─────────────────────────────────────────────────────────────────────────────
SECURITY_AUDIT_CODE = '''\
import sqlite3
import hashlib
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)
SECRET_KEY = "s3cr3t_k3y_2024"          # VULN: hardcoded secret
DB_PATH = "/app/users.db"


def get_user(username: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # VULN: SQL injection – parameters interpolated directly
    query = f"SELECT * FROM users WHERE username = \'{username}\' AND password = \'{password}\'"
    cursor.execute(query)
    return cursor.fetchone()


def hash_password(password: str) -> str:
    # VULN: MD5 is cryptographically broken for passwords
    return hashlib.md5(password.encode()).hexdigest()


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    user = get_user(username, hash_password(password))
    if user:
        return jsonify({"status": "ok", "token": SECRET_KEY})
    return jsonify({"status": "fail"}), 401


@app.route("/run-diagnostic", methods=["POST"])
def run_diagnostic():
    data = request.get_json()
    host = data.get("host", "localhost")
    # VULN: command injection via shell=True + unsanitised input
    result = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True)
    return jsonify({"output": result.stdout.decode()})
'''

SECURITY_AUDIT_TASK = Task(
    name="security_audit",
    difficulty="medium",
    description=(
        "Perform a security audit of this Flask login endpoint. "
        "Identify all security vulnerabilities with their severity and suggest fixes. "
        "Do NOT report style issues—focus only on security."
    ),
    filename="auth_server.py",
    language="python",
    code=SECURITY_AUDIT_CODE,
    context="A Flask REST API used for user authentication in a web application.",
    correct_approved=False,
    max_steps=4,
    ground_truth=[
        GroundTruthIssue(
            category="security",
            severity="critical",
            keywords=["sql injection", "sql", "injection", "parameterized", "f-string", "format"],
            line_hint=15,
            points=1.0,
        ),
        GroundTruthIssue(
            category="security",
            severity="critical",
            keywords=["command injection", "shell=True", "subprocess", "shell injection", "os injection", "ping"],
            line_hint=36,
            points=1.0,
        ),
        GroundTruthIssue(
            category="security",
            severity="high",
            keywords=["hardcoded", "secret", "SECRET_KEY", "hardcoded secret", "credential"],
            line_hint=7,
            points=0.8,
        ),
        GroundTruthIssue(
            category="security",
            severity="high",
            keywords=["md5", "weak hash", "password hash", "bcrypt", "argon", "pbkdf2", "broken"],
            line_hint=21,
            points=0.8,
        ),
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 – HARD: full_review
# A data-processing pipeline with bugs, security, style, AND performance issues
# ─────────────────────────────────────────────────────────────────────────────
FULL_REVIEW_CODE = '''\
import os, sys, json, time, hashlib   # STYLE: multiple imports on one line
from typing import List


ADMIN_PASSWORD = "admin123"            # SECURITY: hardcoded credential


def load_records(filepath: str) -> list:
    """Load JSON records from a file."""
    with open(filepath, "r") as f:
        data = json.load(f)
    return data


def find_duplicates(records: list) -> list:
    """Return records that appear more than once (by \'id\' field)."""
    seen = []
    duplicates = []
    for record in records:
        rid = record.get("id")
        if rid in seen:                 # PERF: O(n^2) – list lookup; should use a set
            duplicates.append(record)
        else:
            seen.append(rid)
    return duplicates


def process_record(record: dict, user_input: str) -> dict:
    """Process a record, optionally applying a user-supplied transform."""
    # SECURITY: eval on user input
    transform = eval(user_input)        # noqa
    result = transform(record)
    return result


def compute_checksum(data: str) -> str:
    """Return a checksum for audit logging."""
    return hashlib.md5(data.encode()).hexdigest()  # SECURITY: MD5 not suitable for integrity


def summarise(records: list) -> dict:
    """Return aggregate stats."""
    total = len(records)
    ids = []
    for r in records:
        ids.append(r["id"])             # BUG: KeyError if record missing \'id\'

    # PERF: string concatenation in loop is O(n^2)
    report = ""
    for rid in ids:
        report += f"ID: {rid}\\n"

    return {"total": total, "report": report, "ids": ids}


def authenticate(password: str) -> bool:
    # BUG: timing attack – direct string comparison
    return password == ADMIN_PASSWORD
'''

FULL_REVIEW_TASK = Task(
    name="full_review",
    difficulty="hard",
    description=(
        "Perform a comprehensive code review covering bugs, security vulnerabilities, "
        "style issues, and performance problems. Be thorough and precise. "
        "Each finding should include the line number, category, severity, and a concrete fix."
    ),
    filename="data_pipeline.py",
    language="python",
    code=FULL_REVIEW_CODE,
    context=(
        "A data-processing pipeline used internally. It loads records from disk, "
        "deduplicates them, and generates a summary report."
    ),
    correct_approved=False,
    max_steps=5,
    ground_truth=[
        GroundTruthIssue(
            category="security",
            severity="critical",
            keywords=["eval", "user input", "code injection", "arbitrary code", "remote code"],
            line_hint=29,
            points=1.0,
        ),
        GroundTruthIssue(
            category="security",
            severity="high",
            keywords=["hardcoded", "ADMIN_PASSWORD", "credential", "hardcoded password"],
            line_hint=6,
            points=0.8,
        ),
        GroundTruthIssue(
            category="security",
            severity="medium",
            keywords=["md5", "checksum", "integrity", "weak", "collision"],
            line_hint=34,
            points=0.6,
        ),
        GroundTruthIssue(
            category="bug",
            severity="high",
            keywords=["KeyError", "missing key", "id", "key error", "record missing"],
            line_hint=41,
            points=0.8,
        ),
        GroundTruthIssue(
            category="bug",
            severity="medium",
            keywords=["timing attack", "timing", "constant time", "compare_digest", "hmac"],
            line_hint=50,
            points=0.7,
        ),
        GroundTruthIssue(
            category="performance",
            severity="medium",
            keywords=["O(n^2)", "list lookup", "set", "find_duplicates", "in seen", "linear search"],
            line_hint=19,
            points=0.6,
        ),
        GroundTruthIssue(
            category="performance",
            severity="low",
            keywords=["string concatenation", "+=", "join", "O(n^2)", "loop", "report"],
            line_hint=45,
            points=0.4,
        ),
        GroundTruthIssue(
            category="style",
            severity="low",
            keywords=["import", "multiple imports", "PEP8", "one import", "separate"],
            line_hint=1,
            points=0.3,
        ),
    ],
)

TASKS: Dict[str, Task] = {
    "find_bug": FIND_BUG_TASK,
    "security_audit": SECURITY_AUDIT_TASK,
    "full_review": FULL_REVIEW_TASK,
}
