"""
Tools and utilities for Blog Writing Agent.
Contains search and data processing functions.
"""
from typing import List, Dict
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch

# ============================================================================
# Web Search Tool
# ============================================================================
def tavily_search(query: str, max_result: int = 5) -> List[Dict]:
    """
    Perform web search using Tavily Search API.
    
    Args:
        query (str): Search query string
        max_result (int): Maximum number of results to return (default: 5)
    
    Returns:
        List[Dict]: Normalized search results with title, url, and content
    
    Example:
        results = tavily_search("LLM optimization techniques")
        for r in results:
            print(r["title"], r["url"])
    """
    tool = TavilySearch(max_results=max_result)
    response = tool.invoke(query)
    if isinstance(response, dict):
        results = response.get("results", [])
    normalized: List[Dict] = []
    
    for r in results[:max_result]:
        normalized.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": (r.get("content") or r.get("snippet") or ""),
        })

    return normalized

