"""
Q2Learn ledger.

A double-entry ledger tracks all money: learner credit balances, platform
revenue, and tutor earnings (accrued and paid). Every movement is a balanced
journal entry, so the books always balance and there is a complete audit trail
(important both for sound engineering and for paying people across borders).

Accounts (namespaced):
  * learner:<id>           -- a learner's prepaid credit balance
  * platform:revenue       -- the platform's margin (the spread)
  * platform:settlement    -- external cash clearing (payment rail)
  * tutor_accrued:<id>     -- a tutor's earned-but-unpaid balance
  * tutor_paid:<id>        -- cumulative paid out to a tutor (audit)

Single asset: CASH, in integer minor units (cents).
"""

from __future__ import annotations

import enum
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> datetime:
    return datetime.now(timezone.utc)


CASH = "CASH"

SETTLEMENT = "platform:settlement"
REVENUE = "platform:revenue"


def learner_acct(lid: str) -> str: return f"learner:{lid}"
def tutor_accrued(tid: str) -> str: return f"tutor_accrued:{tid}"
def tutor_paid(tid: str) -> str: return f"tutor_paid:{tid}"


class EntryType(enum.Enum):
    TOP_UP = "top_up"               # learner buys credits
    ENROLLMENT = "enrollment"       # learner pays into a cohort (prepaid)
    SESSION_CHARGE = "session_charge"   # pay-as-you-go session fee
    TUTOR_ACCRUAL = "tutor_accrual"     # tutor earns for a delivered session
    TUTOR_PAYOUT = "tutor_payout"       # tutor paid out
    REFUND = "refund"


@dataclass(frozen=True)
class Posting:
    account: str
    amount: int                     # signed; +credit, -debit


@dataclass
class JournalEntry:
    type: EntryType
    postings: tuple[Posting, ...]
    memo: str = ""
    id: str = field(default_factory=lambda: _id("je"))
    created_at: datetime = field(default_factory=now)

    def validate(self) -> None:
        total = sum(p.amount for p in self.postings)
        if total != 0:
            raise ValueError(f"unbalanced entry: nets to {total}, must be 0")


class Ledger:
    def __init__(self) -> None:
        self._entries: list[JournalEntry] = []
        self._bal: dict[str, int] = defaultdict(int)

    def post(self, entry: JournalEntry) -> JournalEntry:
        entry.validate()
        for p in entry.postings:
            self._bal[p.account] += p.amount
        self._entries.append(entry)
        return entry

    def balance(self, account: str) -> int:
        return self._bal[account]

    def entries(self) -> list[JournalEntry]:
        return list(self._entries)

    def assert_balanced(self) -> None:
        total = sum(self._bal.values())
        assert total == 0, f"ledger imbalance: {total}"
