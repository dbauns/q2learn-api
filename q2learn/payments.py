"""
Q2Learn payments.

Money in (from learners) and money out (to tutors) go through external,
regulated providers -- a PSP for collecting learner payments and a payout
provider for paying tutors (often cross-border, since the PhDs are worldwide).
This module defines those interfaces; real adapters plug in later.

Boundary (same as the rest of the engine): this makes the platform
payout-ready, not payout-compliant. Cross-border payouts to individuals carry
KYC / tax / money-transmission obligations that require the real providers and
counsel. Tutors must be payout_verified before any payout is permitted.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class PayResult:
    success: bool
    ref: str
    reason: str = ""


class PaymentProvider(abc.ABC):
    """Collects learner payments into platform custody."""
    @abc.abstractmethod
    def charge(self, learner_id: str, amount_cents: int) -> PayResult: ...


class PayoutProvider(abc.ABC):
    """Pays tutor earnings out to their verified account (often cross-border)."""
    @abc.abstractmethod
    def pay(self, tutor_id: str, amount_cents: int) -> PayResult: ...
