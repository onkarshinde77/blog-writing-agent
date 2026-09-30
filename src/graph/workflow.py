"""
Graph assembly and workflow definition for Blog Writing Agent.
Constructs the LangGraph state machine workflow.
"""
from langgraph.graph import StateGraph, START, END
from src.schemas import State, Plan, Task, EvidenceItem
from src.nodes import (
    router_node,
    route_next,
    research_node,
    topic_analysis_node,
    orchestrator,
    fanout,
    workers,
    reducer_node,
)
from src.nodes.quality_control import (
    quality_check_node, quality_research_node, quality_revision_node,
    route_quality_check,
)
from src.publishing.nodes import (
    review_node, blog_approval_node, revise_node, route_blog_approval,
    publish_fanout, publisher_task, aggregate_publications,
    linkedin_content_node, linkedin_approval_node, route_linkedin_approval,
    linkedin_publish_node, final_result_node,
)
import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)
_checkpointer_manager = None

def _checkpointer():
    """Use the project's local SQLite file for durable workflow checkpoints."""
    global _checkpointer_manager
    db_path = Path(os.getenv("PUBLISHING_DB_PATH", "publishing.db"))
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parents[2] / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    connection = sqlite3.connect(str(db_path), check_same_thread=False)
    _checkpointer_manager = connection
    saver = SqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=[Plan, Task, EvidenceItem]))
    saver.setup()
    return saver

# Graph Assembly
def build_graph():
    """
    Build and compile the LangGraph workflow.
    Returns: CompiledStateGraph: Compiled graph ready for execution
    Workflow: generation → reducer → quality gate → review/approval → parallel publishing → aggregation → LinkedIn approval/publish.
    """
    graph = StateGraph(State)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("research", research_node)
    graph.add_node("topic_analysis", topic_analysis_node)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("workers", workers)
    graph.add_node("reducer", reducer_node)
    graph.add_node("quality_check", quality_check_node)
    graph.add_node("quality_research", quality_research_node)
    graph.add_node("quality_revision", quality_revision_node)
    graph.add_node("review", review_node)
    graph.add_node("blog_approval", blog_approval_node)
    graph.add_node("revision", revise_node)
    graph.add_node("publisher", publisher_task)
    graph.add_node("aggregate_publications", aggregate_publications)
    graph.add_node("linkedin_content", linkedin_content_node)
    graph.add_node("linkedin_approval", linkedin_approval_node)
    graph.add_node("linkedin_publish", linkedin_publish_node)
    graph.add_node("finish", final_result_node)
    
    # Add edges
    graph.add_edge(START, "router")
    
    # Conditional edge: research needed or not
    graph.add_conditional_edges(
        "router",
        route_next,
        {"research": "research", "topic_analysis": "topic_analysis"}
    )
    
    # Topic and audience analysis informs planning whether research ran or not.
    graph.add_edge("research", "topic_analysis")
    graph.add_edge("topic_analysis", "orchestrator")

    # Orchestrator → Workers (fan out)
    graph.add_conditional_edges("orchestrator", fanout, ["workers"])
    
    # Workers → Reducer
    graph.add_edge("workers", "reducer")
    
    # Run the final quality gate before the existing review and approval flow.
    graph.add_edge("reducer", "quality_check")
    graph.add_conditional_edges(
        "quality_check",
        route_quality_check,
        {
            "review": "review",
            "quality_research": "quality_research",
            "quality_revision": "quality_revision",
            "quality_failed": "finish",
        },
    )
    graph.add_edge("quality_research", "quality_check")
    graph.add_edge("quality_revision", "quality_check")
    graph.add_edge("review", "blog_approval")
    graph.add_conditional_edges("blog_approval", route_blog_approval)
    graph.add_edge("revision", "quality_check")
    graph.add_conditional_edges("publisher", lambda state: "aggregate_publications", ["aggregate_publications"])
    graph.add_edge("aggregate_publications", "linkedin_content")
    graph.add_edge("linkedin_content", "linkedin_approval")
    graph.add_conditional_edges("linkedin_approval", route_linkedin_approval,
                                {"linkedin_publish": "linkedin_publish", "linkedin_content": "linkedin_content", "linkedin_approval": "linkedin_approval", "finish": "finish"})
    graph.add_edge("linkedin_publish", "finish")
    graph.add_edge("finish", END)

    checkpointer = _checkpointer()
    return graph.compile(checkpointer=checkpointer)

app = build_graph()
# graph = app.get_graph()
# output_path = Path(__file__).parent / "graph.png"
# graph.draw_mermaid_png(output_file_path=str(output_path))
