"""
Orchestrator node for Blog Writing Agent.
Creates the blog outline/plan based on topic and evidence.
"""
from typing import Dict
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import model
from src.prompts import ORCH_SYSTEM
from src.schemas import State, Plan

 
# Orchestrator Node
def orchestrator(state: State) -> Dict:
    """
    Generate blog plan with sections and metadata.
    
    Args:
        state (State): Current workflow state with topic, mode, and evidence
    
    Returns:
        Dict: Updated state with generated Plan
    """
    try:
        planner = model.with_structured_output(Plan)
        evidence = state["evidence"]
        
        # Convert Pydantic objects to dictionaries for LLM context
        evidence = [e.model_dump() for e in evidence[:10]]
        mode = state.get("mode", "closed_book")
        
        plan = planner.invoke([
            SystemMessage(content=ORCH_SYSTEM),
            HumanMessage(content=(f"""
                        Topic : {state['topic']}\n
                        Mode : {mode}\n\n
                        Evidence : Only for fresh claims;may be empty:\n
                        {evidence}
                        """
                        )
                
            )
        ])
        return {"plan": plan}
    except Exception as e:
        print(str(e))
