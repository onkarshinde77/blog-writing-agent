"""
Graph assembly and workflow definition for Blog Writing Agent.
Constructs the LangGraph state machine workflow.
"""
from langgraph.graph import StateGraph, START, END
from src.schemas import State
from src.nodes import (
    router_node,
    route_next,
    research_node,
    orchestrator,
    fanout,
    workers,
    reducer_node,
)
from langgraph.checkpoint.memory import MemorySaver
from src.publishing.nodes import (
    review_node, blog_approval_node, revise_node, route_blog_approval,
    publish_fanout, publisher_task, aggregate_publications,
    linkedin_content_node, linkedin_approval_node, route_linkedin_approval,
    linkedin_publish_node, final_result_node,
)
import os
import logging

log = logging.getLogger(__name__)

def _checkpointer():
    """Use PostgreSQL in deployed setups; preserve MemorySaver for local development."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return MemorySaver()
    from langgraph.checkpoint.postgres import PostgresSaver
    manager = PostgresSaver.from_conn_string(dsn)
    saver = manager.__enter__()
    saver.setup()
    return saver

# Graph Assembly
def build_graph():
    """
    Build and compile the LangGraph workflow.
    Returns: CompiledStateGraph: Compiled graph ready for execution
    Workflow: generation → reducer → review/approval → parallel publishing → aggregation → LinkedIn approval/publish.
    """
    graph = StateGraph(State)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("research", research_node)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("workers", workers)
    graph.add_node("reducer", reducer_node)
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
        {"research": "research", "orchestrator": "orchestrator"}
    )
    
    # Research → Orchestrator
    graph.add_edge("research", "orchestrator")

    # Orchestrator → Workers (fan out)
    graph.add_conditional_edges("orchestrator", fanout, ["workers"])
    
    # Workers → Reducer
    graph.add_edge("workers", "reducer")
    
    # Preserve generation through reducer, then gate every external publication on approval.
    graph.add_edge("reducer", "review")
    graph.add_edge("review", "blog_approval")
    graph.add_conditional_edges("blog_approval", route_blog_approval)
    graph.add_edge("revision", "review")
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
