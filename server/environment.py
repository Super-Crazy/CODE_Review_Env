"""
Code Review Environment – Server-Side Environment Logic
Implements the OpenEnv interface: reset(), step(), state()
"""
from __future__ import annotations
import uuid
from typing import Tuple, Dict, Any

from models import (
    CodeReviewAction,
    CodeReviewObservation,
    CodeSnippet,
    EpisodeState,
)
from tasks import TASKS, Task
from grader import grade_action, is_episode_done


class CodeReviewEnvironment:
    """
    OpenEnv-compliant environment for code review tasks.

    Supports three tasks of increasing difficulty:
      - find_bug      (easy)
      - security_audit (medium)
      - full_review   (hard)
    """

    def __init__(self, task_name: str = "find_bug"):
        if task_name not in TASKS:
            raise ValueError(
                f"Unknown task '{task_name}'. Choose from: {list(TASKS.keys())}"
            )
        self._task_name = task_name
        self._task: Task = TASKS[task_name]
        self._episode_id: str = ""
        self._step_count: int = 0
        self._cumulative_reward: float = 0.0
        self._done: bool = False
        self._attempts: list = []

    # ------------------------------------------------------------------ #
    # OpenEnv Interface                                                    #
    # ------------------------------------------------------------------ #

    def reset(self) -> CodeReviewObservation:
        """Start a new episode. Returns initial observation."""
        self._episode_id = str(uuid.uuid4())
        self._step_count = 0
        self._cumulative_reward = 0.0
        self._done = False
        self._attempts = []

        return CodeReviewObservation(
            task_name=self._task.name,
            task_description=self._task.description,
            snippet=CodeSnippet(
                language=self._task.language,
                filename=self._task.filename,
                code=self._task.code,
                context=self._task.context,
            ),
            step_count=0,
            last_feedback=None,
            score_so_far=0.0,
            done=False,
            message=(
                f"🔍 Code Review Task [{self._task.difficulty.upper()}]: "
                f"{self._task.name.replace('_', ' ').title()}. "
                f"You have up to {self._task.max_steps} attempts."
            ),
        )

    def step(
        self, action: CodeReviewAction
    ) -> Tuple[CodeReviewObservation, float, bool, Dict[str, Any]]:
        """
        Process a review action.
        Returns (observation, reward, done, info).
        """
        if self._done:
            obs = self._make_obs("Episode already finished. Call reset() to start a new one.", 0.0)
            return obs, 0.0, True, {"warning": "episode_already_done"}

        self._step_count += 1
        reward, feedback = grade_action(action, self._task)

        # Accumulate reward (strictly between 0 and 1)
        self._cumulative_reward = min(0.99, self._cumulative_reward + reward * (1.0 / self._task.max_steps))
        self._cumulative_reward = max(0.01, self._cumulative_reward)

        self._attempts.append({
            "step": self._step_count,
            "issues_submitted": len(action.issues),
            "approved": action.approved,
            "step_reward": round(reward, 4),
            "cumulative_reward": round(self._cumulative_reward, 4),
        })

        self._done = is_episode_done(
            self._step_count, self._cumulative_reward, self._task.max_steps
        )

        obs = self._make_obs(feedback, reward)
        info: Dict[str, Any] = {
            "step": self._step_count,
            "cumulative_reward": self._cumulative_reward,
            "episode_id": self._episode_id,
        }
        return obs, reward, self._done, info

    def state(self) -> EpisodeState:
        """Return current episode metadata."""
        return EpisodeState(
            episode_id=self._episode_id,
            task_name=self._task_name,
            step_count=self._step_count,
            max_steps=self._task.max_steps,
            score=round(self._cumulative_reward, 4),
            done=self._done,
            attempts=self._attempts,
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _make_obs(self, feedback: str, last_reward: float) -> CodeReviewObservation:
        return CodeReviewObservation(
            task_name=self._task.name,
            task_description=self._task.description,
            snippet=CodeSnippet(
                language=self._task.language,
                filename=self._task.filename,
                code=self._task.code,
                context=self._task.context,
            ),
            step_count=self._step_count,
            last_feedback=feedback,
            score_so_far=round(self._cumulative_reward, 4),
            done=self._done,
            message="Episode complete. Call reset() for a new episode." if self._done else "",
        )
