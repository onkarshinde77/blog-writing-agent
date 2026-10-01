"""Analyze a topic and its likely audience before creating the blog plan."""
from typing import Dict

from langchain_core.messages import HumanMessage, SystemMessage

from src.config import model
from src.prompts import TOPIC_ANALYSIS_SYSTEM
from src.schemas import State, TopicAudienceAnalysis


def topic_analysis_node(state: State) -> Dict:
    """Return reader-focused writing guidance for all downstream content nodes."""
    analysis = model.with_structured_output(TopicAudienceAnalysis).invoke(
        [
            SystemMessage(content=TOPIC_ANALYSIS_SYSTEM),
            HumanMessage(content=f"Analyze this blog topic before planning: {state['topic']}"),
        ]
    )
    if analysis is None:
        raise ValueError("Topic and audience analysis returned no result.")
    return {"audience_analysis": analysis.model_dump()}
