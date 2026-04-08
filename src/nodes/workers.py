"""
Workers node for Blog Writing Agent.
Generates individual blog sections in parallel.
"""
from typing import Dict
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Send
from src.config import model
from src.prompts import WORKER_SYSTEM
from src.schemas import State, Task, Plan, EvidenceItem

# ============================================================================
# Fanout Conditional Edge Function
# ============================================================================
def fanout(state: State):
    """
    Fan out to workers: create parallel tasks for each section.
    
    Args:
        state (State): Current workflow state with plan
    
    Returns:
        List[Send]: List of Send objects routing to workers
    """
    # Create a Send object for each task (section) to be processed in parallel
    workers_list = [Send(
        "workers",
        {
            "task": task,
            "topic": state['topic'],
            "mode": state['mode'],
            "plan": state['plan'].model_dump(),
            "evidence": [e.model_dump() for e in state['evidence']]
        }) 
        for task in state['plan'].tasks]
    
    return workers_list

# ============================================================================
# Workers Node
# ============================================================================
def workers(payload: Dict) -> Dict:
    """
    Write one blog section based on task and context.
    
    Args:
        payload (Dict): Contains task, plan, evidence, topic, and mode
    
    Returns:
        Dict: Section content with task ID for ordering
    """
    # Reconstruct Pydantic objects from payload dictionaries
    task_data = payload["task"]
    if isinstance(task_data, dict):
        task = Task(**task_data)
    else:
        task = task_data
    plan = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]
    topic = payload["topic"]
    mode = payload.get("mode", "closed_book")
    
    # Format bullets as text
    bullets_text = "\n- " + "\n- ".join(task.bullets)
    
    # Format evidence as text
    evidence_text = ""
    if evidence:
        evidence_text = "\n".join(
            f"""- {e.title} | {e.url}""".strip()
            for e in evidence[:20]
        )
    
    messages = [
        SystemMessage(content=WORKER_SYSTEM),
        HumanMessage(
            content=(
                f"Blog title: {plan.blog_title}\n"
                f"Audience: {plan.audience}\n"
                f"Tone: {plan.tone}\n"
                f"Blog kind: {plan.blog_kind}\n"
                f"Constraints: {plan.constraints}\n"
                f"Topic: {topic}\n"
                f"Mode: {mode}\n\n"
                f"Section title: {task.title}\n"
                f"Goal: {task.goal}\n"
                f"Target words: {task.target_words}\n"
                f"Tags: {task.tags}\n"
                f"requires_research: {task.requires_research}\n"
                f"requires_citations: {task.requires_citations}\n"
                f"requires_code: {task.requires_code}\n"
                f"Bullets:{bullets_text}\n\n"
                f"Evidence (ONLY use these URLs when citing):\n{evidence_text}\n"
            )
        )
    ]
    
    import time
    max_retries = 10
    section = ""
    for attempt in range(max_retries):
        try:
            section = model.invoke(messages).content.strip()
            break
        except Exception as e:
            if "RateLimitError" in str(type(e)) or "429" in str(e):
                if attempt == max_retries - 1:
                    raise e
                wait_time = 6 + (attempt * 5)  # e.g., 6s, 11s, 16s...
                print(f"Worker task '{task.title}' hit rate limit. Waiting {wait_time}s before attempt {attempt + 2}/{max_retries}...")
                time.sleep(wait_time)
            else:
                raise e
    
    return {"sections": [(task.id, section)]}
