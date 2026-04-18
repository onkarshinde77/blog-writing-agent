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
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

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
    graph = StateGraph(State)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("research", research_node)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("workers", workers)
    graph.add_node("reducer", reducer_node)
    
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
    
    # Reducer → END
    graph.add_edge("reducer", END)

    conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    memory = SqliteSaver(conn)
    return graph.compile(checkpointer=memory)

# ============================================================================
# Compiled App Instance
# ============================================================================
app = build_graph()
