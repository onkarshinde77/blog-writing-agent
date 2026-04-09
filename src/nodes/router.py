"""
Router node for Blog Writing Agent.
Determines if web research is needed and selects appropriate mode.
"""
from typing import Dict
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import model
from src.prompts import ROUTER_SYSTEM
from src.schemas import State, RouterDecision

 
# Router Node
def router_node(state: State) -> Dict:
    """
    Route the topic determination: decide if research is needed.
    
    Args:
        state (State): Current workflow state
    
    Returns:
        Dict: Updated state with needs_research, mode, and queries
    """
    topic = state["topic"]
    decider = model.with_structured_output(RouterDecision)
    decision = decider.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {topic}")
        ]
    )
    
    return {
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": decision.queries
    }

 
# Conditional Edge Function
def route_next(state: State) -> str:
    """
    Conditional routing function: determine next node after router.
    
    Args:
        state (State): Current workflow state
    
    Returns:
        str: Next node name ("research" or "orchestrator")
    """
    return "research" if state['needs_research'] else "orchestrator"
