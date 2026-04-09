"""
Data models and schemas for Blog Writing Agent.
Defines Pydantic models for type safety and validation.
"""
from __future__ import annotations
import operator
from typing import List,Dict, Annotated, TypedDict, Literal, Optional
from pydantic import BaseModel, Field


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
    
    as_of:str
    recency_days:int
    
    merged_md:str
    md_with_placeholders:str
    image_specs:List[Dict]
    
    final: str
    
# Task Schema
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
    requires_citations: bool = False
    requires_code: bool = False

# Plan Schema
class Plan(BaseModel):
    """Complete blog plan with all sections and metadata."""
    blog_title: str
    tasks: List[Task]
    tone: str = Field(..., description="Writing tone (e.g., practical, crisp).")
    audience: str = Field(..., description="Who this blog is for.")
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

class EvidencePack(BaseModel):
    """Collection of evidence items."""
    evidence: List[EvidenceItem] = Field(default_factory=list)

class ImageSpec(BaseModel):
    placeholder:str = Field(...,description="eg. [[Image_1]]")
    filename:str = Field(...,description="save under image/, eg. qkv_flow.png")
    alt:str
    caption:str
    prompt:str = Field(...,description="Prompt to send to image model")
    size:Literal["1024x1024","1024x1536","1536x1024"] = "1024x1024"
    quality:Literal["low","medium","high"] = "medium"

class GlobalImagePlan(BaseModel):
    md_with_placeholder:str
    image:List[ImageSpec] = Field(default_factory=list)