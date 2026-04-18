"""
Research node for Blog Writing Agent.
Performs web search and synthesizes evidence items.
"""
from typing import List, Dict
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import model
from src.prompts import RESEARCH_SYSTEM
from src.schemas import State, EvidencePack
from src.tools import tavily_search

# Research Node
def research_node(state: State) -> Dict:
    """
    Execute web research based on router-generated queries.
    
    Args:
        state (State): Current workflow state containing queries
    
    Returns:
        Dict: Updated state with deduplicated evidence items
    """
    queries = state['queries'] or []
    max_results = 3
    raw_results: List[dict] = []
    
    # Perform search for each query
    for q in queries:
        raw_results.extend(tavily_search(q, max_result=max_results))
    
    if not raw_results:
        return {"evidence": []}
    
    # Extract and structure evidence using LLM
    import json
    import time
    import re
    
    extractor = model.with_structured_output(EvidencePack)
    pack = None
    
    for attempt in range(5):
        try:
            pack = extractor.invoke([
                SystemMessage(content=RESEARCH_SYSTEM),
                HumanMessage(content=f"Raw results:\n{raw_results}")
            ])
            break
        except Exception as e:
            error_str = str(e)
            # Try to recover from Groq's 400 tool_use_failed where it emits raw `<function>` tags instead of an API call
            if "failed_generation" in error_str and "<function=" in error_str:
                print(f"Attempting to recover failed generation from Groq (attempt {attempt+1})...")
                # Extract the JSON payload within the <function> tags
                match = re.search(r'<function.*?>\s*({.*?})\s*</function>', error_str, re.DOTALL | re.IGNORECASE)
                if match:
                    try:
                        json_str = match.group(1)
                        # Clean up common json string escapes that might be in the error dump
                        json_str = json_str.replace('\\"', '"').replace('\\n', '\n')
                        data = json.loads(json_str)
                        pack = EvidencePack(**data)
                        break
                    except Exception as inner_e:
                        print(f"Failed to decode recovered json: {inner_e}")
            
            if attempt == 4:
                raise e
                
            print(f"Research node extractor failed parsing, retrying {attempt+2}/5...")
            time.sleep(3)
            
    if pack is None:
        return {"evidence": []}
    
    # Deduplicate by URL
    dedup = {}
    for e in pack.evidence:
        if e.url:
            dedup[e.url] = e
    
    return {"evidence": list(dedup.values())}
