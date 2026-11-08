from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from ..core.envelope import Envelope, ok
from ..deps import CurrentUser, Page
from ..schemas.claims import ClaimCreate, ClaimListItem, ClaimOut, ClaimReviewIn, EvidenceIn
from ..schemas.matches import MatchOut, VerificationQuestion
from ..services import presenters as P, svc

router = APIRouter()


# ---- matches ----
@router.get("/matches/mine", response_model=Envelope[list[MatchOut]], tags=["matches"],
            summary="Candidate matches for all of the user's lost reports")
def my_matches(user: CurrentUser, page: Page):
    items, nxt = page.apply(svc.my_matches(user))
    return ok([P.match(user, m) for m in items], nxt)


@router.get("/matches/{match_id}", response_model=Envelope[MatchOut], tags=["matches"])
def get_match(match_id: UUID, user: CurrentUser):
    return ok(P.match(user, svc.get_match(user, match_id)))


@router.post("/matches/{match_id}/dismiss", response_model=Envelope[MatchOut], tags=["matches"],
             summary="'Not my item'")
def dismiss(match_id: UUID, user: CurrentUser):
    return ok(P.match(user, svc.dismiss_match(user, match_id)))


@router.get("/matches/{match_id}/verification-questions", response_model=Envelope[list[VerificationQuestion]],
            tags=["claims"], summary="Private questions to show on the claim form")
def questions(match_id: UUID, user: CurrentUser):
    return ok([VerificationQuestion(id=i, prompt=p) for i, p in svc.verification_questions(user, match_id)])


# ---- claims ----
@router.post("/matches/{match_id}/claims", response_model=Envelope[ClaimOut], status_code=201, tags=["claims"])
def create_claim(match_id: UUID, body: ClaimCreate, user: CurrentUser):
    c = svc.create_claim(user, match_id, body)
    return ok(P.claim(user, c, "claimant"))


@router.get("/claims/mine", response_model=Envelope[list[ClaimListItem]], tags=["claims"])
def my_claims(user: CurrentUser, page: Page):
    items, nxt = page.apply(svc.my_claims(user))
    return ok([P.claim_item(user, c) for c in items], nxt)


@router.get("/claims/{claim_id}", response_model=Envelope[ClaimOut], tags=["claims"])
def get_claim(claim_id: UUID, user: CurrentUser):
    c, role = svc.get_claim(user, claim_id)
    return ok(P.claim(user, c, role))


@router.post("/claims/{claim_id}/evidence", response_model=Envelope[ClaimOut], tags=["claims"])
def add_evidence(claim_id: UUID, body: EvidenceIn, user: CurrentUser):
    c = svc.add_evidence(user, claim_id, body)
    return ok(P.claim(user, c, "claimant"))


@router.post("/claims/{claim_id}/review", response_model=Envelope[ClaimOut], tags=["claims"],
             summary="Approve / reject / escalate (reviewers only, reason required)")
def review(claim_id: UUID, body: ClaimReviewIn, user: CurrentUser):
    c = svc.review_claim(user, claim_id, body.decision, body.reason)
    return ok(P.claim(user, c, "reviewer"))
