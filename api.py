from fastapi import FastAPI
from pydantic import BaseModel

from q2learn.ledger import Ledger
from q2learn.services import Q2Service, Q2Error
from q2learn.models import (
    Learner,
    Tutor,
    TutorStatus,
    EdxCourse,
    Cohort,
    Session,
    now
)
from q2learn.payments import PaymentProvider, PayoutProvider, PayResult


# ---- Mock providers ----

class MockPaymentProvider(PaymentProvider):
    def charge(self, learner_id: str, amount_cents: int) -> PayResult:
        return PayResult(success=True, ref="mock-payment")


class MockPayoutProvider(PayoutProvider):
    def pay(self, tutor_id: str, amount_cents: int) -> PayResult:
        return PayResult(success=True, ref="mock-payout")


# ---- Engine ----

ledger = Ledger()
q2 = Q2Service(
    ledger,
    MockPaymentProvider(),
    MockPayoutProvider()
)

learners = {}
tutors = {}
courses = {}
cohorts = {}
sessions = {}

# ---- API ----

app = FastAPI(
    title="Q2Learn API",
    version="1.0.0"
)


class CreateLearner(BaseModel):
    email: str
    display_name: str


class TopUpRequest(BaseModel):
    learner_id: str
    amount_cents: int


class CreateTutor(BaseModel):
    email: str
    display_name: str
    field_of_expertise: str


class CreateCohort(BaseModel):
    course_code: str
    course_title: str
    provider: str
    total_hours: int
    tutor_id: str
    title: str

class EnrollLearner(BaseModel):
    cohort_id: str
    learner_id: str
    course_hours: int

class DeliverSessionRequest(BaseModel):
    cohort_id: str
    tutor_id: str
    duration_hours: int

class VerifyTutorRequest(BaseModel):
    tutor_id: str

@app.get("/")
def root():
    return {"message": "Q2Learn API is running"}


@app.post("/learners")
def create_learner(body: CreateLearner):
    learner = Learner(
        email=body.email,
        display_name=body.display_name
    )

    learners[learner.id] = learner

    return {
        "id": learner.id,
        "email": learner.email,
        "display_name": learner.display_name
    }


@app.post("/learners/top-up")
def top_up(body: TopUpRequest):
    try:
        q2.top_up(body.learner_id, body.amount_cents)

        return {
            "ok": True,
            "credits": q2.credit_balance(body.learner_id)
        }

    except Q2Error as e:
        return {
            "ok": False,
            "error": str(e)
        }


@app.get("/learners/{learner_id}/credits")
def credits(learner_id: str):
    return {
        "credits": q2.credit_balance(learner_id)
    }

@app.post("/tutors")
def create_tutor(body: CreateTutor):

    tutor = Tutor(
        email=body.email,
        display_name=body.display_name,
        field_of_expertise=body.field_of_expertise
    )

    tutors[tutor.id] = tutor

    return {
        "id": tutor.id,
        "email": tutor.email,
        "display_name": tutor.display_name,
        "field_of_expertise": tutor.field_of_expertise,
        "status": tutor.status.value,
        "payout_verified": tutor.payout_verified
    }

@app.post("/cohorts")
def create_cohort(body: CreateCohort):

    course = EdxCourse(
        code=body.course_code,
        title=body.course_title,
        provider=body.provider,
        total_hours=body.total_hours
    )

    courses[course.id] = course

    cohort = Cohort(
        course_id=course.id,
        tutor_id=body.tutor_id,
        title=body.title
    )

    cohorts[cohort.id] = cohort

    return {
        "cohort_id": cohort.id,
        "course_id": course.id,
        "title": cohort.title,
        "capacity": cohort.capacity,
        "enrolled": len(cohort.learner_ids),
        "status": cohort.status.value
    }

@app.post("/cohorts/enroll")
def enroll_learner(body: EnrollLearner):

    cohort = cohorts[body.cohort_id]

    q2.enroll(
        cohort=cohort,
        learner_id=body.learner_id,
        course_hours=body.course_hours
    )

    return {
        "ok": True,
        "cohort_id": cohort.id,
        "enrolled": len(cohort.learner_ids),
        "seats_left": cohort.seats_left
    }

@app.post("/sessions/deliver")
def deliver_session(body: DeliverSessionRequest):

    cohort = cohorts[body.cohort_id]
    tutor = tutors[body.tutor_id]

    session = Session(
        cohort_id=cohort.id,
        scheduled_at=now(),
        duration_hours=body.duration_hours
    )

    sessions[session.id] = session

    q2.deliver_session(
        cohort=cohort,
        tutor=tutor,
        session=session
    )

    return {
        "session_id": session.id,
        "status": session.status.value
    }

@app.post("/tutors/verify")
def verify_tutor(body: VerifyTutorRequest):

    tutor = tutors[body.tutor_id]

    tutor.status = TutorStatus.VERIFIED
    tutor.payout_verified = True

    return {
        "id": tutor.id,
        "status": tutor.status.value,
        "payout_verified": tutor.payout_verified
    }

@app.get("/tutors/{tutor_id}/balance")
def tutor_balance(tutor_id: str):

    return {
        "accrued_balance": q2.tutor_accrued_balance(tutor_id)
    }
