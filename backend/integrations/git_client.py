"""
Local git operations + safety checks.

Safety protocol before every task:
  1. Check for uncommitted changes → HALT if dirty
  2. Check for unresolved merge conflicts → HALT if any
  3. Pull latest from remote → HALT if pull fails
  4. Create feature branch from clean HEAD → proceed
"""

import logging
import tempfile
from pathlib import Path

from git import Repo, GitCommandError, InvalidGitRepositoryError

logger = logging.getLogger(__name__)


class GitSafetyError(Exception):
    """Raised when a safety check fails and the agent must halt."""


class GitClient:
    def __init__(self, remote_url: str, base_branch: str = "main"):
        self.remote_url = remote_url
        self.base_branch = base_branch

    def safety_check(self, repo: Repo) -> None:
        """
        Run all pre-task safety checks. Raises GitSafetyError on any failure.
        The agent must halt and surface the error to the user.
        """
        # 1. Uncommitted changes
        if repo.is_dirty(untracked_files=True):
            raise GitSafetyError(
                "Repo has uncommitted changes or untracked files — "
                "commit, stash, or clean them before AutoDev can proceed."
            )

        # 2. Merge conflicts (unresolved)
        conflicted = [
            item.a_path for item in repo.index.diff(None)
            if item.change_type == "U"
        ]
        if conflicted:
            raise GitSafetyError(
                f"Unresolved merge conflicts in: {', '.join(conflicted)} — "
                "resolve them manually before AutoDev can proceed."
            )

        # 3. Pull latest
        try:
            origin = repo.remotes["origin"]
            origin.pull(self.base_branch)
        except (GitCommandError, IndexError) as exc:
            raise GitSafetyError(
                f"Failed to pull latest from origin/{self.base_branch}: {exc}"
            )

    def clone_ephemeral(self, task_id: str) -> tuple[Repo, Path]:
        """
        Clone the target repo into an ephemeral temp directory.
        Returns (Repo, path). Caller is responsible for cleanup (or use reset()).
        """
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"autodev-task-{task_id}-"))
        logger.info("Cloning %s into %s", self.remote_url, tmp_dir)
        repo = Repo.clone_from(self.remote_url, str(tmp_dir))
        return repo, tmp_dir

    def create_feature_branch(self, repo: Repo, branch_name: str) -> None:
        """Create and checkout a new feature branch from the current HEAD."""
        branch = repo.create_head(branch_name)
        branch.checkout()
        logger.info("Checked out feature branch: %s", branch_name)

    def push_branch(self, repo: Repo, branch_name: str) -> None:
        """Push the feature branch to origin."""
        origin = repo.remotes["origin"]
        origin.push(refspec=f"{branch_name}:{branch_name}")
        logger.info("Pushed branch %s to origin", branch_name)
