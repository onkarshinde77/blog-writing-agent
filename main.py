"""
Blog Writing Agent - Main Entry Point
Executes the blog writing workflow.
"""
from src.config import CONFIG
from src.graph import app
from src.schemas import State

# ============================================================================
# Main Execution Function
# ============================================================================
def run(topic: str) -> dict:
    """
    Execute the blog writing workflow for a given topic.
    
    Args:
        topic (str): Blog topic to write about
    
    Returns:
        dict: Final state including generated blog post
    
    Example:
        >>> result = run("State of Multimodal LLMs in 2026")
        >>> print(result["final"])
    """
    out = app.invoke(
        {
            "topic": topic,
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "sections": [],
            "final": "",
        },
        config=CONFIG
    )

    return out


# ============================================================================
# Entry Point
# ============================================================================
if __name__ == "__main__":
    # Example usage
    topic = "State of Multimodal LLMs in 2026"
    print(f"Generating blog on: {topic}")
    print("=" * 80)
    
    result = run(topic)
    
    print("\n" + "=" * 80)
    print("Blog generation completed!")
    print(f"\nFinal blog post:\n{result.get('final', '')}")
