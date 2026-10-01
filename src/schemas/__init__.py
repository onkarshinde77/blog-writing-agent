"""
Data models and schemas for Blog Writing Agent.
Defines Pydantic models for type safety and validation.
"""
from __future__ import annotations
import operator
from typing import List, Dict, Annotated, TypedDict, Literal, Optional
from pydantic import BaseModel, Field, field_validator

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
        description="3-5 concrete, non-overlapping subpoints to cover in this section.",
    )
    target_words: int = Field(
        ...,
        description="Target word count for this section (100–250).",
    )
    tags: List[str]
    requires_research: bool
    requires_code: bool

    @field_validator("bullets")
    @classmethod
    def validate_bullet_count(cls, bullets: List[str]) -> List[str]:
        if not 3 <= len(bullets) <= 5:
            raise ValueError("Each plan section must contain between 3 and 5 bullets.")
        return bullets

    @field_validator("target_words")
    @classmethod
    def validate_target_words(cls, target_words: int) -> int:
        if not 100 <= target_words <= 250:
            raise ValueError("Each plan section must target between 100 and 250 words.")
        return target_words

# Plan Schema
class Plan(BaseModel):
    """Complete blog plan with all sections and metadata."""
    blog_title: str
    tasks: List[Task]
    tone: str = Field(..., description="Writing tone (e.g., practical, crisp).")
    audience: str = Field(..., description="The intended readership identified by the topic and audience analysis.")
    blog_kind: Literal["explainer", "tutorial", "news_roundup", "comparison", "system_design", "essay"]
    constraints: List[str]

    @field_validator("tasks")
    @classmethod
    def validate_task_count(cls, tasks: List[Task]) -> List[Task]:
        if not 3 <= len(tasks) <= 5:
            raise ValueError("A blog plan must contain between 3 and 5 sections.")
        return tasks

# Router Decision Schema
class RouterDecision(BaseModel):
    """Decision output from router: whether research is needed and mode."""
    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    queries: List[str] = Field(default_factory=list)


class TopicAudienceAnalysis(BaseModel):
    """Guidance for matching a blog's content and depth to its topic and reader."""
    topic_type: str = Field(..., description="What kind of topic this is, such as personal, social, practical, scientific, educational, or technical.")
    likely_audience: str = Field(..., description="The people most likely to read the article and what they already know.")
    reader_intent: str = Field(..., description="What the reader likely wants to understand, decide, or do.")
    complexity: Literal["introductory", "intermediate", "advanced", "varies"]
    useful_angle: str = Field(..., description="A specific, reader-relevant angle for the article.")
    voice: str = Field(..., description="A natural voice and level of formality that fit this topic and audience.")
    use_code: bool
    code_rationale: str
    use_formulas: bool
    formulas_rationale: str
    use_statistics: bool
    statistics_rationale: str
    use_technical_terminology: bool
    terminology_rationale: str
    use_examples: bool
    examples_rationale: str
    use_step_by_step: bool
    step_by_step_rationale: str
    avoid: List[str] = Field(default_factory=list, description="Irrelevant formats, jargon, or assumptions to avoid for this topic.")

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
    input_mode: str
    existing_blog: Optional[BlogData]
    # routing / research
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    audience_analysis: Optional[dict]
    plan: Optional[Plan]
    # workers
    sections: Annotated[List[tuple[int, str]], operator.add]  # (task_id, section_md)
    final: str
    # Review, approval, and distribution state (the original generation state is unchanged).
    quality_report: Optional[dict]
    quality_passed: bool
    quality_attempt: int
    quality_research_attempts: int
    quality_needs_research: bool
    quality_queries: List[str]
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
