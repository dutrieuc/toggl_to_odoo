import re
from typing import Tuple, Optional, Match

from toggl_to_odoo.timewarrior import TimeInterval

from toggl_to_odoo.convert import SimpleConverter


def _has_any_tag(entry: TimeInterval, *tags: str) -> bool:
    return any(tag in entry.tags for tag in tags)


class OdooConverter(SimpleConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and any(
            tag.startswith("Odoo") for tag in entry.tags
        )


class OdooOnboarding(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-onboarding" in entry.tags


class OdooTraining(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-training" in entry.tags


class OdooOwndb(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-owndb" in entry.tags


class OdooMisc(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-misc" in entry.tags


class OdooImprovement(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-improvement" in entry.tags


class OdooCoaching(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-coaching" in entry.tags


class OdooReview(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-review" in entry.tags


class OdooMeeting(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and "Odoo-meeting" in entry.tags


class OdooTask(OdooConverter):
    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and _has_any_tag(
            entry, "Odoo-psbe", "Odoo-maintenance"
        )


def extract_task(entry: TimeInterval) -> Tuple[int, Optional[str], str]:
    match: Match = re.search(
        r"^\[(?P<task_id>\d+)(?::\s*(?P<task_desc>.*?))?\]\s*(?P<description>.*)",
        entry.annotation,
    )
    if not match:
        raise ValueError(f"Couldn't extract task info from entry: {repr(entry)}")
    task_id: int = int(match.group("task_id"))
    task_desc: Optional[str] = match.group("task_desc") or None
    description: str = match.group("description")
    return task_id, task_desc, description
