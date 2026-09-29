"""
Data models and schemas for Blog Writing Agent.
Defines Pydantic models for type safety and validation.
"""
from __future__ import annotations
import operator
from typing import List, Dict, Annotated, TypedDict, Literal, Optional
from pydantic import BaseModel, Field

class Task(BaseModel):
    """Represents a single section/task in the blog outline."""
    id: int
    title: str
    
    goal: str = Field(
        ...,
        description="One sentence describing what the reader should be able to do/understand after this section.",
    )
    bullets: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3-5 concrete, non-overlapping subpoints to cover in this section.",
    )
    target_words: int = Field(
        ...,
        description="Target word count for this section (120–450).",
    )
    tags: List[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_code: bool = False

# Plan Schema
class Plan(BaseModel):
    """Complete blog plan with all sections and metadata."""
    blog_title: str
    tasks: List[Task]
    tone: str = Field(..., description="Writing tone (e.g., practical, crisp).")
    audience: str = Field(..., description="Who this blog is for. (e.g: enginear, normal people, doctor, student, proffessor/teacher)")
    blog_kind: Literal["explainer", "tutorial", "news_roundup", "comparison", "system_design"] = "explainer"
    constraints: List[str] = Field(default_factory=list)

# Router Decision Schema
class RouterDecision(BaseModel):
    """Decision output from router: whether research is needed and mode."""
    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    queries: List[str] = Field(default_factory=list)

# Evidence Schema
class EvidenceItem(BaseModel):
    """Single research result/evidence item."""
    title: str
    url: str
    content: str


class BlogData(TypedDict):
    title: str
    content: str
    description: str
    tags: List[str]
    cover_image: Optional[str]
    canonical_url: str


class ReviewResult(TypedDict):
    status: Literal["approved", "needs_revision"]
    issues: List[str]
    suggestions: List[str]


class HumanDecision(TypedDict, total=False):
    action: Literal["approve", "revise", "edit", "reject", "edited"]
    feedback: str
    platforms: List[str]
    blog: BlogData
    text: str


class PublicationResult(TypedDict):
    platform: str
    status: str
    post_id: Optional[str]
    url: Optional[str]
    error: Optional[str]


class LinkedInDraft(TypedDict):
    text: str
    hashtags: List[str]

# State Schema
class State(TypedDict):
    """Global state for the LangGraph workflow."""
    topic: str
    # routing / research
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]
    # workers
    sections: Annotated[List[tuple[int, str]], operator.add]  # (task_id, section_md)
    final: str
    # Review, approval, and distribution state (the original generation state is unchanged).
    blog_plan: Optional[BlogData]
    review: Optional[ReviewResult]
    human_blog_decision: Optional[HumanDecision]
    revision_feedback: str
    publish_platforms: List[str]
    published_results: Annotated[List[PublicationResult], operator.add]
    published_links: Dict[str, PublicationResult]
    successful_platforms: List[str]
    failed_platforms: List[str]
    all_published_urls: List[str]
    primary_blog_url: str
    linkedin_draft: Optional[LinkedInDraft]
    linkedin_human_decision: Optional[HumanDecision]
    linkedin_result: Optional[PublicationResult]
    workflow_id: str
    final_result: Optional[dict]
