"""
Q2Learn services -- the platform logic.

Flows:
  * top_up:      learner buys credits (money in via PSP -> learner credit)
  * enroll:      learner joins a cohort, prepaying the full course
                 (total_hours x $10) from credits  [default model]
  * pay_as_you_go: alternatively, charge per attended session  [optional model]
  * deliver_session: when a class hour is delivered, accrue the tutor's $30 and
                 recognise the platform spread as revenue
  * payout:      pay a verified tutor their accrued balance out via the provider

The spread is the platform's margin: learners pay $10/hr each (up to 10 => up to
$100/hr); the tutor is paid a flat $30/hr; the difference is platform revenue.
"""

from __future__ import annotations

from .ledger import (CASH, EntryType, JournalEntry, Ledger, Posting, REVENUE,
                     SETTLEMENT, learner_acct, tutor_accrued, tutor_paid)
from .models import (Cohort, CohortStatus, LEARNER_FEE_PER_HOUR_CENTS,
                     MAX_CLASS_SIZE, Session, SessionStatus,
                     TUTOR_PAY_PER_HOUR_CENTS, Tutor)
from .payments import PaymentProvider, PayoutProvider


class Q2Error(Exception):
    pass


class Q2Service:
    def __init__(self, ledger: Ledger, psp: PaymentProvider, payouts: PayoutProvider):
        self._l = ledger
        self._psp = psp
        self._payouts = payouts

    # -- learner money in ------------------------------------------------- #
    def top_up(self, learner_id: str, amount_cents: int) -> JournalEntry:
        if amount_cents <= 0:
            raise Q2Error("top-up must be positive")
        res = self._psp.charge(learner_id, amount_cents)
        if not res.success:
            raise Q2Error(f"payment failed: {res.reason}")
        return self._l.post(JournalEntry(
            type=EntryType.TOP_UP,
            postings=(
                Posting(SETTLEMENT, -amount_cents),
                Posting(learner_acct(learner_id), +amount_cents),
            ),
            memo=f"top-up ref={res.ref}",
        ))

    def credit_balance(self, learner_id: str) -> int:
        return self._l.balance(learner_acct(learner_id))

    # -- enrollment (prepaid, default) ------------------------------------ #
    def enroll(self, cohort: Cohort, learner_id: str, course_hours: int) -> JournalEntry:
        if cohort.status != CohortStatus.OPEN:
            raise Q2Error("cohort not open for enrollment")
        if cohort.seats_left <= 0:
            raise Q2Error("cohort full")
        if learner_id in cohort.learner_ids:
            raise Q2Error("already enrolled")

cost = LEARNER_FEE_PER_HOUR_CENTS * course_hours

balance = self.credit_balance(learner_id)

print(
    f"learner={learner_id} "
    f"balance={balance} "
    f"cost={cost}"
)

if balance < cost:
    raise Q2Error("insufficient credits to enroll")

entry = self._l.post(
    JournalEntry(
        type=EntryType.ENROLLMENT,
        postings=(
            Posting(learner_acct(learner_id), -cost),
            Posting(SETTLEMENT, +cost),
        ),
        memo=f"enroll cohort={cohort.id} {course_hours}h @ "
             f"${LEARNER_FEE_PER_HOUR_CENTS/100}/h = ${cost/100}",
    )
)
        cohort.learner_ids.append(learner_id)
        return entry

    # -- session delivery: accrue tutor + recognise platform spread ------- #
    def deliver_session(self, cohort: Cohort, tutor: Tutor, session: Session) -> JournalEntry:
        if session.status == SessionStatus.COMPLETED:
            raise Q2Error("session already delivered")
        if not tutor.can_teach():
            raise Q2Error("tutor not verified to teach")

        attendees = len(session.attended_learner_ids) or cohort.enrolled
        hours = session.duration_hours

        learner_fees = LEARNER_FEE_PER_HOUR_CENTS * attendees * hours
        tutor_pay = TUTOR_PAY_PER_HOUR_CENTS * hours
        spread = learner_fees - tutor_pay     # platform margin (can be negative if <3 attend)

        # Move the delivered value out of settlement: tutor accrual + platform revenue.
        postings = [
            Posting(SETTLEMENT, -learner_fees),
            Posting(tutor_accrued(tutor.id), +tutor_pay),
            Posting(REVENUE, +spread),
        ]
        entry = self._l.post(JournalEntry(
            type=EntryType.TUTOR_ACCRUAL,
            postings=tuple(postings),
            memo=f"session {session.id}: {attendees} learners x {hours}h "
                 f"-> fees ${learner_fees/100}, tutor ${tutor_pay/100}, "
                 f"spread ${spread/100}",
        ))
        session.status = SessionStatus.COMPLETED
        return entry

    def tutor_accrued_balance(self, tutor_id: str) -> int:
        return self._l.balance(tutor_accrued(tutor_id))

    def platform_revenue(self) -> int:
        return self._l.balance(REVENUE)

    # -- payout to tutor -------------------------------------------------- #
    def payout_tutor(self, tutor: Tutor, amount_cents: int | None = None) -> JournalEntry:
        if not tutor.can_be_paid():
            raise Q2Error("tutor not payout-verified")
        accrued = self.tutor_accrued_balance(tutor.id)
        amount = accrued if amount_cents is None else amount_cents
        if amount <= 0:
            raise Q2Error("nothing to pay out")
        if amount > accrued:
            raise Q2Error("payout exceeds accrued balance")

        res = self._payouts.pay(tutor.id, amount)
        if not res.success:
            raise Q2Error(f"payout failed: {res.reason}")

        return self._l.post(JournalEntry(
            type=EntryType.TUTOR_PAYOUT,
            postings=(
                Posting(tutor_accrued(tutor.id), -amount),
                Posting(tutor_paid(tutor.id), +amount),   # audit: cumulative paid
                # cash leaves platform custody to the tutor's external account
                Posting(SETTLEMENT, -amount),
                Posting("external:tutors", +amount),
            ),
            memo=f"payout tutor={tutor.id} ${amount/100} ref={res.ref}",
        ))
