"""Final evidence, completeness, and correctness gate for generated articles."""
from __future__ import annotations

import logging
import re
from typing import Any, Literal
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.markdown_math import normalize_markdown_math
from src.blog_history import save_state_blog
from src.schemas import State

log = logging.getLogger(__name__)
MAX_AUTOMATIC_REVISIONS = 2
MAX_SUPPLEMENTAL_RESEARCH = 1


class QualityFinding(BaseModel):
    category: Literal[
        "completeness", "citation", "unsupported_claim", "classification",
        "calculation", "units", "structure",
    ]
    severity: Literal["critical", "major", "minor"]
    excerpt: str = Field(description="Short quote or section name locating the issue")
    issue: str
    correction: str


class QualityAudit(BaseModel):
    passed: bool
    summary: str
    findings: list[QualityFinding] = Field(default_factory=list)
    needs_research: bool = False
    research_queries: list[str] = Field(default_factory=list)


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def _evidence_records(evidence: list[Any]) -> list[dict[str, str]]:
    records = []
    for item in evidence:
        item = _plain(item)
        if isinstance(item, dict) and item.get("url"):
            records.append({
                "title": str(item.get("title", "")),
                "url": str(item.get("url", "")),
                "content": str(item.get("content", ""))[:1200],
            })
    return records


