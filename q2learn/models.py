"""
Q2Learn core domain models.

The product thesis, encoded in the model:
  * Learning is a SOCIAL act. The core unit is therefore not a lone lesson but a
    COHORT -- up to 10 learners moving through a real curriculum together, led by
    a PhD tutor. The cohort is the completion engine; people finish because they
    learn with others.
  * The curriculum is a real edX course (accredited, a topic the learner chose),
    so time spent converts into something that counts. The edX certificate is
    arranged directly between the learner and edX -- Q2Learn does not administer
    that flow.

Money model ("Starbucks salaries, cappuccino fees"):
  * Learner fee:  $10 / hour / learner
  * Tutor pay:    $30 / hour
  * Class size:   up to 10 learners
  * Breakeven at 3 learners; ~70% gross margin at a full class of 10.

Money is always integer minor units (cents). Never float.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> datetime:
    return datetime.now(timezone.utc)


# Economics (cents)
LEARNER_FEE_PER_HOUR_CENTS = 10_00      # $10 / learner / hour
TUTOR_PAY_PER_HOUR_CENTS = 30_00        # $30 / hour
MAX_CLASS_SIZE = 10


# --------------------------------------------------------------------------- #
# People                                                                      #
# --------------------------------------------------------------------------- #
class TutorStatus(enum.Enum):
    PENDING = "pending"          # applied, not yet verified
    VERIFIED = "verified"        # credentials checked; can teach + be paid
    SUSPENDED = "suspended"


@dataclass
class Learner:
    email: str
    display_name: str
    id: str = field(default_factory=lambda: _id("lnr"))
    created_at: datetime = field(default_factory=now)


@dataclass
class Tutor:
    """A PhD-level expert who leads cohorts and earns a 'Starbucks salary'."""
    email: str
    display_name: str
    field_of_expertise: str
    id: str = field(default_factory=lambda: _id("tut"))
    status: TutorStatus = TutorStatus.PENDING
    # Tutors receive money, so they require KYC/payout verification before payout
    payout_verified: bool = False
    created_at: datetime = field(default_factory=now)

    def can_teach(self) -> bool:
        return self.status == TutorStatus.VERIFIED

    def can_be_paid(self) -> bool:
        return self.status == TutorStatus.VERIFIED and self.payout_verified


# --------------------------------------------------------------------------- #
# Curriculum + cohort                                                         #
# --------------------------------------------------------------------------- #
@dataclass
class EdxCourse:
    """A real edX course used as the cohort curriculum."""
    code: str                      # e.g. "edX:HarvardX/CS50"
    title: str
    provider: str                  # e.g. "HarvardX"
    total_hours: int               # planned live class hours for the cohort
    id: str = field(default_factory=lambda: _id("crs"))


class CohortStatus(enum.Enum):
    OPEN = "open"                  # enrolling
    RUNNING = "running"            # in progress
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Cohort:
    """
    The core unit: up to MAX_CLASS_SIZE learners moving through an edX course
    together, led by one PhD tutor over the course's planned hours.
    """
    course_id: str
    tutor_id: str
    title: str
    id: str = field(default_factory=lambda: _id("coh"))
    status: CohortStatus = CohortStatus.OPEN
    capacity: int = MAX_CLASS_SIZE
    learner_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=now)

    @property
    def enrolled(self) -> int:
        return len(self.learner_ids)

    @property
    def seats_left(self) -> int:
        return self.capacity - self.enrolled

    @property
    def is_viable(self) -> bool:
        """3+ learners covers the tutor's hourly pay (breakeven)."""
        return self.enrolled >= 3


class SessionStatus(enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"


@dataclass
class Session:
    """One live class hour within a cohort -- the social/learning event."""
    cohort_id: str
    scheduled_at: datetime
    duration_hours: int = 1
    id: str = field(default_factory=lambda: _id("ses"))
    status: SessionStatus = SessionStatus.SCHEDULED
    attended_learner_ids: list[str] = field(default_factory=list)
