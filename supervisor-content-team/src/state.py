"""Shared state schema. Every node reads from and writes to one ContentState dict."""

import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field


# The agents the supervisor can hand off to, plus the terminal signal.

Worker = Literal["researcher", "writer", "editor", "seo", "FINISH"]


class ContentState(TypedDict, total=False):
    """The single source of truth passed between every node."""

    topic: str             # the input subject for the article
    research: str          # synthesized findings from the researcher
    draft: str             # the writer's article draft
    edited: str            # the editor's tightened version
    seo: dict              # title, meta_description, keywords, slug
    editor_verdict: str    # "approved" or "revision" - set by the editor
    editor_feedback: str   # the editor's reason when a revision is requested
    revision_count: int    # how many writer rewrites have happened
    next: str              # the supervisor's latest routing decision
    step: int              # number of supervisor turns so far(capped by MAX_STEPS)
    
    history: Annotated[list[str], operator.add]


class Route(BaseModel):
    """Structured routing decision the supervisor LLM must produce."""
    next: Worker = Field(
    description="Which agent runs next, or FINISH when the article is done."
        )
    reason: str = Field(description="One short sentence explaining the choice.")