from fastapi import FastAPI
from pydantic import BaseModel

from q2learn.ledger import Ledger
from q2learn.services import Q2Service, Q2Error
from q2learn.models import Learner, Tutor, EdxCourse, Cohort
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
