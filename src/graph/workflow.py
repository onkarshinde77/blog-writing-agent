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
    generate_and_place_images,
    merge_content,
    decide_images
)

# ============================================================================
# Graph Assembly
# ============================================================================
def build_graph():
    """
    Build and compile the LangGraph workflow.
    
    Returns:
        CompiledStateGraph: Compiled graph ready for execution
    
    Workflow:
        START → router → (research → orchestrator | orchestrator) → workers → reducer → END
    """

# build reducer subgraph
    reducer_graph = StateGraph(State)
    # nodes
    reducer_graph.add_node("merge_content", merge_content)
    reducer_graph.add_node("decide_images", decide_images)
    reducer_graph.add_node("generate_and_place_images", generate_and_place_images)
    # edges
    reducer_graph.add_edge(START, "merge_content")
    reducer_graph.add_edge("merge_content", "decide_images")
    reducer_graph.add_edge("decide_images", "generate_and_place_images")
    reducer_graph.add_edge("generate_and_place_images", END)

    reducer_subgraph = reducer_graph.compile()

    # main graph
    graph = StateGraph(State)

    # nodes
    graph.add_node("router", router_node)
    graph.add_node("research", research_node)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("workers", workers)
    graph.add_node("reducer", reducer_subgraph)

    
    # edges
    graph.add_edge(START, "router")
    
    # Conditional edge: research needed or not
    graph.add_conditional_edges(
        "router",
        route_next,
        {"research": "research", "orchestrator": "orchestrator"}
    )
    
    graph.add_edge("research", "orchestrator")
    graph.add_conditional_edges("orchestrator", fanout, ["workers"])
    graph.add_edge("workers", "reducer")
    graph.add_edge("reducer", END)

    workflow = graph.compile()
    
    # png_bytes = workflow.get_graph().draw_mermaid_png()
    # with open("graph.png", "wb") as f:
    #     f.write(png_bytes)
    
    return workflow

# Compiled App Instance
app = build_graph()
