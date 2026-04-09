"""
Code Review Environment – Pydantic Models
Defines Action, Observation, and State for the OpenEnv interface.
"""
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    STYLE = "style"
    PERFORMANCE = "performance"
    LOGIC = "logic"


class ReviewIssue(BaseModel):
    """A single issue found during code review."""
    category: IssueCategory = Field(..., description="Type of issue")
    severity: IssueSeverity = Field(..., description="Severity level")
    line_number: Optional[int] = Field(None, description="Line number (1-indexed), if applicable")
    description: str = Field(..., description="Clear description of the issue")
    suggestion: Optional[str] = Field(None, description="Suggested fix or improvement")


class CodeReviewAction(BaseModel):
    """
    Action submitted by the agent: a structured code review.
    The agent provides a list of issues found and an overall summary.
    """
    issues: List[ReviewIssue] = Field(
        default_factory=list,
        description="List of issues found in the code"
    )
    summary: str = Field(
        ...,
        description="Overall review summary (1-3 sentences)"
    )
    approved: bool = Field(
        False,
        description="Whether the code is approved (True = looks good, False = needs changes)"
    )


class CodeSnippet(BaseModel):
    """A code snippet presented to the agent for review."""
    language: str = Field(default="python", description="Programming language")
    filename: str = Field(..., description="Filename for context")
    code: str = Field(..., description="The code to review")
    context: Optional[str] = Field(None, description="Additional context (e.g. what the code is supposed to do)")


class CodeReviewObservation(BaseModel):
    """
    Observation returned to the agent after reset() or step().
    Contains the code to review, task instructions, and feedback from prior action.
    """
    task_name: str = Field(..., description="Current task: find_bug | security_audit | full_review")
    task_description: str = Field(..., description="What the agent should do")
    snippet: CodeSnippet = Field(..., description="Code snippet to review")
    step_count: int = Field(0, description="Current step number")
    last_feedback: Optional[str] = Field(None, description="Feedback from last action (if any)")
    score_so_far: float = Field(0.0, description="Cumulative score in this episode [0.0, 1.0]")
    done: bool = Field(False, description="Whether the episode is complete")
    message: str = Field("", description="Informational message")


class EpisodeState(BaseModel):
    """Internal episode state (returned by state() endpoint)."""
    episode_id: str
    task_name: str
    step_count: int
    max_steps: int
    score: float
    done: bool
    attempts: List[Dict[str, Any]] = Field(default_factory=list)
