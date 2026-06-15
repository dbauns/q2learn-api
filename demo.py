"""
Q2Learn engine -- end-to-end demo + assertions.
Run:  python3 demo.py
"""

from q2learn.ledger import (Ledger, REVENUE, SETTLEMENT, learner_acct,
                            tutor_accrued, tutor_paid)
from q2learn.models import (Cohort, EdxCourse, Learner, Tutor, TutorStatus,
                            Session, LEARNER_FEE_PER_HOUR_CENTS,
                            TUTOR_PAY_PER_HOUR_CENTS, MAX_CLASS_SIZE)
from q2learn.payments import PaymentProvider, PayoutProvider, PayResult
from q2learn.services import Q2Service, Q2Error
from datetime import datetime, timezone


class MockPSP(PaymentProvider):
    def __init__(self, ledger): self.l = ledger
    def charge(self, learner_id, amount_cents):
        from q2learn.ledger import JournalEntry, Posting, EntryType
        # external funds arrive into settlement custody
        self.l.post(JournalEntry(EntryType.TOP_UP,
            (Posting("external:learners", -amount_cents),
             Posting(SETTLEMENT, +amount_cents)), memo="PSP inflow"))
        return PayResult(True, "psp-1")


class MockPayout(PayoutProvider):
    def pay(self, tutor_id, amount_cents):
        return PayResult(True, "payout-1")


def main():
    ledger = Ledger()
    q2 = Q2Service(ledger, MockPSP(ledger), MockPayout())

    print("=== Q2Learn engine: end-to-end ===\n")
    print(f"Economics: ${LEARNER_FEE_PER_HOUR_CENTS/100:.0f}/learner/hr in, "
          f"${TUTOR_PAY_PER_HOUR_CENTS/100:.0f}/hr to tutor, "
          f"max {MAX_CLASS_SIZE} learners/class\n")

    # -- curriculum + tutor + cohort ------------------------------------- #
    course = EdxCourse(code="HarvardX/PH125", title="Data Science",
                       provider="HarvardX", total_hours=16)
    tutor = Tutor(email="dr.sato@x.com", display_name="Dr. Sato",
                  field_of_expertise="Statistics",
                  status=TutorStatus.VERIFIED, payout_verified=True)
    cohort = Cohort(course_id=course.id, tutor_id=tutor.id,
                    title="Data Science — Spring cohort")
    print(f"Course (edX): {course.title} / {course.provider} ({course.total_hours}h)")
    print(f"Tutor: {tutor.display_name}, PhD {tutor.field_of_expertise}")
    print(f"Cohort: '{cohort.title}' (capacity {cohort.capacity})\n")

    # -- enroll a full class of 10 --------------------------------------- #
    learners = [Learner(email=f"l{i}@x.com", display_name=f"Learner {i+1}")
                for i in range(MAX_CLASS_SIZE)]
    course_cost = LEARNER_FEE_PER_HOUR_CENTS * course.total_hours   # $160
    for ln in learners:
        q2.top_up(ln.id, course_cost)              # each tops up exactly the course cost
        q2.enroll(cohort, ln.id, course.total_hours)
    print(f"Enrolled {cohort.enrolled} learners "
          f"(each prepaid {course.total_hours}h x ${LEARNER_FEE_PER_HOUR_CENTS/100:.0f} "
          f"= ${course_cost/100:.0f})")
    print(f"Cohort viable (>=3): {cohort.is_viable}\n")
    ledger.assert_balanced()

    # -- deliver all 16 sessions (full attendance) ----------------------- #
    for h in range(course.total_hours):
        s = Session(cohort_id=cohort.id, scheduled_at=datetime.now(timezone.utc))
        s.attended_learner_ids = list(cohort.learner_ids)   # all 10 attend
        q2.deliver_session(cohort, tutor, s)
    ledger.assert_balanced()

    accrued = q2.tutor_accrued_balance(tutor.id)
    revenue = q2.platform_revenue()
    print(f"After {course.total_hours} delivered sessions (10 learners each):")
    print(f"  Tutor accrued:    ${accrued/100:,.2f}  "
          f"(= {course.total_hours}h x ${TUTOR_PAY_PER_HOUR_CENTS/100:.0f})")
    print(f"  Platform revenue: ${revenue/100:,.2f}  "
          f"(spread: 10 learners pay $100/hr, tutor $30/hr -> $70/hr x {course.total_hours}h)")
    margin = revenue / (revenue + accrued) * 100
    print(f"  Gross margin:     {margin:.0f}%\n")

    # -- pay the tutor out ----------------------------------------------- #
    q2.payout_tutor(tutor)
    print(f"Tutor paid out: ${ledger.balance(tutor_paid(tutor.id))/100:,.2f}")
    print(f"Tutor accrued now: ${q2.tutor_accrued_balance(tutor.id)/100:,.2f}")
    ledger.assert_balanced()

    print("\n=== Ledger audit ===")
    ledger.assert_balanced()
    print(f"Journal entries: {len(ledger.entries())}")
    print("Global double-entry invariant: BALANCED")


