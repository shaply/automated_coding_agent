"""
Planning phase: generate a structured implementation plan using the LLM,
then refine it based on user comments until approved.
"""

import logging
from pathlib import Path

from integrations.llm_client import LLMClient
from orchestrator.context_loader import build_context_summary

logger = logging.getLogger(__name__)

_PLANNING_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planning.txt"
_REFINEMENT_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "refinement.txt"


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class Planner:
    def __init__(self, llm: LLMClient, repo_path: str):
        self.llm = llm
        self.repo_path = repo_path

    def generate_plan(self, task: str) -> list[str]:
        """Generate a numbered implementation plan for the given task."""
        context = build_context_summary(self.repo_path)
        template = _load_prompt(_PLANNING_PROMPT_PATH)
        prompt = template.format(task=task, context=context)

        logger.info("Generating plan for task: %s", task[:80])
        response = self.llm.complete([{"role": "user", "content": prompt}])
        return self._parse_plan(response)

    def refine_plan(self, current_plan: list[str], comment: str) -> list[str]:
        """Refine an existing plan based on user feedback."""
        plan_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(current_plan))
        template = _load_prompt(_REFINEMENT_PROMPT_PATH)
        prompt = template.format(plan=plan_text, comment=comment)

        logger.info("Refining plan based on comment: %s", comment[:80])
        response = self.llm.complete([{"role": "user", "content": prompt}])
        return self._parse_plan(response)

    def _parse_plan(self, text: str) -> list[str]:
        """
        Parse numbered steps from LLM response.
        Accepts lines like '1. Do something' or '1) Do something'.
        Falls back to returning the full text as a single step if no numbered
        steps are found.
        """
        import re
        lines = text.strip().splitlines()
        steps = []
        for line in lines:
            m = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
            if m:
                steps.append(m.group(1).strip())
        if not steps:
            logger.warning("Could not parse numbered steps from plan response; using full text.")
            steps = [text.strip()]
        return steps
