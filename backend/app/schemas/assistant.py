"""Request and response shapes for POST /assistant/query."""

from pydantic import BaseModel, ConfigDict, Field


class AssistantQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=500)


class AssistantReply(BaseModel):
    topic: str | None  # id of the matched topic; None = no match (fallback answer)
    title: str | None
    answer: str
    emergency: str  # always "Emergency: 112. Tourist helpline: 1363."
    language: str  # language of the question: "en", "hi" or "hi-Latn"
    note: str = (
        "Answers come from a fixed, hand-written list (in English). General guidance only, "
        "not legal or medical advice."
    )