# --------------------------------------------------------------------------- #
# Assertions                                                                  #
# --------------------------------------------------------------------------- #
def _svc():
    l = Ledger(); return l, Q2Service(l, MockPSP(l), MockPayout())


def test_full_class_economics():
    l, q2 = _svc()
    course = EdxCourse("c", "T", "HarvardX", 1)
    tutor = Tutor("t@x.com", "Dr", "Stats", status=TutorStatus.VERIFIED, payout_verified=True)
    cohort = Cohort(course.id, tutor.id, "c")
    for i in range(10):
        ln = Learner(f"{i}@x.com", f"L{i}")
        q2.top_up(ln.id, 10_00); q2.enroll(cohort, ln.id, 1)
    s = Session(cohort.id, datetime.now(timezone.utc)); s.attended_learner_ids = list(cohort.learner_ids)
    q2.deliver_session(cohort, tutor, s)
    assert q2.tutor_accrued_balance(tutor.id) == 30_00          # tutor $30
    assert q2.platform_revenue() == 70_00                       # spread $70
    l.assert_balanced()
    print("ok: full class -> tutor $30, platform $70 (70% margin)")


def test_breakeven_at_three():
    l, q2 = _svc()
    course = EdxCourse("c", "T", "HarvardX", 1)
    tutor = Tutor("t@x.com", "Dr", "Stats", status=TutorStatus.VERIFIED, payout_verified=True)
    cohort = Cohort(course.id, tutor.id, "c")
    for i in range(3):
        ln = Learner(f"{i}@x.com", f"L{i}")
        q2.top_up(ln.id, 10_00); q2.enroll(cohort, ln.id, 1)
    s = Session(cohort.id, datetime.now(timezone.utc)); s.attended_learner_ids = list(cohort.learner_ids)
    q2.deliver_session(cohort, tutor, s)
    assert q2.tutor_accrued_balance(tutor.id) == 30_00
    assert q2.platform_revenue() == 0                           # breakeven
    l.assert_balanced()
    print("ok: 3 learners -> breakeven (platform $0, tutor fully covered)")


def test_capacity_enforced():
    l, q2 = _svc()
    course = EdxCourse("c", "T", "HarvardX", 1)
    tutor = Tutor("t@x.com", "Dr", "Stats", status=TutorStatus.VERIFIED)
    cohort = Cohort(course.id, tutor.id, "c")
    for i in range(10):
        ln = Learner(f"{i}@x.com", f"L{i}")
        q2.top_up(ln.id, 10_00); q2.enroll(cohort, ln.id, 1)
    extra = Learner("x@x.com", "X"); q2.top_up(extra.id, 10_00)
    try:
        q2.enroll(cohort, extra.id, 1); assert False
    except Q2Error as e:
        assert "full" in str(e)
    print("ok: class capped at 10 learners")


def test_insufficient_credits():
    l, q2 = _svc()
    course = EdxCourse("c", "T", "HarvardX", 16)
    tutor = Tutor("t@x.com", "Dr", "Stats", status=TutorStatus.VERIFIED)
    cohort = Cohort(course.id, tutor.id, "c")
    ln = Learner("a@x.com", "A"); q2.top_up(ln.id, 50_00)   # only $50, need $160
    try:
        q2.enroll(cohort, ln.id, 16); assert False
    except Q2Error as e:
        assert "insufficient" in str(e)
    print("ok: enrollment blocked without enough prepaid credits")


def test_payout_requires_verification():
    l, q2 = _svc()
    tutor = Tutor("t@x.com", "Dr", "Stats", status=TutorStatus.VERIFIED, payout_verified=False)
    # give the tutor an accrued balance directly for the test
    from q2learn.ledger import JournalEntry, Posting, EntryType
    l.post(JournalEntry(EntryType.TUTOR_ACCRUAL,
        (Posting(tutor_accrued(tutor.id), +30_00), Posting(REVENUE, -30_00))))
    try:
        q2.payout_tutor(tutor); assert False
    except Q2Error as e:
        assert "payout-verified" in str(e)
    print("ok: unverified tutor cannot be paid out")


def test_payout_balances():
    l, q2 = _svc()
    course = EdxCourse("c", "T", "HarvardX", 1)
    tutor = Tutor("t@x.com", "Dr", "Stats", status=TutorStatus.VERIFIED, payout_verified=True)
    cohort = Cohort(course.id, tutor.id, "c")
    for i in range(5):
        ln = Learner(f"{i}@x.com", f"L{i}")
        q2.top_up(ln.id, 10_00); q2.enroll(cohort, ln.id, 1)
    s = Session(cohort.id, datetime.now(timezone.utc)); s.attended_learner_ids = list(cohort.learner_ids)
    q2.deliver_session(cohort, tutor, s)
    assert q2.tutor_accrued_balance(tutor.id) == 30_00
    q2.payout_tutor(tutor)
    assert q2.tutor_accrued_balance(tutor.id) == 0
    assert l.balance(tutor_paid(tutor.id)) == 30_00
    l.assert_balanced()
    print("ok: payout clears accrued balance, ledger balanced")


if __name__ == "__main__":
    main()
    print("\n=== tests ===")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("\nAll tests passed")
