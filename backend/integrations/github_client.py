"""
GitHub API integration: fetch assigned issues, open PRs.
Wraps PyGitHub. Only used when github.enabled = true in config.
"""

import logging
from dataclasses import dataclass

from github import Github, GithubException

logger = logging.getLogger(__name__)


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    url: str
    labels: list[str]


class GitHubClient:
    def __init__(self, token: str, repo_name: str):
        self._gh = Github(token)
        self._repo = self._gh.get_repo(repo_name)

    def get_assigned_issues(
        self, assignee: str, required_label: str | None = None
    ) -> list[GitHubIssue]:
        """Return open issues assigned to the given GitHub username.

        If *required_label* is set, only issues that carry that label are returned.
        This lets you differentiate bot-assigned issues from human-assigned ones
        without needing a separate bot account.
        """
        issues = self._repo.get_issues(state="open", assignee=assignee)
        result = []
        for issue in issues:
            if issue.pull_request is not None:
                continue  # exclude PRs
            label_names = [label.name for label in issue.labels]
            if required_label and required_label not in label_names:
                logger.debug(
                    "Skipping issue #%d — missing required label '%s'",
                    issue.number, required_label,
                )
                continue
            result.append(GitHubIssue(
                number=issue.number,
                title=issue.title,
                body=issue.body or "",
                url=issue.html_url,
                labels=label_names,
            ))
        return result

    def open_pull_request(
        self,
        branch: str,
        title: str,
        body: str,
        base: str = "main",
    ) -> str:
        """Open a PR and return its URL."""
        try:
            pr = self._repo.create_pull(
                title=title,
                body=body,
                head=branch,
                base=base,
            )
            logger.info("Opened PR #%d: %s", pr.number, pr.html_url)
            return pr.html_url
        except GithubException as exc:
            logger.error("Failed to open PR: %s", exc)
            raise
