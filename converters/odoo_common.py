import re
from typing import Match, Optional, Tuple

from timew_to_odoo.timew_to_odoo.timewarrior import TimeInterval

from timew_to_odoo.timew_to_odoo.convert import SimpleConverter


TASK_TAG_REGEX = re.compile(r"^task:(?P<task_id>\d+)$")


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
