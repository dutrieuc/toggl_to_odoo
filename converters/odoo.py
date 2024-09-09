from toggl.api import TimeEntry

from toggl_to_odoo.convert import ChainedConverter, SimpleConverter, TimesheetLine
from .odoo_common import (
    OdooConverter,
    OdooOnboarding,
    OdooTraining,
    OdooOwndb,
    OdooMisc,
    OdooImprovement,
    OdooCoaching,
    OdooReview,
    OdooMeeting,
    OdooTask,
    extract_task,
)
from typing import (
    TypedDict,
    Union,
    MutableMapping,
    TypeVar,
    Type,
    Callable,
    Optional,
    Tuple,
    MutableSequence,
    List,
    Sequence,
    Set,
    ClassVar,
    Iterator,
    Generic,
)
from math import ceil


class CustomChainedConverter(ChainedConverter):

    @staticmethod
    def rounded_amount(line: TimesheetLine) -> int:
        return ceil( line.get('unit_amount')*4 - 0.25)/4

    @staticmethod
    def merge(
        lines: List[TimesheetLine], keys: Optional[Sequence[str]] = None
    ) -> List[TimesheetLine]:
        buckets = ChainedConverter.merge(lines, keys)
        for line in buckets:
            line["unit_amount"] = CustomChainedConverter.rounded_amount(line)
        return buckets


converter2odoo = CustomChainedConverter("toggl2odoo")


class SimpleConverter2Odoo(SimpleConverter):
    def matches(self, entry: TimeEntry) -> bool:
        return super().matches(entry)

    def convert(self, entry: TimeEntry) -> TimesheetLine:
        return super().convert(entry)


class OdooConverter2Odoo(SimpleConverter2Odoo, OdooConverter):
    ...


@converter2odoo.register(110)
class OdooOnboarding2Odoo(OdooOnboarding, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        line.update(
            project="(PS) INT. TRAINING",
            task="(PS) INT. TRAINING",
            name=f"[functional][onboarding] - {entry.description}",
        )
        return line


@converter2odoo.register(120)
class OdooTraining2Odoo(OdooTraining, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        line.update(
            project=12335,  # "(BS) SELF TRAINING"
            task=3901684, # "(BS) TRAINING",
            name=f"[technical] {entry.description}",
        )
        return line


@converter2odoo.register(180)
class OdooOwndb2Odoo(OdooOwndb, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        line.update(
            project="(PS) INT. TRAINING",
            task="(PS) INT. TRAINING",
            name=f"[technical+functional] owndb: {entry.description}",
        )
        return line


@converter2odoo.register(210)
class OdooMisc2Odoo(OdooMisc, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        line.update(
            project="(BS) MISC",
            task=3820301,
        )
        return line


@converter2odoo.register(410)
class OdooImprovement2Odoo(OdooImprovement, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        task_id: int
        description: str
        task_id, _, description = extract_task(entry)
        line.update(project="(BS) IMPROVEMENT", task=task_id, name=description)
        return line


@converter2odoo.register(510)
class OdooCoaching2Odoo(OdooCoaching, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        line.update(
            project="(BS) COACHING",
            task="(BS) HELPING COLLEAGUES",
        )
        return line


@converter2odoo.register(610)
class OdooReview2Odoo(OdooReview, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        line.update(
            project=853,
            task="Code Review/PR Review",
        )
        return line


@converter2odoo.register(710)
class OdooMeeting2Odoo(OdooMeeting, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        line.update(
            project="(BS) MEETING",
            task=3820297,
        )
        return line


@converter2odoo.register(810)
class OdooTask2Odoo(OdooTask, OdooConverter2Odoo):
    def convert(self, entry: TimeEntry) -> TimesheetLine:
        line: TimesheetLine = super().convert(entry)
        task_id: int
        description: str
        task_id, _, description = extract_task(entry)
        line.pop("project", None)
        line.update(task=task_id, name=description)
        return line

