import re
from typing import Dict, Match, Optional, Tuple

from timew_to_odoo.timew_to_odoo.timewarrior import TimeInterval

from timew_to_odoo.timew_to_odoo.convert import SimpleConverter


TASK_TAG_REGEX = re.compile(r"^task:(?P<task_id>\d+)$")

PROJECT_TAG = "Odoo-psbe"


def _has_any_tag(entry: TimeInterval, *tags: str) -> bool:
    return any(tag in entry.tags for tag in tags)


def special_tasks() -> Dict[str, str]:
    """Return the mapping of special-task kinds to their Timewarrior tags."""
    return {
        cls.kind: cls.tag
        for cls in sorted(
            OdooConverter.__subclasses__(), key=lambda cls: cls.__name__
        )
        if cls.kind and cls.tag
    }


class OdooConverter(SimpleConverter):
    kind: str = ""
    tag: str = ""

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and any(
            tag.startswith("Odoo") for tag in entry.tags
        )


class OdooOnboarding(OdooConverter):
    kind = "onboarding"
    tag = "Odoo-onboarding"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooTraining(OdooConverter):
    kind = "training"
    tag = "Odoo-training"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooOwndb(OdooConverter):
    kind = "owndb"
    tag = "Odoo-owndb"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooMisc(OdooConverter):
    kind = "misc"
    tag = "Odoo-misc"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooImprovement(OdooConverter):
    kind = "improvement"
    tag = "Odoo-improvement"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooCoaching(OdooConverter):
    kind = "coaching"
    tag = "Odoo-coaching"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooReview(OdooConverter):
    kind = "review"
    tag = "Odoo-review"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooMeeting(OdooConverter):
    kind = "meeting"
    tag = "Odoo-meeting"

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and self.tag in entry.tags


class OdooTask(OdooConverter):
    tags = (PROJECT_TAG, "Odoo-maintenance")

    def matches(self, entry: TimeInterval) -> bool:
        return super().matches(entry) and _has_any_tag(entry, *self.tags)


def extract_task(entry: TimeInterval) -> Tuple[int, str]:
    """Return the Odoo task id carried by the ``task:XXXXX`` tag and the
    interval description (its annotation).

    Raises ``ValueError`` if no ``task:`` tag holds a numeric id.
    """
    for tag in entry.tags:
        match: Optional[Match] = TASK_TAG_REGEX.match(tag)
        if match:
            return int(match.group("task_id")), entry.annotation
    raise ValueError(f"Couldn't extract task info from entry: {repr(entry)}")