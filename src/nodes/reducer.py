"""
Reducer node for Blog Writing Agent.
Combines all sections into final blog post and saves to file.
"""
from typing import Dict
from pathlib import Path
from src.schemas import State

# Reducer Node
def reducer_node(state: State) -> dict:
    """
    Combine all generated sections into final blog post.
    
    Args:
        state (State): Current workflow state with all sections
    
    Returns:
        Dict: Final markdown content
    """
    plan = state["plan"]

    # Sort sections by task ID to maintain correct order
    ordered_sections = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    
    # Combine sections into final markdown
    body = "\n\n".join(ordered_sections).strip()
    final_md = f"# {plan.blog_title}\n\n{body}\n"

    # Save to file
    filename = f"{plan.blog_title}.md"
    Path(filename).write_text(final_md, encoding="utf-8")

    return {"final": final_md}
