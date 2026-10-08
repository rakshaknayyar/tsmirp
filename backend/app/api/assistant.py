"""POST /assistant/query - the tourist assistant (any logged-in user).

Answers come from the fixed knowledge base in app/services/assistant_kb.py. The question is not
stored or logged, because it may contain personal details.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.assistant import AssistantQuery, AssistantReply
from app.services.assistant import answer_question

router = APIRouter(tags=["assistant"])


@router.post("/assistant/query", response_model=AssistantReply)
def query(body: AssistantQuery, user: CurrentUser) -> AssistantReply:
    result = answer_question(body.question)
    return AssistantReply(
        topic=result.topic.id if result.topic else None,
        title=result.topic.title if result.topic else None,
        answer=result.answer,
        emergency=result.emergency,
        language=result.language,
    )
