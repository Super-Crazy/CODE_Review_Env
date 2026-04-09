"""
Tests for the Code Review OpenEnv environment.
Run with: pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from models import CodeReviewAction, ReviewIssue, IssueCategory, IssueSeverity
from tasks import TASKS, FIND_BUG_TASK, SECURITY_AUDIT_TASK, FULL_REVIEW_TASK
from grader import grade_action, is_episode_done
from server.environment import CodeReviewEnvironment


# ── Grader Tests ───────────────────────────────────────────────────────────────

class TestGrader:

    def test_perfect_bug_detection(self):
        """Correctly identifying all bugs gives high reward."""
        action = CodeReviewAction(
            issues=[
                ReviewIssue(
                    category=IssueCategory.BUG,
                    severity=IssueSeverity.MEDIUM,
                    description="The threshold check uses > instead of >= so students scoring exactly at threshold are incorrectly excluded",
                    suggestion="Change 'score > threshold' to 'score >= threshold'",
                    line_number=13,
                ),
                ReviewIssue(
                    category=IssueCategory.BUG,
                    severity=IssueSeverity.MEDIUM,
                    description="range(n+1) causes an off-by-one error, the string repeats n+1 times instead of n",
                    suggestion="Change range(n+1) to range(n)",
                    line_number=20,
                ),
                ReviewIssue(
                    category=IssueCategory.BUG,
                    severity=IssueSeverity.HIGH,
                    description="calculate_average raises ZeroDivisionError on an empty list",
                    suggestion="Add guard: if not numbers: return 0.0",
                    line_number=6,
                ),
            ],
            summary="Three bugs found: boundary condition error, off-by-one loop, and missing empty list guard.",
            approved=False,
        )
        reward, feedback = grade_action(action, FIND_BUG_TASK)
        assert reward >= 0.7, f"Expected high reward, got {reward}: {feedback}"

    def test_zero_reward_empty_review(self):
        """Empty issues list should give low reward."""
        action = CodeReviewAction(
            issues=[],
            summary="Code looks fine.",
            approved=True,  # Wrong: should not be approved
        )
        reward, feedback = grade_action(action, FIND_BUG_TASK)
        assert reward <= 0.2, f"Expected low reward for empty review, got {reward}"

    def test_false_positive_penalty(self):
        """Invented issues that don't match ground truth reduce score."""
        action = CodeReviewAction(
            issues=[
                ReviewIssue(
                    category=IssueCategory.STYLE,
                    severity=IssueSeverity.LOW,
                    description="Missing type hints everywhere",
                    line_number=1,
                ),
                ReviewIssue(
                    category=IssueCategory.STYLE,
                    severity=IssueSeverity.LOW,
                    description="No docstring on function body",
                    line_number=5,
                ),
                ReviewIssue(
                    category=IssueCategory.STYLE,
                    severity=IssueSeverity.LOW,
                    description="Variable names could be more descriptive",
                    line_number=3,
                ),
            ],
            summary="Some style issues.",
            approved=True,
        )
        reward, feedback = grade_action(action, FIND_BUG_TASK)
        assert reward < 0.3

    def test_security_sql_injection_detected(self):
        """SQL injection detection gives reward."""
        action = CodeReviewAction(
            issues=[
                ReviewIssue(
                    category=IssueCategory.SECURITY,
                    severity=IssueSeverity.CRITICAL,
                    description="SQL injection vulnerability: user input is directly interpolated into the SQL query via f-string",
                    suggestion="Use parameterized queries: cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))",
                    line_number=15,
                ),
            ],
            summary="Critical SQL injection found.",
            approved=False,
        )
        reward, feedback = grade_action(action, SECURITY_AUDIT_TASK)
        assert reward > 0.0

    def test_command_injection_detected(self):
        """Command injection detection gives reward."""
        action = CodeReviewAction(
            issues=[
                ReviewIssue(
                    category=IssueCategory.SECURITY,
                    severity=IssueSeverity.CRITICAL,
                    description="Command injection: shell=True with unsanitized user input in subprocess.run allows arbitrary command execution",
                    suggestion="Use a list of arguments instead: subprocess.run(['ping', '-c', '1', host], capture_output=True)",
                    line_number=36,
                ),
            ],
            summary="Command injection vulnerability.",
            approved=False,
        )
        reward, feedback = grade_action(action, SECURITY_AUDIT_TASK)
        assert reward > 0.0

    def test_approval_bonus_correct(self):
        """Correct approval decision adds small bonus."""
        # For find_bug task, correct_approved=False
        action_wrong_approval = CodeReviewAction(
            issues=[
                ReviewIssue(
                    category=IssueCategory.BUG,
                    severity=IssueSeverity.MEDIUM,
                    description="off-by-one error in range(n+1) causes too many iterations",
                    suggestion="use range(n)",
                ),
            ],
            summary="Bug found.",
            approved=True,  # WRONG: should be False
        )
        action_right_approval = CodeReviewAction(
            issues=[
                ReviewIssue(
                    category=IssueCategory.BUG,
                    severity=IssueSeverity.MEDIUM,
                    description="off-by-one error in range(n+1) causes too many iterations",
                    suggestion="use range(n)",
                ),
            ],
            summary="Bug found.",
            approved=False,  # CORRECT
        )
        r_wrong, _ = grade_action(action_wrong_approval, FIND_BUG_TASK)
        r_right, _ = grade_action(action_right_approval, FIND_BUG_TASK)
        assert r_right > r_wrong


