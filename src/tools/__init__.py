"""
Tools and utilities for Blog Writing Agent.
Contains search and data processing functions.
"""
from typing import List, Dict
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch
from langchain_community.tools import DuckDuckGoSearchResults # not work
from ddgs import DDGS
from ddgs.exceptions import DDGSException

# Web Search Tool
def duck_search(query: str, max_results: int = 5) -> list[dict]:
    try:
        results = DDGS().text(
            query,
            max_results=max_results
        )
        if not results:
            return []
        return results

    except DDGSException as e:
        print(f"[DuckDuckGo] No results for: {query}")
        print(f"[DuckDuckGo] Reason: {e}")
        return []

    except Exception as e:
        print(f"[DuckDuckGo] Unexpected error for: {query}")
        print(f"[DuckDuckGo] Reason: {e}")
        return []

# def tavily_search(query: str, max_result: int = 5) -> List[Dict]:
#     """
#     Perform web search using Tavily Search API.
#     Args:
#         query (str): Search query string
#         max_result (int): Maximum number of results to return (default: 5)
    
#     Returns:
#         List[Dict]: Normalized search results with title, url, and content
#     Example:
#         results = tavily_search("LLM optimization techniques")
#         for r in results:
#             print(r["title"], r["url"])
#     """
#     tool = TavilySearch(max_results=max_result)
#     response = tool.invoke(query)
#     if isinstance(response, dict):
#         results = response.get("results", [])
#     normalized: List[Dict] = []
    
#     for r in results[:max_result]:
#         normalized.append({
#             "title": r.get("title", ""),
#             "url": r.get("url", ""),
#             "content": (r.get("content") or r.get("snippet") or ""),
#         })

#     return normalized