def _structural_findings(state: State, article: str, evidence: list[dict[str, str]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(category: str, excerpt: str, issue: str, correction: str) -> None:
        findings.append({"category": category, "severity": "major", "excerpt": excerpt[:180], "issue": issue, "correction": correction})

    plan = _plain(state.get("plan"))
    tasks = plan.get("tasks", []) if isinstance(plan, dict) else getattr(plan, "tasks", [])
    expected_ids = {str(_plain(task).get("id") if isinstance(_plain(task), dict) else getattr(task, "id", "")) for task in tasks}
    sections = state.get("sections", [])
    received_ids = {str(section[0]) for section in sections if isinstance(section, (tuple, list)) and len(section) == 2}
    missing = sorted(expected_ids - received_ids)
    if missing:
        add("completeness", "Missing generated sections", f"Planned sections with no worker output: {', '.join(missing)}.", "Write every missing planned section before continuing.")
    empty_sections = [str(section[0]) for section in sections if isinstance(section, (tuple, list)) and len(section) == 2 and not str(section[1]).strip()]
    if empty_sections:
        add("completeness", "Empty generated sections", f"Sections with IDs {', '.join(empty_sections)} contain no text.", "Write complete content for every empty section.")
    if not article.strip():
        add("completeness", "Empty article", "The final article has no content.", "Write the complete article from the approved plan.")

    outside_code = re.sub(r"(?s)(```.*?```|~~~.*?~~~)", "", article)
    if outside_code.count("$$") % 2:
        add("completeness", "Unclosed display equation", "A display-math delimiter is unmatched.", "Close or repair the equation delimiters.")
    code_blocks = re.findall(r"```|~~~", article)
    if len(code_blocks) % 2:
        add("completeness", "Unclosed code block", "A fenced code block is not closed.", "Complete or close the code block.")

    valid_urls = {_canonical_url(item["url"]) for item in evidence}
    content_without_code = re.sub(r"(?s)(```.*?```|~~~.*?~~~)", "", article)
    for match in re.finditer(r"(?<!!)\[[^\]]+\]\((https?://[^\s)]+)(?:\s+[^)]*)?\)", content_without_code):
        url = match.group(1).rstrip(".,;:")
        if _canonical_url(url) not in valid_urls:
            add("citation", match.group(0), "This citation does not point to a URL in the supplied research evidence.", "Replace it with a supporting evidence URL or remove the unsupported claim.")
    return findings


def quality_check_node(state: State) -> dict:
    """Audit the full article; block approval until it passes or exhausts safe retries."""
    from src.config import get_model

    article = normalize_markdown_math(state.get("final", ""))
    evidence = _evidence_records(state.get("evidence", []))
    hard_findings = _structural_findings(state, article, evidence)
    prompt = f"""Audit this complete article against every quality requirement. Return a structured pass/fail result and actionable findings.

Requirements:
1. Check every planned section for completion. Find cut-off sections, incomplete sentences, dangling clauses, unclosed code/math blocks, and missing conclusions.
2. Inspect every specific factual and numerical claim. Verify it against the supplied evidence, not memory alone. Required claims need an inline Markdown citation like [Source title](exact-evidence-URL). Reject fabricated, irrelevant, or unsupported citations.
3. Identify unsupported claims. Do not pass an unsupported claim merely because it sounds plausible; request revision to remove it, qualify it, or support it with evidence.
4. Make the distinction clear: sourced facts are cited; predictions are labelled Forecast; premises are labelled Assumption; interpretation is labelled Analysis. Flag forecasts or assumptions stated as established fact.
5. Recalculate arithmetic and check units, conversions, orders of magnitude, and dimensional consistency. Flag any result that cannot be verified.
6. Set passed=false for any unresolved critical or major problem. Minor style suggestions alone do not fail the gate.

When evidence is insufficient for an important factual/numerical claim, set needs_research=true and provide 2-4 focused search queries. Never invent URLs. If evidence is empty, request research for claims that require sourcing; standard definitions or derivations may pass only when internally consistent and clearly presented.

PLANNED SECTION COUNT: {len((_plain(state.get('plan')) or {}).get('tasks', [])) if isinstance(_plain(state.get('plan')), dict) else len(getattr(state.get('plan'), 'tasks', []))}
DETERMINISTIC CHECKS: {hard_findings}
SUPPLIED EVIDENCE (only these URLs are citable): {evidence[:16]}
ARTICLE:
{article}
"""
    try:
        audit_obj = get_model(state.get("model_name")).with_structured_output(QualityAudit).invoke([
            SystemMessage(content="You are a strict final editorial, source-verification, and calculation auditor. Be evidence-led and do not claim to have verified unavailable facts."),
            HumanMessage(content=prompt),
        ])
        audit = _plain(audit_obj)
        if not isinstance(audit, dict):
            raise TypeError("Quality audit response was not an object")
        audit = QualityAudit.model_validate(audit)
        llm_findings = [finding.model_dump() for finding in audit.findings]
        all_findings = hard_findings + llm_findings
        passed = audit.passed and not hard_findings and not any(item["severity"] in {"critical", "major"} for item in llm_findings)
        report = {
            "status": "passed" if passed else "failed",
            "summary": audit.summary,
            "findings": all_findings,
            "research_requested": audit.needs_research,
        }
        queries = [query.strip() for query in audit.research_queries if isinstance(query, str) and query.strip()][:4]
        if audit.needs_research and not queries:
            queries = [f"authoritative sources for key factual and numerical claims in: {state.get('topic', 'this article')}"]
        return {
            "final": article,
            "quality_report": report,
            "quality_passed": passed,
            "quality_needs_research": bool(audit.needs_research and queries),
            "quality_queries": queries,
        }
    except Exception:
        log.exception("quality_audit_failed workflow_id=%s", state.get("workflow_id", ""))
        report = {
            "status": "failed",
            "summary": "The automated quality audit could not complete; the article is blocked from approval until it can be checked.",
            "findings": hard_findings + [{
                "category": "structure", "severity": "critical", "excerpt": "Quality auditor",
                "issue": "The quality audit service did not return a valid result.",
                "correction": "Retry generation after the model service is available.",
            }],
            "research_requested": False,
        }
        return {"final": article, "quality_report": report, "quality_passed": False, "quality_needs_research": False, "quality_queries": []}


def quality_research_node(state: State) -> dict:
    """Gather one supplemental batch of sources for unsupported claims."""
    from src.nodes.research import research_node

    existing = _evidence_records(state.get("evidence", []))
    extra = research_node({**state, "queries": state.get("quality_queries", [])}).get("evidence", [])
    merged: dict[str, Any] = {}
    for item in state.get("evidence", []):
        record = _plain(item)
        if isinstance(record, dict) and record.get("url"):
            merged[_canonical_url(str(record["url"]))] = item
    for item in extra:
        record = _plain(item)
        if isinstance(record, dict) and record.get("url"):
            merged.setdefault(_canonical_url(record["url"]), item)
    log.info("quality_research workflow_id=%s prior_sources=%d added_sources=%d", state.get("workflow_id", ""), len(existing), max(0, len(merged) - len(existing)))
    return {"evidence": list(merged.values()), "quality_research_attempts": int(state.get("quality_research_attempts", 0)) + 1}


def quality_revision_node(state: State) -> dict:
    """Revise the full article against the audit and return it to the quality gate."""
    from src.config import get_model

    report = state.get("quality_report") or {}
    evidence = _evidence_records(state.get("evidence", []))
    prompt = f"""Revise the complete Markdown article to fix every critical and major finding below.

Rules:
- Keep supported material and the original topic; do not silently omit a planned section.
- Use only supplied sources and cite their exact URLs using [Source title](URL). Never invent a source or citation.
- Remove or clearly qualify claims that cannot be supported; do not fabricate replacement facts.
- Label forecasts as Forecast, premises as Assumption, and interpretation as Analysis when that distinction matters.
- Recalculate numeric examples, check units, and correct dimensional or conversion errors.
- Finish every section and sentence; close code fences, braces, and display equations.
- Preserve valid Markdown math using $...$ inline and $$...$$ for display equations.
- Return only the complete revised article, with no audit commentary.

AUDIT FINDINGS:
{report.get('findings', [])}

SUPPLIED EVIDENCE:
{evidence[:16]}

ARTICLE:
{state.get('final', '')}
"""
    revised = get_model(state.get("model_name")).invoke([
        SystemMessage(content="You are a careful technical editor revising a complete article against a strict quality audit."),
        HumanMessage(content=prompt),
    ]).content
    if isinstance(revised, list):
        revised = "\n".join(str(item) for item in revised)
    revised = normalize_markdown_math(str(revised)).strip()
    save_state_blog({**state, "final": revised}, status="quality_revised")
    plan = _plain(state.get("plan"))
    title = plan.get("blog_title") if isinstance(plan, dict) else getattr(plan, "blog_title", state.get("topic", "blog"))
    Path(f"{title or state.get('topic', 'blog')}.md").write_text(revised + "\n", encoding="utf-8")
    return {
        "final": revised,
        "quality_attempt": int(state.get("quality_attempt", 0)) + 1,
        "quality_passed": False,
    }


def route_quality_check(state: State) -> str:
    if state.get("quality_passed"):
        return "review"
    if state.get("quality_needs_research") and int(state.get("quality_research_attempts", 0)) < MAX_SUPPLEMENTAL_RESEARCH:
        return "quality_research"
    if int(state.get("quality_attempt", 0)) < MAX_AUTOMATIC_REVISIONS:
        return "quality_revision"
    return "quality_failed"
