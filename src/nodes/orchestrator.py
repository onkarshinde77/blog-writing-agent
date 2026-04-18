"""
Orchestrator node for Blog Writing Agent.
Creates the blog outline/plan based on topic and evidence.
"""
from typing import Dict
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import model
from src.prompts import ORCH_SYSTEM
from src.schemas import State, Plan
import time

# ============================================================================
# Orchestrator Node
# ============================================================================
def orchestrator(state: State) -> Dict:
    """
    Generate blog plan with sections and metadata.
    
    Args:
        state (State): Current workflow state with topic, mode, and evidence
    
    Returns:
        Dict: Updated state with generated Plan
    """
    planner = model.with_structured_output(Plan)
    evidence = state["evidence"]
    
    # Convert Pydantic objects to dictionaries for LLM context
    evidence = [e.model_dump() for e in evidence[:10]]
    mode = state.get("mode", "closed_book")
    
    messages = [
        SystemMessage(content=ORCH_SYSTEM),
        HumanMessage(content=(f"""
                    Topic : {state['topic']}\n
                    Mode : {mode}\n\n
                    Evidence : Only for fresh claims;may be empty:\n
                    {evidence}
                    """
                    )
            
        )
    ]
    
    max_retries = 6
    last_err = None
    for attempt in range(max_retries):
        try:
            plan = planner.invoke(messages)
            if plan is None or not hasattr(plan, "tasks"):
                raise ValueError("Plan returned by LLM was invalid or empty.")
            return {"plan": plan}
        except Exception as e:
            last_err = str(e)
            print(f"Orchestrator generation failed (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(3 + attempt * 2)  # brief linear backoff
            
    raise RuntimeError(f"Orchestrator exhausted all {max_retries} retries. Last error: {last_err}")
