"""Pydantic schemas for every LLM decision node (structured output)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RouteName = Literal["vectorstore", "sql_lookup", "web_search"]


class RouteDecision(BaseModel):
    source: RouteName = Field(
        description=(
            "vectorstore: NexCart policies, FAQs, product manuals, troubleshooting. "
            "sql_lookup: a specific order ID or customer order status/ETA/items. "
            "web_search: current events, outages, live web info, or anything not in "
            "NexCart internal docs or the orders database."
        )
    )
    rationale: str = Field(description="One-sentence reason for this route.")


class DocumentGrade(BaseModel):
    index: int = Field(description="0-based index of the document being graded.")
    relevant: bool = Field(
        description="True if this document can help answer the user question."
    )


class DocumentGrades(BaseModel):
    grades: list[DocumentGrade]


class RewrittenQuery(BaseModel):
    query: str = Field(description="Improved search query for retrieval or web search.")
    reason: str = Field(description="Why the original query was insufficient.")


class OrderLookupParse(BaseModel):
    order_id: str | None = Field(
        default=None,
        description="Order number digits only if present, else null.",
    )
    customer_email: str | None = Field(
        default=None,
        description="Customer email if present, else null.",
    )


class AnswerGrade(BaseModel):
    grounded: bool = Field(
        description=(
            "True if the answer's facts appear in the context (paraphrase allowed). "
            "False only if it invents numbers/dates/fees/names not in the context."
        )
    )
    relevant: bool = Field(
        description="True if the answer is about the user's question. Independent of grounded."
    )
    reason: str = Field(description="Brief justification.")
