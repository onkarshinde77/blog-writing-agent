import re
from typing import Dict, List
from src.schemas import State, EvidenceItem
from src.tools import duck_search


def clean_body(text: str) -> str:

    if not isinstance(text, str):
        return ""

    if not text.strip():
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    # Remove markdown links but keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Keep mostly English sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)

    english_sentences = []
    for sentence in sentences:
        if not sentence.strip():
            continue
        english_chars = len(re.findall(r"[A-Za-z]", sentence))
        total_chars = len(re.findall(r"[A-Za-z\u00C0-\uFFFF]", sentence))

        if total_chars == 0:
            continue
        if english_chars / total_chars >= 0.7:
            english_sentences.append(sentence.strip())

    text = " ".join(english_sentences)
    # Normalize spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def research_node(state: State) -> Dict:
    queries = state.get("queries", [])
    if not queries:
        print("[Research] No queries found.")
        return {"evidence": []}

    evidence: List[EvidenceItem] = []
    for query in queries:
        if not isinstance(query, str) or not query.strip():
            continue
        print(f"[Research] Searching: {query}")
        try:
            results = duck_search(
                query=query,
                max_results=5
            )
        except Exception as e:
            print(f"[Research] Search failed: {query}")
            print(f"[Research] Error: {e}")
            continue

        if not results:
            print(f"[Research] No results: {query}")
            continue

        for result in results:
            if not isinstance(result, dict):
                continue
            title = result.get("title", "")
            url = result.get("href", "")
            body = result.get("body", "")

            if not body:
                continue
            try:
                body = clean_body(body)
            except Exception as e:
                print(f"[Research] Cleaning failed: {e}")
                continue

            if not body:
                continue

            evidence.append(
                EvidenceItem(
                    title=title,
                    url=url,
                    content=body
                )
            )

    print(f"[Research] Total evidence items: {len(evidence)}")
    return {
        "evidence": evidence
    }