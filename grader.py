"""
Code Review Environment – Grader
Deterministic, reproducible scoring for all three tasks.
"""
from __future__ import annotations
from typing import List, Tuple

from models import CodeReviewAction, ReviewIssue
from tasks import Task, GroundTruthIssue


def _issue_matches_ground_truth(issue: ReviewIssue, gt: GroundTruthIssue) -> bool:
    """
    Returns True if a submitted ReviewIssue covers a ground-truth issue.
    Matching rules:
      1. category must match (exact)
      2. description OR suggestion must contain at least one keyword (case-insensitive)
    Line-number check is soft (±3 lines) but not required.
    """
    if issue.category.value != gt.category:
        return False

    text = f"{issue.description} {issue.suggestion or ''}".lower()
    return any(kw.lower() in text for kw in gt.keywords)


def grade_action(action: CodeReviewAction, task: Task) -> Tuple[float, str]:
    """
    Grade a single CodeReviewAction against the task's ground truth.

    Returns
    -------
    reward : float  – incremental reward in [0.0, 1.0]
    feedback : str  – human-readable feedback for the agent
    """
    total_points = sum(gt.points for gt in task.ground_truth)
    earned_points = 0.0
    matched_gts: List[int] = []
    missed_gts: List[GroundTruthIssue] = []
    false_positives = 0

    for gt_idx, gt in enumerate(task.ground_truth):
        matched = False
        for issue in action.issues:
            if _issue_matches_ground_truth(issue, gt):
                matched = True
                break
        if matched:
            earned_points += gt.points
            matched_gts.append(gt_idx)
        else:
            missed_gts.append(gt)

    # Penalty for false positives (spurious issues not in ground truth)
    for issue in action.issues:
        covers_any = any(
            _issue_matches_ground_truth(issue, gt) for gt in task.ground_truth
        )
        if not covers_any:
            false_positives += 1

    fp_penalty = min(0.3, false_positives * 0.05)

    # Approval bonus/malus
    approval_bonus = 0.0
    if action.approved == task.correct_approved:
        approval_bonus = 0.1
    else:
        approval_bonus = -0.1

    raw_score = (earned_points / total_points) if total_points > 0 else 0.0
    reward = max(0.0, min(1.0, raw_score - fp_penalty + approval_bonus))
    # Scores must be strictly between 0 and 1 (not 0.0, not 1.0)
    reward = max(0.01, min(0.99, reward))

    # Build feedback message
    found_count = len(matched_gts)
    total_count = len(task.ground_truth)
    lines = [
        f"✅ Found {found_count}/{total_count} issues (+{earned_points:.1f}/{total_points:.1f} pts).",
    ]
    if false_positives:
        lines.append(f"⚠️  {false_positives} false positive(s) detected (−{fp_penalty:.2f} penalty).")
    if missed_gts:
        hints = [f"[{g.category}/{g.severity}]" for g in missed_gts[:3]]
        lines.append(f"❌ Missed: {', '.join(hints)}.")
    if action.approved != task.correct_approved:
        lines.append("⚠️  Approval decision was incorrect.")
    lines.append(f"📊 Step reward: {reward:.2f}")
    feedback = " ".join(lines)

    return reward, feedback


def is_episode_done(step_count: int, cumulative_reward: float, max_steps: int) -> bool:
    """Episode ends when agent reaches max_steps or achieves perfect score."""
    return step_count >= max_steps or cumulative_reward >= 0.95
