"""
Orchestrator node for Blog Writing Agent.
Creates the blog outline/plan based on topic and evidence.
"""
import json
from typing import Dict
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import model
from src.prompts import ORCH_SYSTEM
from src.schemas import State, Plan
import time

# Orchestrator Node
def orchestrator(state: State) -> Dict:
    """
    Generate blog plan with sections and metadata.
    
    Args:
        state (State): Current workflow state with topic, mode, and evidence
    
    Returns:
        Dict: Updated state with generated Plan
    """
    # JSON mode avoids Groq's tool-call argument parser. We include the concrete
    # schema in the prompt and then validate the parsed object with Pydantic.
    planner = model.with_structured_output(Plan, method="json_mode")
    evidence = state["evidence"]
    
    # Convert Pydantic objects to dictionaries for LLM context
    print("evidence : ",evidence)
    evidence = [e.model_dump() for e in evidence[:10]]
    mode = state.get("mode", "closed_book")
    audience_analysis = state.get("audience_analysis") or {}
    
    plan_schema = json.dumps(Plan.model_json_schema(), ensure_ascii=False)
    messages = [
        SystemMessage(content=ORCH_SYSTEM),
        HumanMessage(content=(f"""
                    Topic : {state['topic']}\n
                    Topic & Audience Analysis (follow this guidance when planning): {audience_analysis}\n
                    Mode : {mode}\n\n
                    Evidence : Only for fresh claims;may be empty:\n
                    {evidence}

                    Return exactly one valid JSON object. Do not use Markdown fences or add text outside the object.
                    Every Plan and Task field in this schema is required. Include tags, requires_research, and requires_code for every task.
                    Required JSON schema:
                    {plan_schema}
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
            if attempt < max_retries - 1:
                messages.append(HumanMessage(content=(
                    "Your previous output did not parse or validate against the required Plan schema. "
                    "Return a corrected complete JSON object only, with every required field and 3-5 bullets per task."
                )))
            time.sleep(3 + attempt * 2)  # brief linear backoff
            
    raise RuntimeError(f"Orchestrator exhausted all {max_retries} retries. Last error: {last_err}")