# ── Environment Tests ──────────────────────────────────────────────────────────

class TestEnvironment:

    def test_reset_returns_observation(self):
        env = CodeReviewEnvironment(task_name="find_bug")
        obs = env.reset()
        assert obs.task_name == "find_bug"
        assert obs.step_count == 0
        assert obs.score_so_far == 0.0
        assert not obs.done
        assert obs.snippet.code  # non-empty code

    def test_step_increments_step_count(self):
        env = CodeReviewEnvironment(task_name="find_bug")
        env.reset()
        action = CodeReviewAction(
            issues=[],
            summary="No issues found.",
            approved=True,
        )
        obs, reward, done, info = env.step(action)
        assert obs.step_count == 1
        assert info["step"] == 1

    def test_step_after_done_returns_zero_reward(self):
        env = CodeReviewEnvironment(task_name="find_bug")
        env.reset()
        # Force completion
        env._done = True
        action = CodeReviewAction(issues=[], summary="x", approved=False)
        obs, reward, done, info = env.step(action)
        assert reward == 0.0
        assert done is True

    def test_state_returns_episode_info(self):
        env = CodeReviewEnvironment(task_name="security_audit")
        env.reset()
        state = env.state()
        assert state.task_name == "security_audit"
        assert state.step_count == 0
        assert state.max_steps == SECURITY_AUDIT_TASK.max_steps

    def test_all_tasks_loadable(self):
        for task_name in ["find_bug", "security_audit", "full_review"]:
            env = CodeReviewEnvironment(task_name=task_name)
            obs = env.reset()
            assert obs.task_name == task_name
            assert len(obs.snippet.code) > 50

    def test_invalid_task_raises(self):
        with pytest.raises(ValueError, match="Unknown task"):
            CodeReviewEnvironment(task_name="nonexistent_task")

    def test_full_episode_flow(self):
        """Complete episode: reset → multiple steps → done."""
        env = CodeReviewEnvironment(task_name="find_bug")
        obs = env.reset()
        assert not obs.done

        total_reward = 0.0
        for _ in range(FIND_BUG_TASK.max_steps):
            action = CodeReviewAction(
                issues=[
                    ReviewIssue(
                        category=IssueCategory.BUG,
                        severity=IssueSeverity.MEDIUM,
                        description="threshold check uses > instead of >= causing boundary exclusion",
                        suggestion="use >= for correct inclusive comparison",
                    )
                ],
                summary="Found a boundary bug.",
                approved=False,
            )
            obs, reward, done, info = env.step(action)
            total_reward += reward
            if done:
                break

        assert obs.step_count > 0
        assert obs.score_so_far >= 0.0


# ── Episode Done Logic Tests ───────────────────────────────────────────────────

class TestEpisodeDone:

    def test_done_at_max_steps(self):
        assert is_episode_done(3, 0.5, 3) is True

    def test_done_at_perfect_score(self):
        assert is_episode_done(1, 0.97, 5) is True

    def test_not_done_early(self):
        assert is_episode_done(1, 0.3, 5) is False

    def test_done_exactly_at_threshold(self):
        assert is_episode_done(2, 0.95, 5) is True


# ── Task Bank Integrity Tests ──────────────────────────────────────────────────

class TestTaskBank:

    def test_all_tasks_have_ground_truth(self):
        for name, task in TASKS.items():
            assert len(task.ground_truth) >= 2, f"Task '{name}' needs >= 2 ground truth issues"

    def test_task_difficulties_ordered(self):
        difficulties = {
            "find_bug": "easy",
            "security_audit": "medium",
            "full_review": "hard",
        }
        for name, expected_diff in difficulties.items():
            assert TASKS[name].difficulty == expected_diff

    def test_tasks_have_non_empty_code(self):
        for name, task in TASKS.items():
            assert len(task.code) > 100, f"Task '{name}' code seems too short"

    def test_ground_truth_points_positive(self):
        for name, task in TASKS.items():
            for gt in task.ground_truth:
                assert gt.points > 0, f"Task '{name}' has zero-point ground truth"
