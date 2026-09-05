"""PlanRepository: bridge between legacy file plans and per-interview DB plans.

Legacy LiveKit agent continues to use FilePlanRepository / plan_loader by default.
DatabasePlanRepository is available for the SaaS API and future engine binding.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from config import QUESTION_PLAN_PATH, ROOT_DIR
from core.enums import QuestionPlanStatus
from models.interview import Interview
from repositories.question_plans import QuestionPlanRepository


class PlanRepository(ABC):
    @abstractmethod
    def get_plan_for_interview(self, interview_id: uuid.UUID | str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def save_plan_for_interview(
        self, interview_id: uuid.UUID | str, plan: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError


class FilePlanRepository(PlanRepository):
    """Compatibility wrapper around the global `output/question_plan.json` workflow."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or QUESTION_PLAN_PATH

    def get_plan_for_interview(self, interview_id: uuid.UUID | str) -> dict[str, Any] | None:
        # File backend is global; interview_id is accepted for interface parity only.
        _ = interview_id
        if not self.path.is_file():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def save_plan_for_interview(
        self, interview_id: uuid.UUID | str, plan: dict[str, Any]
    ) -> dict[str, Any]:
        _ = interview_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(plan)
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return payload


class DatabasePlanRepository(PlanRepository):
    """Persist/retrieve plans via QuestionPlan + Question tables."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._plans = QuestionPlanRepository(db)

    def get_plan_for_interview(self, interview_id: uuid.UUID | str) -> dict[str, Any] | None:
        iid = uuid.UUID(str(interview_id))
        plan = self._plans.get_latest_for_interview(iid)
        if plan is None:
            return None
        return self._plans.to_engine_dict(plan)

    def save_plan_for_interview(
        self, interview_id: uuid.UUID | str, plan: dict[str, Any]
    ) -> dict[str, Any]:
        iid = uuid.UUID(str(interview_id))
        interview = self.db.get(Interview, iid)
        if interview is None:
            raise ValueError(f"Interview not found: {iid}")
        status = QuestionPlanStatus.generated
        if plan.get("approved_by_human") or plan.get("approval_status") == "approved":
            status = QuestionPlanStatus.approved
        saved = self._plans.save_plan_dict(interview, plan, status=status, source="database")
        return self._plans.to_engine_dict(saved)


def default_file_plan_repository() -> FilePlanRepository:
    return FilePlanRepository(ROOT_DIR / "output" / "question_plan.json")
